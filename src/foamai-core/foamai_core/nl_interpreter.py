"""Natural Language Interpreter Agent - Parses user prompts into CFD parameters."""

import json
import re
from typing import Dict, Any, Optional, Tuple, List
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType


class FlowContext(BaseModel):
    """Context of the flow problem."""
    is_external_flow: bool = Field(description="True if flow around object (external), False if flow through object (internal)")
    domain_type: str = Field(description="Type of domain: 'unbounded' for external flow, 'channel' for bounded flow")
    domain_size_multiplier: float = Field(description="Multiplier for domain size relative to object size (e.g., 20 for 20x object diameter)")


class CFDParameters(BaseModel):
    """Structured CFD parameters extracted from natural language.
    
    Note: Analysis type defaults to UNSTEADY (transient) unless explicitly 
    specified as steady/steady-state in the user prompt.
    """
    
    # Geometry information
    geometry_type: GeometryType = Field(description="Type of geometry (cylinder, airfoil, etc.)")
    geometry_dimensions: Dict[str, float] = Field(description="Geometry dimensions (diameter, length, etc.)")
    is_custom_geometry: bool = Field(default=False, description="True if using custom STL geometry")
    
    # Flow context
    flow_context: FlowContext = Field(description="Context of the flow (external/internal, domain type)")
    
    # Flow conditions
    flow_type: FlowType = Field(default=FlowType.LAMINAR, description="Flow type (laminar, turbulent, transitional)")
    analysis_type: AnalysisType = Field(description="Analysis type (steady, unsteady)")
    
    # Fluid properties
    velocity: Optional[float] = Field(None, description="Inlet velocity (m/s)")
    pressure: Optional[float] = Field(None, description="Reference pressure (Pa)")
    temperature: Optional[float] = Field(None, description="Temperature (K)")
    density: Optional[float] = Field(None, description="Fluid density (kg/m³)")
    viscosity: Optional[float] = Field(None, description="Dynamic viscosity (Pa·s)")
    
    # Dimensionless numbers
    reynolds_number: Optional[float] = Field(None, description="Reynolds number")
    mach_number: Optional[float] = Field(None, description="Mach number")
    
    # Boundary conditions
    inlet_conditions: Dict[str, Any] = Field(default_factory=dict, description="Inlet boundary conditions")
    outlet_conditions: Dict[str, Any] = Field(default_factory=dict, description="Outlet boundary conditions")
    wall_conditions: Dict[str, Any] = Field(default_factory=dict, description="Wall boundary conditions")
    
    # Solver preferences
    solver_type: Optional[str] = Field(None, description="Preferred solver (simpleFoam, pimpleFoam, etc.)")
    turbulence_model: Optional[str] = Field(None, description="Turbulence model (k-epsilon, k-omega, etc.)")
    
    # Simulation settings
    end_time: Optional[float] = Field(None, description="End time for transient simulations (in seconds)")
    time_step: Optional[float] = Field(None, description="Fixed time step (if specified by user)")
    simulation_time: Optional[float] = Field(None, description="Total simulation time in seconds")
    
    # Mesh preferences
    mesh_resolution: Optional[str] = Field(None, description="Mesh resolution (coarse, medium, fine)")
    
    # Advanced user-configurable parameters
    domain_size_multiplier: Optional[float] = Field(None, description="Domain size multiplier (e.g., 20 for 20x object size)")
    courant_number: Optional[float] = Field(None, description="Target Courant number for time stepping")
    min_time_step: Optional[float] = Field(None, description="Minimum time step limit")
    max_time_step: Optional[float] = Field(None, description="Maximum time step limit")
    
    # Additional parameters
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Additional extracted information")


def extract_dimensions_from_text(text: str, geometry_type: GeometryType) -> Dict[str, float]:
    """Extract dimensions from natural language text using regex patterns."""
    dimensions = {}
    
    # Common patterns for dimension extraction
    patterns = {
        # Diameter patterns
        'diameter': [
            r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*diameter',
            r'diameter\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?',
            r'd\s*=\s*(\d+\.?\d*)\s*(?:m|meter|metre)?',
            r'(\d+\.?\d*)\s*(?:mm|cm|inch|inches)\s*diameter'
        ],
        # Length patterns
        'length': [
            r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*long',
            r'length\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?',
            r'l\s*=\s*(\d+\.?\d*)\s*(?:m|meter|metre)?'
        ],
        # Chord patterns (for airfoils)
        'chord': [
            r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*chord',
            r'chord\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?',
            r'c\s*=\s*(\d+\.?\d*)\s*(?:m|meter|metre)?'
        ],
        # Width/height patterns
        'width': [
            r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*wide',
            r'width\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?'
        ],
        'height': [
            r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*(?:high|tall)',
            r'height\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?'
        ],
        # Angle of attack
        'angle_of_attack': [
            r'(\d+\.?\d*)\s*(?:deg|degree)?\s*(?:angle\s*of\s*attack|aoa)',
            r'(?:angle\s*of\s*attack|aoa)\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:deg|degree)?'
        ]
    }
    
    # Unit conversion factors to meters
    unit_conversions = {
        'mm': 0.001,
        'cm': 0.01,
        'inch': 0.0254,
        'inches': 0.0254,
        'ft': 0.3048,
        'feet': 0.3048
    }
    
    text_lower = text.lower()
    
    # Extract dimensions based on patterns
    for dim_name, dim_patterns in patterns.items():
        for pattern in dim_patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = float(match.group(1))
                
                # Check for unit conversion
                for unit, factor in unit_conversions.items():
                    if unit in match.group(0):
                        value *= factor
                        break
                
                dimensions[dim_name] = value
                break
    
    # Apply geometry-specific dimension extraction
    if geometry_type == GeometryType.CYLINDER:
        # For cylinders, if only one dimension given, assume it's diameter
        if not dimensions.get('diameter') and any(word in text_lower for word in ['radius', 'r=']):
            radius_match = re.search(r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*radius', text_lower)
            if radius_match:
                dimensions['diameter'] = float(radius_match.group(1)) * 2
    
    elif geometry_type == GeometryType.CUBE:
        # For cubes, look for side length or size
        if not dimensions.get('side_length'):
            # Look for various cube dimension patterns
            cube_patterns = [
                r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*(?:cube|square)',
                r'(\d+\.?\d*)\s*(?:m|meter|metre)?\s*side',
                r'side\s*(?:length)?\s*(?:of|:)?\s*(\d+\.?\d*)\s*(?:m|meter|metre)?',
            ]
            for pattern in cube_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value = float(match.group(1))
                    # Check for unit conversion
                    for unit, factor in unit_conversions.items():
                        if unit in match.group(0):
                            value *= factor
                            break
                    dimensions['side_length'] = value
                    break
    
    return dimensions


def detect_advanced_parameters(prompt: str) -> Dict[str, Any]:
    """Detect advanced user-configurable parameters from the prompt with validation."""
    import re
    prompt_lower = prompt.lower()
    advanced_params = {}
    validation_errors = []
    
    # Detect domain size multiplier
    domain_patterns = [
        r'domain\s+(?:size\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:x|times)',
        r'(\d+(?:\.\d+)?)\s*(?:x|times)\s+(?:the\s+)?(?:object|cylinder|sphere|airfoil|geometry)\s+(?:size|diameter|dimension)',
        r'domain\s+(?:size\s+)?(?:multiplier\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
        r'use\s+(\d+(?:\.\d+)?)\s*(?:x|times)\s+domain',
        r'(\d+(?:\.\d+)?)\s*(?:x|times)\s+larger\s+domain',
        r'domain\s+(\d+(?:\.\d+)?)\s*(?:x|times)\s+(?:the\s+)?(?:object|size)',
        r'with\s+(\d+(?:\.\d+)?)\s*(?:x|times)\s+domain\s+size',
        r'(\d+(?:\.\d+)?)\s*(?:x|times)\s+domain\s+size',
        r'(\d+(?:\.\d+)?)\s*(?:x|times)\s+domain(?:\s|$)'
    ]
    
    for pattern in domain_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            multiplier = float(match.group(1))
            if 1.0 <= multiplier <= 200.0:
                advanced_params["domain_size_multiplier"] = multiplier
                break
            else:
                validation_errors.append({
                    "parameter": "domain_size_multiplier", 
                    "value": multiplier,
                    "min": 1.0,
                    "max": 200.0,
                    "reason": "Domain size multiplier must be reasonable for computational efficiency and accuracy. Values below 1x would cut into the geometry, and values above 200x would waste computational resources unnecessarily."
                })
                break
    
    # Detect Courant number
    courant_patterns = [
        r'courant\s+(?:number\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
        r'cfl\s+(?:number\s+)?(?:of\s+)?(\d+(?:\.\d+)?)',
        r'use\s+courant\s+(?:number\s+)?(\d+(?:\.\d+)?)',
        r'courant\s+(?:number\s+)?(?:=|:|to)\s*(\d+(?:\.\d+)?)',
        r'cfl\s+(?:=|:)\s*(\d+(?:\.\d+)?)',
        r'set\s+courant\s+(?:number\s+)?(?:to\s+)?(\d+(?:\.\d+)?)'
    ]
    
    for pattern in courant_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            courant = float(match.group(1))
            if 0.1 <= courant <= 2.0:
                advanced_params["courant_number"] = courant
                break
            else:
                validation_errors.append({
                    "parameter": "courant_number", 
                    "value": courant,
                    "min": 0.1,
                    "max": 2.0,
                    "reason": "Courant number must be in a stable range. Values below 0.1 lead to unnecessarily small time steps and long simulation times, while values above 2.0 can cause numerical instability and simulation failure."
                })
                break
    
    # Detect minimum time step
    min_dt_patterns = [
        r'minimum\s+time\s+step\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'min\s+(?:time\s+)?step\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'minimum\s+dt\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'min\s+dt\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)'
    ]
    
    for pattern in min_dt_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            min_dt = float(match.group(1))
            if 1e-10 <= min_dt <= 1e-2:
                advanced_params["min_time_step"] = min_dt
                break
            else:
                validation_errors.append({
                    "parameter": "min_time_step", 
                    "value": min_dt,
                    "min": 1e-10,
                    "max": 1e-2,
                    "reason": "Minimum time step must be physically meaningful. Values below 1e-10 seconds are smaller than molecular time scales and computationally impractical, while values above 0.01 seconds are too large for most CFD problems and would miss important physics."
                })
                break
    
    # Detect maximum time step
    max_dt_patterns = [
        r'maximum\s+time\s+step\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'max\s+(?:time\s+)?step\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'maximum\s+dt\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)',
        r'max\s+dt\s+(?:of\s+)?(\d+(?:\.\d+)?(?:e[-+]?\d+)?)'
    ]
    
    for pattern in max_dt_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            max_dt = float(match.group(1))
            if 1e-6 <= max_dt <= 1.0:
                advanced_params["max_time_step"] = max_dt
                break
            else:
                validation_errors.append({
                    "parameter": "max_time_step", 
                    "value": max_dt,
                    "min": 1e-6,
                    "max": 1.0,
                    "reason": "Maximum time step must allow for meaningful time resolution. Values below 1e-6 seconds are unnecessarily restrictive for most problems, while values above 1.0 second are too large for transient CFD simulations and would miss important temporal dynamics."
                })
                break
    
    # Store validation errors if any
    if validation_errors:
        advanced_params["validation_errors"] = validation_errors
    
    return advanced_params


def validate_physical_parameters(parsed_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate physical parameters extracted by OpenAI and return any validation errors."""
    validation_errors = []
    
    # Validate velocity
    velocity = parsed_params.get("velocity")
    if velocity is not None:
        if velocity <= 0:
            validation_errors.append({
                "parameter": "velocity",
                "value": velocity,
                "min": 0.001,
                "max": 1000.0,
                "reason": "Velocity must be positive. Zero or negative velocities are not physically meaningful for flow simulations."
            })
        elif velocity > 1000.0:
            validation_errors.append({
                "parameter": "velocity",
                "value": velocity,
                "min": 0.001,
                "max": 1000.0,
                "reason": "Velocity above 1000 m/s is extremely high and likely an error. For supersonic flows, please specify Mach number instead. Most engineering flows are below 100 m/s."
            })
    
    # Validate Reynolds number
    reynolds_number = parsed_params.get("reynolds_number")
    if reynolds_number is not None:
        if reynolds_number <= 0:
            validation_errors.append({
                "parameter": "reynolds_number",
                "value": reynolds_number,
                "min": 0.1,
                "max": 1e8,
                "reason": "Reynolds number must be positive. It represents the ratio of inertial to viscous forces and cannot be zero or negative."
            })
        elif reynolds_number > 1e8:
            validation_errors.append({
                "parameter": "reynolds_number",
                "value": reynolds_number,
                "min": 0.1,
                "max": 1e8,
                "reason": "Reynolds number above 100 million is extremely high and computationally challenging. Most engineering flows have Re < 10 million. Please verify your input."
            })
    
    # Validate temperature
    temperature = parsed_params.get("temperature")
    if temperature is not None:
        if temperature <= 0:
            validation_errors.append({
                "parameter": "temperature",
                "value": temperature,
                "min": 1.0,
                "max": 5000.0,
                "reason": "Temperature must be positive (in Kelvin). Absolute zero (0 K) and negative temperatures are not physically meaningful for CFD simulations."
            })
        elif temperature > 5000.0:
            validation_errors.append({
                "parameter": "temperature",
                "value": temperature,
                "min": 1.0,
                "max": 5000.0,
                "reason": "Temperature above 5000 K is extremely high (hotter than most flames). Most engineering applications are below 1500 K. Please verify the temperature is in Kelvin, not Celsius."
            })
    
    # Validate pressure
    pressure = parsed_params.get("pressure")
    if pressure is not None:
        if pressure < 0:
            validation_errors.append({
                "parameter": "pressure",
                "value": pressure,
                "min": 0.0,
                "max": 1e8,
                "reason": "Pressure cannot be negative (assuming absolute pressure). Use gauge pressure with caution, and verify your pressure reference."
            })
        elif pressure > 1e8:  # 100 MPa
            validation_errors.append({
                "parameter": "pressure",
                "value": pressure,
                "min": 0.0,
                "max": 1e8,
                "reason": "Pressure above 100 MPa is extremely high. Most engineering applications are below 10 MPa. Please verify the pressure units (Pa, not kPa or MPa)."
            })
    
    # Validate density
    density = parsed_params.get("density")
    if density is not None:
        if density <= 0:
            validation_errors.append({
                "parameter": "density",
                "value": density,
                "min": 0.001,
                "max": 20000.0,
                "reason": "Density must be positive. Zero or negative density is not physically meaningful."
            })
        elif density > 20000.0:  # Denser than most metals
            validation_errors.append({
                "parameter": "density",
                "value": density,
                "min": 0.001,
                "max": 20000.0,
                "reason": "Density above 20,000 kg/m³ is extremely high (denser than most metals). Typical fluids: air ~1.2, water ~1000, mercury ~13,500 kg/m³. Please verify your units."
            })
    
    # Validate viscosity
    viscosity = parsed_params.get("viscosity")
    if viscosity is not None:
        if viscosity <= 0:
            validation_errors.append({
                "parameter": "viscosity",
                "value": viscosity,
                "min": 1e-8,
                "max": 1e3,
                "reason": "Viscosity must be positive. Zero or negative viscosity is not physically meaningful."
            })
        elif viscosity > 1e3:  # Very high viscosity
            validation_errors.append({
                "parameter": "viscosity",
                "value": viscosity,
                "min": 1e-8,
                "max": 1e3,
                "reason": "Viscosity above 1000 Pa·s is extremely high (thicker than honey). Typical values: air ~1.8e-5, water ~1e-3, oil ~0.1 Pa·s. Please verify your units."
            })
    
    # Validate simulation time
    simulation_time = parsed_params.get("simulation_time")
    if simulation_time is not None:
        if simulation_time <= 0:
            validation_errors.append({
                "parameter": "simulation_time",
                "value": simulation_time,
                "min": 1e-6,
                "max": 86400.0,
                "reason": "Simulation time must be positive. Zero or negative simulation time is not meaningful."
            })
        elif simulation_time > 86400.0:  # More than 24 hours
            validation_errors.append({
                "parameter": "simulation_time",
                "value": simulation_time,
                "min": 1e-6,
                "max": 86400.0,
                "reason": "Simulation time above 24 hours (86,400 seconds) is extremely long and may take prohibitively long to compute. Most CFD simulations are seconds to minutes. Please verify your time units."
            })
    
    return validation_errors


def format_validation_errors(validation_errors: List[Dict[str, Any]]) -> str:
    """Format validation errors into a user-friendly error message with next steps."""
    if not validation_errors:
        return ""
    
    error_lines = ["🚨 PARAMETER VALIDATION FAILED"]
    error_lines.append("=" * 50)
    error_lines.append("")
    error_lines.append("The following parameter values are outside acceptable ranges:")
    error_lines.append("")
    
    for i, error in enumerate(validation_errors, 1):
        param = error["parameter"]
        value = error["value"]
        min_val = error["min"]
        max_val = error["max"]
        reason = error["reason"]
        
        # Format parameter name nicely
        param_display = param.replace("_", " ").title()
        
        # Format the value with appropriate precision
        if isinstance(value, float):
            if value >= 1e6 or value <= 1e-6:
                value_str = f"{value:.2e}"
            else:
                value_str = f"{value:.6g}"
        else:
            value_str = str(value)
        
        # Format min/max values
        if isinstance(min_val, float):
            if min_val >= 1e6 or min_val <= 1e-6:
                min_str = f"{min_val:.2e}"
            else:
                min_str = f"{min_val:.6g}"
        else:
            min_str = str(min_val)
            
        if isinstance(max_val, float):
            if max_val >= 1e6 or max_val <= 1e-6:
                max_str = f"{max_val:.2e}"
            else:
                max_str = f"{max_val:.6g}"
        else:
            max_str = str(max_val)
        
        error_lines.append(f"❌ {i}. {param_display}")
        error_lines.append(f"    Your value: {value_str}")
        error_lines.append(f"    Acceptable range: {min_str} to {max_str}")
        error_lines.append(f"    Why this matters: {reason}")
        error_lines.append("")
    
    error_lines.append("🤔 What would you like to do?")
    error_lines.append("")
    error_lines.append("   1️⃣  Modify your prompt with valid parameter values")
    error_lines.append("   2️⃣  Use the system defaults (recommended)")
    error_lines.append("   3️⃣  Override validation and proceed anyway (not recommended)")
    error_lines.append("")
    error_lines.append("💡 For option 1, please update your prompt with values in the acceptable ranges.")
    error_lines.append("   For option 2, remove the invalid parameters from your prompt.")
    error_lines.append("   For option 3, add '--force-validation' to your command (use with caution).")
    
    return "\n".join(error_lines)


def infer_flow_context(text: str, geometry_type: GeometryType, user_domain_multiplier: Optional[float] = None) -> FlowContext:
    """Infer flow context from text with optional user-specified domain multiplier."""
    text_lower = text.lower()
    
    # Determine if it's external or internal flow
    if any(keyword in text_lower for keyword in ["around", "over", "past", "external", "cylinder", "sphere", "airfoil", "cube"]):
        if not any(keyword in text_lower for keyword in ["through", "in", "inside", "internal", "pipe", "channel", "duct"]):
            is_external = True
    elif any(keyword in text_lower for keyword in ["through", "in", "inside", "internal", "pipe", "channel", "duct"]):
        is_external = False
    else:
        # Default based on geometry type
        if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE, GeometryType.AIRFOIL, GeometryType.CUBE]:
            is_external = True
        else:
            is_external = False  # Default to internal flow for pipes/channels
    
    # Determine domain type and size
    if is_external:
        domain_type = "unbounded"
        # Use user-specified domain multiplier if provided, otherwise use defaults
        if user_domain_multiplier is not None:
            domain_size_multiplier = user_domain_multiplier
        else:
            # Default domain size based on geometry type
            if geometry_type == GeometryType.CYLINDER:
                domain_size_multiplier = 20.0  # 20x diameter typical for cylinder
            elif geometry_type == GeometryType.AIRFOIL:
                domain_size_multiplier = 30.0  # 30x chord for airfoil
            elif geometry_type == GeometryType.SPHERE:
                domain_size_multiplier = 20.0  # 20x diameter for sphere
            elif geometry_type == GeometryType.CUBE:
                domain_size_multiplier = 20.0  # 20x side length for cube
            else:
                domain_size_multiplier = 10.0  # Default
    else:
        domain_type = "channel"
        domain_size_multiplier = 1.0  # No expansion for internal flow
    
    return FlowContext(
        is_external_flow=is_external,
        domain_type=domain_type,
        domain_size_multiplier=domain_size_multiplier
    )


def apply_intelligent_defaults(geometry_type: GeometryType, dimensions: Dict[str, float], 
                             flow_context: FlowContext, reynolds_number: Optional[float]) -> Dict[str, float]:
    """Apply intelligent defaults for missing dimensions based on geometry and flow type."""
    
    # Remove None values from dimensions dictionary
    dimensions = {k: v for k, v in dimensions.items() if v is not None}
    
    # Geometry-specific intelligent defaults
    if geometry_type == GeometryType.CYLINDER:
        if 'diameter' not in dimensions or dimensions.get('diameter') is None:
            if reynolds_number and reynolds_number < 1000:
                dimensions['diameter'] = 0.01  # Small cylinder for low Re
            elif reynolds_number and reynolds_number > 100000:
                dimensions['diameter'] = 1.0   # Large cylinder for high Re
            else:
                dimensions['diameter'] = 0.1   # Default 10cm
        
        if 'length' not in dimensions:
            if flow_context.is_external_flow:
                # For 2D external flow, use thin slice
                dimensions['length'] = dimensions['diameter'] * 0.1
            else:
                # For internal flow (unlikely for cylinder), use longer length
                dimensions['length'] = dimensions['diameter'] * 10
    
    elif geometry_type == GeometryType.AIRFOIL:
        if 'chord' not in dimensions or dimensions.get('chord') is None:
            dimensions['chord'] = 0.1  # Default 10cm chord
        if 'span' not in dimensions or dimensions.get('span') is None:
            # For 2D simulation, use thin span
            dimensions['span'] = dimensions.get('chord', 0.1) * 0.1
        if 'thickness' not in dimensions or dimensions.get('thickness') is None:
            # Typical airfoil thickness ratio
            dimensions['thickness'] = dimensions.get('chord', 0.1) * 0.12
    
    elif geometry_type == GeometryType.PIPE:
        if 'diameter' not in dimensions or dimensions.get('diameter') is None:
            dimensions['diameter'] = 0.05  # Default 5cm pipe
        if 'length' not in dimensions or dimensions.get('length') is None:
            # Ensure sufficient length for flow development
            dimensions['length'] = max(dimensions.get('diameter', 0.05) * 20, 1.0)
    
    elif geometry_type == GeometryType.CHANNEL:
        if 'height' not in dimensions or dimensions.get('height') is None:
            dimensions['height'] = 0.1  # Default 10cm height
        if 'width' not in dimensions or dimensions.get('width') is None:
            # Aspect ratio considerations
            if 'height' in dimensions:
                dimensions['width'] = dimensions['height'] * 2  # 2:1 aspect ratio
            else:
                dimensions['width'] = 0.2
        if 'length' not in dimensions or dimensions.get('length') is None:
            dimensions['length'] = max(dimensions.get('height', 0.1) * 10, 1.0)
    
    elif geometry_type == GeometryType.SPHERE:
        if 'diameter' not in dimensions or dimensions.get('diameter') is None:
            dimensions['diameter'] = 0.1  # Default 10cm sphere
    
    elif geometry_type == GeometryType.CUBE:
        if 'side_length' not in dimensions or dimensions.get('side_length') is None:
            if reynolds_number and reynolds_number < 1000:
                dimensions['side_length'] = 0.01  # Small cube for low Re
            elif reynolds_number and reynolds_number > 100000:
                dimensions['side_length'] = 1.0   # Large cube for high Re
            else:
                dimensions['side_length'] = 0.1   # Default 10cm cube
    
    return dimensions


def detect_boundary_conditions(prompt: str) -> Dict[str, Any]:
    """Detect boundary condition specifications from the prompt."""
    conditions = {}
    prompt_lower = prompt.lower()
    
    # Inlet velocity patterns
    velocity_pattern = r'(?:inlet\s+)?velocity\s*[:=]?\s*([\d.]+)\s*(?:m/s|meter[s]?/second)?'
    if match := re.search(velocity_pattern, prompt_lower):
        conditions["inlet_velocity"] = float(match.group(1))
    
    # Pressure patterns
    pressure_pattern = r'(?:outlet\s+)?pressure\s*[:=]?\s*([\d.]+)\s*(?:pa|pascal)?'
    if match := re.search(pressure_pattern, prompt_lower):
        conditions["outlet_pressure"] = float(match.group(1))
    
    # Temperature patterns
    temp_pattern = r'temperature\s*[:=]?\s*([\d.]+)\s*(?:k|kelvin|c|celsius)?'
    if match := re.search(temp_pattern, prompt_lower):
        temp = float(match.group(1))
        # Convert Celsius to Kelvin if needed
        if 'c' in match.group(0).lower() and temp < 100:  # Likely Celsius
            temp += 273.15
        conditions["temperature"] = temp
    
    return conditions


def detect_rotation_request(prompt: str) -> Dict[str, Any]:
    """Detect rotation specifications from the prompt."""
    import re
    rotation_info = {
        "rotate": False,
        "rotation_axis": None,
        "rotation_angle": None,
        "rotation_center": None
    }
    
    prompt_lower = prompt.lower()
    
    # Check for rotation keywords
    rotation_keywords = [
        r"\brotate\b", r"\brotation\b", r"\bturn\b", r"\bangle\b", 
        r"\borientation\b", r"\byaw\b", r"\bpitch\b", r"\broll\b"
    ]
    
    if not any(re.search(keyword, prompt_lower) for keyword in rotation_keywords):
        return rotation_info
    
    # Detect rotation angle
    angle_patterns = [
        r'rotate\s*(?:by\s*)?([-+]?\d+(?:\.\d+)?)\s*(?:degree|deg|°)',
        r'turn\s*(?:by\s*)?([-+]?\d+(?:\.\d+)?)\s*(?:degree|deg|°)',
        r'([-+]?\d+(?:\.\d+)?)\s*(?:degree|deg|°)\s*rotation',
        r'angle\s*[:=]?\s*([-+]?\d+(?:\.\d+)?)\s*(?:degree|deg|°)?'
    ]
    
    for pattern in angle_patterns:
        if match := re.search(pattern, prompt_lower):
            rotation_info["rotate"] = True
            rotation_info["rotation_angle"] = float(match.group(1))
            break
    
    # Detect rotation axis
    if re.search(r'\b(?:around|about)\s*x[-\s]?axis\b', prompt_lower):
        rotation_info["rotation_axis"] = "x"
    elif re.search(r'\b(?:around|about)\s*y[-\s]?axis\b', prompt_lower):
        rotation_info["rotation_axis"] = "y"
    elif re.search(r'\b(?:around|about)\s*z[-\s]?axis\b', prompt_lower):
        rotation_info["rotation_axis"] = "z"
    elif re.search(r'\byaw\b', prompt_lower):
        rotation_info["rotation_axis"] = "z"  # Yaw is rotation around Z
    elif re.search(r'\bpitch\b', prompt_lower):
        rotation_info["rotation_axis"] = "y"  # Pitch is rotation around Y
    elif re.search(r'\broll\b', prompt_lower):
        rotation_info["rotation_axis"] = "x"  # Roll is rotation around X
    
    # If rotation detected but no axis specified, default to Z (most common for vehicles)
    if rotation_info["rotate"] and not rotation_info["rotation_axis"]:
        rotation_info["rotation_axis"] = "z"
    
    return rotation_info


def detect_multiphase_flow(prompt: str) -> Dict[str, Any]:
    """Detect multiphase flow indicators from the prompt using word boundaries."""
    import re
    prompt_lower = prompt.lower()
    multiphase_info = {
        "is_multiphase": False,
        "phases": [],
        "free_surface": False
    }
    
    # Keywords that indicate multiphase flow with word boundaries
    multiphase_keywords = [
        r"\bwater\b", r"\bliquid\b", r"\boil\b", r"\bgas\b", r"\binterface\b",
        r"\bfree surface\b", r"\bvof\b", r"\bvolume of fluid\b", r"\bmultiphase\b",
        r"\bdam break\b", r"\bwave\b", r"\bdroplet\b", r"\bbubble\b", r"\bsplash\b",
        r"\bfilling\b", r"\bdraining\b", r"\bsloshing\b", r"\bmarine\b", r"\bnaval\b",
        r"\btwo-phase\b", r"\btwo phase\b"
    ]
    
    # Check for multiphase keywords
    found_keywords = []
    for keyword in multiphase_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(keyword)
    
    # Identify specific phases mentioned using word boundaries
    phases = []
    # Water/liquid detection
    if any(re.search(pattern, prompt_lower) for pattern in [r"\bwater\b", r"\bliquid\b"]):
        phases.append("water")
    
    # Air/gas detection - special handling for "air" to avoid false positives
    air_detected = False
    if re.search(r"\bair\b", prompt_lower):
        # Check if it's in context of multiphase flow (with other fluids)
        other_fluids = [r"\bwater\b", r"water", r"\bliquid\b", r"liquid", r"\boil\b"]
        if any(re.search(fluid, prompt_lower) for fluid in other_fluids):
            air_detected = True
        # Check for explicit multiphase contexts
        multiphase_contexts = [
            r"\bair.*water\b", r"\bwater.*air\b", r"water.*air", r"air.*water",
            r"\btwo.*phase\b", r"\bfree surface\b", r"\bdam break\b", r"\bwave\b"
        ]
        if any(re.search(context, prompt_lower) for context in multiphase_contexts):
            air_detected = True
    
    # Gas detection (broader than air)
    if re.search(r"\bgas\b", prompt_lower) or air_detected:
        phases.append("air")
    
    # Oil detection
    if re.search(r"\boil\b", prompt_lower):
        phases.append("oil")
    
    # Check for free surface indicators
    free_surface_keywords = [r"\bfree surface\b", r"\bdam break\b", r"\bwave\b", r"\bsloshing\b", r"\binterface\b"]
    if any(re.search(keyword, prompt_lower) for keyword in free_surface_keywords):
        multiphase_info["free_surface"] = True
    
    # Determine if this is multiphase
    explicit_multiphase = any(re.search(pattern, prompt_lower) for pattern in [r"\bmultiphase\b", r"\btwo-phase\b", r"\btwo phase\b", r"\bvof\b"])
    
    if len(phases) >= 2 or explicit_multiphase or multiphase_info["free_surface"]:
        multiphase_info["is_multiphase"] = True
        if not phases:  # Default to water-air if no specific phases mentioned
            phases = ["water", "air"]
    
    multiphase_info["phases"] = phases
    
    return multiphase_info


def nl_interpreter_agent(state: CFDState) -> CFDState:
    """
    Natural Language Interpreter Agent.
    
    Parses user's natural language prompt into structured CFD parameters
    using OpenAI GPT-4 with structured output parsing.
    """
    try:
        if state["verbose"]:
            logger.info(f"NL Interpreter: Processing prompt: {state['user_prompt']}")
            if state.get("stl_file"):
                logger.info(f"NL Interpreter: STL file provided: {state['stl_file']}")
        
        # Get API key from config
        from .config import get_settings
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Create LLM with structured output
        llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",  # Use mini for faster response during development
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=2000
        )
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=CFDParameters)
        
        # Modify prompt template to handle STL files
        stl_instruction = ""
        if state.get("stl_file"):
            stl_instruction = f"""
IMPORTANT: The user is providing an STL file for custom geometry: {state['stl_file']}
- Set geometry_type to "custom" 
- Set is_custom_geometry to true
- Set is_external_flow to true (STL files are typically external flow around objects)
- Set domain_type to "unbounded"
- Set domain_size_multiplier to 20.0 (reasonable default for external flow)
- Do not try to extract specific geometry dimensions - the STL file defines the geometry
- Focus on extracting flow parameters, boundary conditions, and simulation settings from the prompt
"""
        
        # Create prompt template with enhanced instructions
        prompt = ChatPromptTemplate.from_template("""
You are an expert CFD engineer. Parse the following natural language description of a fluid dynamics problem into structured parameters.

{stl_instruction}

Extract all relevant information including:
- Geometry type and dimensions (extract numerical values with units)
- Flow context (is it flow AROUND an object or THROUGH a channel/pipe?)
- Flow conditions (velocity, pressure, temperature)
- Fluid properties (density, viscosity)
- Boundary conditions
- Analysis type (steady/unsteady, laminar/turbulent)
- Solver preferences
- Mesh preferences
- Advanced parameters (domain size, time stepping controls)

IMPORTANT RULES:
1. For "flow around" objects (cylinder, sphere, airfoil), set is_external_flow=true and domain_type="unbounded"
2. For "flow through" or "flow in" objects (pipe, channel), set is_external_flow=false and domain_type="channel"
3. If neither is specified, use these defaults:
   - Cylinder, Sphere, Airfoil → external flow (around object)
   - Pipe, Channel → internal flow (through object)
4. Extract ALL numerical dimensions mentioned (with unit conversion to meters)
5. For external flow, set domain_size_multiplier appropriately (typically 20-30x object size)
6. DEFAULT TO UNSTEADY (TRANSIENT) ANALYSIS unless the user explicitly mentions "steady", "steady-state", or "stationary"
7. Extract advanced parameters if specified by user (domain size multiplier, Courant number, time step limits)

Problem Description: {user_prompt}

Examples of dimension extraction:
- "10mm diameter cylinder" → diameter: 0.01 (converted to meters)
- "5 inch pipe" → diameter: 0.127 (converted to meters)
- "flow around a cylinder" → is_external_flow: true, domain_type: "unbounded"
- "flow through a pipe" → is_external_flow: false, domain_type: "channel"

Examples of analysis type extraction:
- "flow around a cylinder" → analysis_type: UNSTEADY (default)
- "steady flow around a cylinder" → analysis_type: STEADY (explicitly mentioned)
- "steady-state simulation" → analysis_type: STEADY (explicitly mentioned)
- "turbulent flow" → analysis_type: UNSTEADY (default)
- "transient flow" → analysis_type: UNSTEADY (explicitly mentioned)

Examples of simulation time extraction:
- "simulate for 5 seconds" → simulation_time: 5.0
- "run for 0.5s" → simulation_time: 0.5
- "10 second simulation" → simulation_time: 10.0
- No time specified → simulation_time: null (will default to 1.0s)

Examples of mesh resolution:
- "coarse mesh" → mesh_resolution: "coarse"
- "fine resolution" → mesh_resolution: "fine"
- No mesh specified → mesh_resolution: null (will default to "medium")

Examples of advanced parameter extraction:
- "use 50x domain size" → domain_size_multiplier: 50.0
- "domain 10 times the cylinder diameter" → domain_size_multiplier: 10.0
- "use Courant number 0.8" → courant_number: 0.8
- "CFL of 0.5" → courant_number: 0.5
- "minimum time step 1e-6" → min_time_step: 1e-6
- "max time step 0.001" → max_time_step: 0.001
- No advanced parameters specified → all null (will use defaults)

{format_instructions}

Return valid JSON that matches the schema exactly.
""")
        
        # Create chain
        chain = prompt | llm | parser
        
        # Process the user prompt
        result = chain.invoke({
            "user_prompt": state["user_prompt"],
            "stl_instruction": stl_instruction,
            "format_instructions": parser.get_format_instructions()
        })
        
        # Convert to dictionary
        parsed_params = result.dict()
        
        # Handle STL file-specific logic
        if state.get("stl_file"):
            # Force custom geometry settings for STL files
            parsed_params["geometry_type"] = GeometryType.CUSTOM
            parsed_params["is_custom_geometry"] = True
            parsed_params["geometry_dimensions"] = {"is_3d": True}  # Mark as 3D
            
            # Set appropriate flow context for STL files (typically external flow)
            parsed_params["flow_context"] = {
                "is_external_flow": True,
                "domain_type": "unbounded",
                "domain_size_multiplier": 20.0
            }
            
            if state["verbose"]:
                logger.info("NL Interpreter: STL file detected, configured for custom 3D geometry")
        else:
            # Extract dimensions from text (as backup/enhancement) for non-STL cases
            text_dimensions = extract_dimensions_from_text(state["user_prompt"], parsed_params["geometry_type"])
            
            # Merge extracted dimensions with LLM-parsed dimensions
            for key, value in text_dimensions.items():
                if key not in parsed_params["geometry_dimensions"] or parsed_params["geometry_dimensions"][key] is None:
                    parsed_params["geometry_dimensions"][key] = value
            
            # Apply intelligent defaults for missing dimensions
            parsed_params["geometry_dimensions"] = apply_intelligent_defaults(
                parsed_params["geometry_type"],
                parsed_params["geometry_dimensions"],
                FlowContext(**parsed_params["flow_context"]),
                parsed_params.get("reynolds_number")
            )
            
            # For non-STL cases, ensure is_custom_geometry is False
            parsed_params["is_custom_geometry"] = False
        
        # Infer flow context if not properly set (for non-STL cases)
        if not state.get("stl_file") and ("flow_context" not in parsed_params or parsed_params["flow_context"] is None):
            user_domain_multiplier = parsed_params.get("domain_size_multiplier")
            parsed_params["flow_context"] = infer_flow_context(
                state["user_prompt"], 
                parsed_params["geometry_type"], 
                user_domain_multiplier
            ).dict()
        elif not state.get("stl_file") and parsed_params.get("domain_size_multiplier") is not None:
            # Update existing flow context with user-specified domain multiplier
            flow_context = FlowContext(**parsed_params["flow_context"])
            flow_context.domain_size_multiplier = parsed_params["domain_size_multiplier"]
            parsed_params["flow_context"] = flow_context.dict()
        
        # Extract geometry information with flow context
        geometry_info = {
            "type": parsed_params["geometry_type"],
            "dimensions": parsed_params["geometry_dimensions"],
            "mesh_resolution": parsed_params.get("mesh_resolution", "medium"),
            "flow_context": parsed_params["flow_context"],
            "is_custom_geometry": parsed_params.get("is_custom_geometry", False),
            "stl_file": state.get("stl_file")  # Pass STL file path to geometry info
        }
        
        # Log results if verbose
        if state["verbose"]:
            logger.info(f"NL Interpreter: Extracted geometry: {geometry_info}")
            logger.info(f"NL Interpreter: Flow context: {parsed_params['flow_context']}")
            logger.info(f"NL Interpreter: Flow type: {parsed_params['flow_type']}")
            logger.info(f"NL Interpreter: Analysis type: {parsed_params['analysis_type']}")
            logger.info(f"NL Interpreter: Custom geometry: {parsed_params.get('is_custom_geometry', False)}")
        
        # Calculate Reynolds number if not provided
        if not parsed_params.get("reynolds_number") and parsed_params.get("velocity"):
            reynolds_number = calculate_reynolds_number(parsed_params, geometry_info)
            if reynolds_number:
                parsed_params["reynolds_number"] = reynolds_number
        
        # Set default fluid properties if not specified
        parsed_params = set_default_fluid_properties(parsed_params)
        
        # Detect multiphase flow indicators
        multiphase_info = detect_multiphase_flow(state["user_prompt"])
        
        # Merge multiphase information into parsed parameters
        parsed_params["is_multiphase"] = multiphase_info["is_multiphase"]
        parsed_params["phases"] = multiphase_info["phases"]
        parsed_params["free_surface"] = multiphase_info["free_surface"]
        
        # Detect boundary conditions from prompt
        boundary_conditions = detect_boundary_conditions(state["user_prompt"])
        for key, value in boundary_conditions.items():
            if key not in parsed_params or parsed_params[key] is None:
                parsed_params[key] = value
        
        # Detect rotation request from prompt
        rotation_info = detect_rotation_request(state["user_prompt"])
        if rotation_info["rotate"]:
            parsed_params["rotation_info"] = rotation_info
            if state["verbose"]:
                logger.info(f"NL Interpreter: Detected rotation request: {rotation_info}")
        
        # Detect advanced parameters from prompt and check for validation errors
        advanced_params = detect_advanced_parameters(state["user_prompt"])
        all_validation_errors = []
        
        # Check for validation errors from advanced parameters
        if "validation_errors" in advanced_params:
            all_validation_errors.extend(advanced_params["validation_errors"])
            del advanced_params["validation_errors"]  # Remove from params to avoid adding to parsed_params
        
        # Add valid advanced parameters
        for key, value in advanced_params.items():
            if key not in parsed_params or parsed_params[key] is None:
                parsed_params[key] = value
                if state["verbose"]:
                    logger.info(f"NL Interpreter: User-specified {key}: {value}")
        
        # Validate physical parameters extracted by OpenAI
        physical_validation_errors = validate_physical_parameters(parsed_params)
        all_validation_errors.extend(physical_validation_errors)
        
        # If there are validation errors, check if user wants to override
        if all_validation_errors:
            if state.get("force_validation", False):
                # User has chosen to override validation, proceed with warnings
                warning_message = f"⚠️  VALIDATION OVERRIDE: Proceeding with {len(all_validation_errors)} out-of-range parameter(s). This may lead to computational issues or simulation failure."
                logger.warning(f"NL Interpreter: Parameter validation overridden by user: {warning_message}")
                # Add detailed validation warnings but don't stop execution
                for error in all_validation_errors:
                    warning_detail = f"Parameter '{error['parameter']}' = {error['value']} (acceptable range: {error['min']} to {error['max']})"
                    logger.warning(f"NL Interpreter: {warning_detail}")
                
                return {
                    **state,
                    "warnings": state["warnings"] + [warning_message],
                    "parsed_parameters": parsed_params,
                    "geometry_info": geometry_info,
                    "current_step": CFDStep.NL_INTERPRETATION
                }
            else:
                # Normal validation failure - stop execution with helpful error message
                error_message = format_validation_errors(all_validation_errors)
                logger.error(f"NL Interpreter: Parameter validation failed: {error_message}")
                return {
                    **state,
                    "errors": state["errors"] + [error_message],
                    "current_step": CFDStep.ERROR
                }
        
        return {
            **state,
            "parsed_parameters": parsed_params,
            "geometry_info": geometry_info,
            "original_prompt": state["user_prompt"],  # Pass original prompt for AI solver selection
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"NL Interpreter error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Natural language interpretation failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def calculate_reynolds_number(params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Optional[float]:
    """Calculate Reynolds number from available parameters."""
    try:
        velocity = params.get("velocity")
        density = params.get("density", 1.225)  # Air at sea level
        viscosity = params.get("viscosity", 1.81e-5)  # Air at 20°C
        
        # Handle None values
        if density is None:
            density = 1.225
        if viscosity is None:
            viscosity = 1.81e-5
        
        if not velocity or velocity is None:
            return None
        
        # Get characteristic length based on geometry type
        characteristic_length = get_characteristic_length(geometry_info)
        
        if characteristic_length and characteristic_length > 0:
            reynolds_number = (density * velocity * characteristic_length) / viscosity
            logger.info(f"Calculated Reynolds number: {reynolds_number:.0f}")
            return reynolds_number
        
        return None
        
    except Exception as e:
        logger.warning(f"Could not calculate Reynolds number: {e}")
        return None


def get_characteristic_length(geometry_info: Dict[str, Any]) -> Optional[float]:
    """Get characteristic length for Reynolds number calculation."""
    geometry_type = geometry_info.get("type")
    dimensions = geometry_info.get("dimensions", {})
    
    if geometry_type == GeometryType.CYLINDER:
        return dimensions.get("diameter", 0.1)  # Default 0.1m diameter
    elif geometry_type == GeometryType.AIRFOIL:
        return dimensions.get("chord", 0.1)  # Default 0.1m chord
    elif geometry_type == GeometryType.PIPE:
        return dimensions.get("diameter", 0.05)  # Default 0.05m diameter
    elif geometry_type == GeometryType.SPHERE:
        return dimensions.get("diameter", 0.1)  # Default 0.1m diameter
    elif geometry_type == GeometryType.CUBE:
        return dimensions.get("side_length", 0.1)  # Default 0.1m side length
    elif geometry_type == GeometryType.CHANNEL:
        return dimensions.get("height", 0.1)  # Default 0.1m height
    else:
        return 0.1  # Default characteristic length


def set_default_fluid_properties(params: Dict[str, Any]) -> Dict[str, Any]:
    """Set default fluid properties if not specified."""
    defaults = {
        "density": 1.225,  # Air at sea level (kg/m³)
        "viscosity": 1.81e-5,  # Air at 20°C (Pa·s)
        "temperature": 293.15,  # 20°C in Kelvin
        "pressure": 101325,  # Atmospheric pressure (Pa)
    }
    
    for key, value in defaults.items():
        if key not in params or params[key] is None:
            params[key] = value
    
    return params


def create_default_boundary_conditions(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create default boundary conditions based on extracted parameters."""
    boundary_conditions = {
        "inlet": {
            "type": "fixedValue",
            "velocity": params.get("velocity", 1.0),
            "pressure": "zeroGradient",
            "turbulenceIntensity": 0.05,
            "turbulenceLengthScale": 0.01
        },
        "outlet": {
            "type": "zeroGradient",
            "velocity": "zeroGradient",
            "pressure": "fixedValue",
            "pressure_value": 0.0
        },
        "walls": {
            "type": "noSlip",
            "velocity": "fixedValue",
            "velocity_value": [0, 0, 0]
        }
    }
    
    return boundary_conditions 
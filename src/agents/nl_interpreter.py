"""Natural Language Interpreter Agent - Parses user prompts into structured CFD parameters."""

import json
import re
from typing import Dict, Any, Optional, Tuple, List
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType
from .stl_processor import validate_stl_file, process_stl_file


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


def infer_flow_context(text: str, geometry_type: GeometryType) -> FlowContext:
    """Infer whether flow is external (around object) or internal (through object)."""
    text_lower = text.lower()
    
    # Keywords indicating external flow
    external_keywords = ['around', 'over', 'past', 'across', 'external', 'bluff body', 
                        'drag', 'lift', 'wake', 'vortex shedding', 'aerodynamic']
    
    # Keywords indicating internal flow
    internal_keywords = ['through', 'in', 'inside', 'internal', 'pipe flow', 'channel flow',
                        'duct', 'pressure drop', 'friction']
    
    # Count keyword matches
    external_score = sum(1 for keyword in external_keywords if keyword in text_lower)
    internal_score = sum(1 for keyword in internal_keywords if keyword in text_lower)
    
    # Geometry-specific defaults
    if external_score > internal_score:
        is_external = True
    elif internal_score > external_score:
        is_external = False
    else:
        # Use geometry-based defaults
        if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE, GeometryType.AIRFOIL, GeometryType.CUBE]:
            is_external = True  # Default to external flow for these geometries
        else:
            is_external = False  # Default to internal flow for pipes/channels
    
    # Determine domain type and size
    if is_external:
        domain_type = "unbounded"
        # Domain size based on geometry type
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
    
    Parses user's natural language prompt into structured CFD parameters,
    including geometry information, flow conditions, and analysis requirements.
    Now supports STL file integration for custom geometries.
    """
    try:
        if state["verbose"]:
            logger.info("NL Interpreter: Starting natural language interpretation")
        
        user_prompt = state["user_prompt"]
        geometry_source = state["geometry_source"]
        
        # Handle STL file if present
        if geometry_source == "stl" and state["stl_file_path"]:
            return process_stl_workflow(state, user_prompt)
        else:
            return process_parametric_workflow(state, user_prompt)
            
    except Exception as e:
        logger.error(f"NL Interpreter error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Natural language interpretation failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def process_stl_workflow(state: CFDState, user_prompt: str) -> CFDState:
    """Process workflow with STL file geometry."""
    if state["verbose"]:
        logger.info(f"Processing STL workflow with file: {state['stl_file_path']}")
    
    # Validate STL file
    is_valid, warnings = validate_stl_file(state["stl_file_path"])
    
    if not is_valid:
        error_msg = f"STL file validation failed: {'; '.join(warnings)}"
        logger.error(error_msg)
        return {
            **state,
            "errors": state["errors"] + [error_msg],
            "current_step": CFDStep.ERROR
        }
    
    # Process STL geometry
    stl_geometry = process_stl_file(state["stl_file_path"])
    
    if not stl_geometry:
        error_msg = "Failed to process STL geometry"
        logger.error(error_msg)
        return {
            **state,
            "errors": state["errors"] + [error_msg],
            "current_step": CFDStep.ERROR
        }
    
    # Parse flow parameters from prompt (same as parametric workflow)
    parsed_params = parse_flow_parameters(user_prompt)
    
    # Determine flow context for STL geometry
    flow_context = determine_stl_flow_context(user_prompt, stl_geometry)
    
    # Create geometry info based on STL
    geometry_info = create_stl_geometry_info(stl_geometry, flow_context)
    
    # Add STL-specific warnings
    all_warnings = state["warnings"] + warnings
    if stl_geometry.get("estimated_cells", 0) > 500000:
        all_warnings.append("STL geometry may result in a large mesh - consider using coarser settings")
    
    if state["verbose"]:
        logger.info(f"STL Interpreter: Processed {stl_geometry['num_triangles']} triangles")
        logger.info(f"STL Interpreter: Characteristic length: {stl_geometry['characteristic_length']:.3f}m")
        logger.info(f"STL Interpreter: Flow type: {parsed_params.get('flow_type', 'unknown')}")
    
    return {
        **state,
        "parsed_parameters": parsed_params,
        "geometry_info": geometry_info,
        "stl_geometry": stl_geometry,
        "warnings": all_warnings,
        "errors": []
    }


def process_parametric_workflow(state: CFDState, user_prompt: str) -> CFDState:
    """Process workflow with parametric geometry (original functionality)."""
    if state["verbose"]:
        logger.info("Processing parametric geometry workflow")
    
    # Parse the user prompt
    parsed_params = parse_user_prompt(user_prompt)
    
    # Extract geometry information
    geometry_info = extract_geometry_info(parsed_params, user_prompt)
    
    # Validate parsed parameters
    validation_result = validate_parsed_parameters(parsed_params, geometry_info)
    if not validation_result["valid"]:
        logger.warning(f"Parameter validation issues: {validation_result['warnings']}")
        return {
            **state,
            "errors": state["errors"] + validation_result["errors"],
            "warnings": state["warnings"] + validation_result["warnings"]
        }
    
    if state["verbose"]:
        logger.info(f"NL Interpreter: Geometry type = {geometry_info.get('type', 'unknown')}")
        logger.info(f"NL Interpreter: Flow type = {parsed_params.get('flow_type', 'unknown')}")
        logger.info(f"NL Interpreter: Analysis type = {parsed_params.get('analysis_type', 'unknown')}")
    
    return {
        **state,
        "parsed_parameters": parsed_params,
        "geometry_info": geometry_info,
        "warnings": state["warnings"] + validation_result["warnings"],
        "errors": []
    }


def determine_stl_flow_context(user_prompt: str, stl_geometry: Dict[str, Any]) -> Dict[str, Any]:
    """Determine flow context for STL geometry based on prompt."""
    prompt_lower = user_prompt.lower()
    
    # Determine if this is internal or external flow
    is_external_flow = True  # Default assumption
    
    # Keywords that suggest internal flow
    internal_keywords = [
        "through", "inside", "internal", "pipe", "duct", "channel", 
        "tube", "passage", "cavity", "inlet", "flow through"
    ]
    
    if any(keyword in prompt_lower for keyword in internal_keywords):
        is_external_flow = False
    
    # Keywords that suggest external flow
    external_keywords = [
        "around", "over", "external", "aerodynamic", "wind", "air flow",
        "flow around", "flow over", "drag", "lift"
    ]
    
    if any(keyword in prompt_lower for keyword in external_keywords):
        is_external_flow = True
    
    # Determine domain sizing based on geometry
    dimensions = stl_geometry["bounding_box"]["dimensions"]
    char_length = stl_geometry["characteristic_length"]
    
    if is_external_flow:
        # External flow needs larger domain
        domain_size_multiplier = 20.0
        inlet_distance = char_length * 10
        outlet_distance = char_length * 15
    else:
        # Internal flow - domain is the geometry itself
        domain_size_multiplier = 1.2  # Just slightly larger
        inlet_distance = char_length * 0.1
        outlet_distance = char_length * 0.1
    
    return {
        "is_external_flow": is_external_flow,
        "domain_size_multiplier": domain_size_multiplier,
        "inlet_distance": inlet_distance,
        "outlet_distance": outlet_distance,
        "mesh_resolution": "medium",  # Default, can be overridden
        "flow_direction": determine_flow_direction(user_prompt, stl_geometry)
    }


def determine_flow_direction(user_prompt: str, stl_geometry: Dict[str, Any]) -> str:
    """Determine primary flow direction from prompt and geometry."""
    prompt_lower = user_prompt.lower()
    
    # Look for directional indicators in prompt
    if any(word in prompt_lower for word in ["x-direction", "along x", "horizontal"]):
        return "x"
    elif any(word in prompt_lower for word in ["y-direction", "along y", "lateral"]):
        return "y"
    elif any(word in prompt_lower for word in ["z-direction", "along z", "vertical"]):
        return "z"
    
    # Default to longest dimension of geometry
    dimensions = stl_geometry["bounding_box"]["dimensions"]
    max_dim_idx = dimensions.index(max(dimensions))
    
    return ["x", "y", "z"][max_dim_idx]


def create_stl_geometry_info(stl_geometry: Dict[str, Any], flow_context: Dict[str, Any]) -> Dict[str, Any]:
    """Create geometry info structure for STL-based geometry."""
    
    # Use a generic "custom" geometry type for STL
    geometry_type = GeometryType.CUSTOM if hasattr(GeometryType, 'CUSTOM') else "custom"
    
    # Extract dimensions from STL bounding box
    bbox = stl_geometry["bounding_box"]
    dimensions = {
        "length": bbox["dimensions"][0],
        "width": bbox["dimensions"][1], 
        "height": bbox["dimensions"][2],
        "characteristic_length": stl_geometry["characteristic_length"],
        "surface_area": stl_geometry["surface_area"]
    }
    
    # Add volume if available
    if stl_geometry.get("volume"):
        dimensions["volume"] = stl_geometry["volume"]
    
    return {
        "type": geometry_type,
        "dimensions": dimensions,
        "mesh_resolution": flow_context.get("mesh_resolution", "medium"),
        "flow_context": flow_context,
        "stl_surfaces": stl_geometry.get("surfaces", []),
        "mesh_recommendations": stl_geometry.get("mesh_recommendations", {}),
        "source": "stl"
    }


def parse_flow_parameters(user_prompt: str) -> Dict[str, Any]:
    """Parse flow parameters from user prompt (used for both STL and parametric)."""
    # Use existing parameter parsing logic
    return parse_user_prompt(user_prompt)


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
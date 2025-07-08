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


def nl_interpreter_agent(state: CFDState) -> CFDState:
    """
    Natural Language Interpreter Agent.
    
    Parses user's natural language prompt into structured CFD parameters
    using OpenAI GPT-4 with structured output parsing.
    """
    try:
        if state["verbose"]:
            logger.info(f"NL Interpreter: Processing prompt: {state['user_prompt']}")
        
        # Get settings for API key
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Create LLM with structured output
        llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",  # Use mini for faster response during development
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=2000
        )
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=CFDParameters)
        
        # Create prompt template with enhanced instructions
        prompt = ChatPromptTemplate.from_template("""
You are an expert CFD engineer. Parse the following natural language description of a fluid dynamics problem into structured parameters.

Extract all relevant information including:
- Geometry type and dimensions (extract numerical values with units)
- Flow context (is it flow AROUND an object or THROUGH a channel/pipe?)
- Flow conditions (velocity, pressure, temperature)
- Fluid properties (density, viscosity)
- Boundary conditions
- Analysis type (steady/unsteady, laminar/turbulent)
- Solver preferences
- Mesh preferences

IMPORTANT RULES:
1. For "flow around" objects (cylinder, sphere, airfoil), set is_external_flow=true and domain_type="unbounded"
2. For "flow through" or "flow in" objects (pipe, channel), set is_external_flow=false and domain_type="channel"
3. If neither is specified, use these defaults:
   - Cylinder, Sphere, Airfoil → external flow (around object)
   - Pipe, Channel → internal flow (through object)
4. Extract ALL numerical dimensions mentioned (with unit conversion to meters)
5. For external flow, set domain_size_multiplier appropriately (typically 20-30x object size)
6. DEFAULT TO UNSTEADY (TRANSIENT) ANALYSIS unless the user explicitly mentions "steady", "steady-state", or "stationary"

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

{format_instructions}

Return valid JSON that matches the schema exactly.
""")
        
        # Create chain
        chain = prompt | llm | parser
        
        # Process the user prompt
        result = chain.invoke({
            "user_prompt": state["user_prompt"],
            "format_instructions": parser.get_format_instructions()
        })
        
        # Convert to dictionary
        parsed_params = result.dict()
        
        # Extract dimensions from text (as backup/enhancement)
        text_dimensions = extract_dimensions_from_text(state["user_prompt"], parsed_params["geometry_type"])
        
        # Merge extracted dimensions with LLM-parsed dimensions
        for key, value in text_dimensions.items():
            if key not in parsed_params["geometry_dimensions"] or parsed_params["geometry_dimensions"][key] is None:
                parsed_params["geometry_dimensions"][key] = value
        
        # Infer flow context if not properly set
        if "flow_context" not in parsed_params or parsed_params["flow_context"] is None:
            parsed_params["flow_context"] = infer_flow_context(state["user_prompt"], parsed_params["geometry_type"]).dict()
        
        # Apply intelligent defaults for missing dimensions
        parsed_params["geometry_dimensions"] = apply_intelligent_defaults(
            parsed_params["geometry_type"],
            parsed_params["geometry_dimensions"],
            FlowContext(**parsed_params["flow_context"]),
            parsed_params.get("reynolds_number")
        )
        
        # Extract geometry information with flow context
        geometry_info = {
            "type": parsed_params["geometry_type"],
            "dimensions": parsed_params["geometry_dimensions"],
            "mesh_resolution": parsed_params.get("mesh_resolution", "medium"),
            "flow_context": parsed_params["flow_context"]
        }
        
        # Log results if verbose
        if state["verbose"]:
            logger.info(f"NL Interpreter: Extracted geometry: {geometry_info}")
            logger.info(f"NL Interpreter: Flow context: {parsed_params['flow_context']}")
            logger.info(f"NL Interpreter: Flow type: {parsed_params['flow_type']}")
            logger.info(f"NL Interpreter: Analysis type: {parsed_params['analysis_type']}")
        
        # Calculate Reynolds number if not provided
        if not parsed_params.get("reynolds_number") and parsed_params.get("velocity"):
            reynolds_number = calculate_reynolds_number(parsed_params, geometry_info)
            if reynolds_number:
                parsed_params["reynolds_number"] = reynolds_number
        
        # Set default fluid properties if not specified
        parsed_params = set_default_fluid_properties(parsed_params)
        
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
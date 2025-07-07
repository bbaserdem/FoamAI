"""Natural Language Interpreter Agent - Parses user prompts into CFD parameters."""

import json
from typing import Dict, Any, Optional
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType


class CFDParameters(BaseModel):
    """Structured CFD parameters extracted from natural language."""
    
    # Geometry information
    geometry_type: GeometryType = Field(description="Type of geometry (cylinder, airfoil, etc.)")
    geometry_dimensions: Dict[str, float] = Field(description="Geometry dimensions (diameter, length, etc.)")
    
    # Flow conditions
    flow_type: FlowType = Field(description="Flow type (laminar, turbulent, transitional)")
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
    end_time: Optional[float] = Field(None, description="End time for transient simulations")
    time_step: Optional[float] = Field(None, description="Time step")
    
    # Mesh preferences
    mesh_resolution: Optional[str] = Field(None, description="Mesh resolution (coarse, medium, fine)")
    
    # Additional parameters
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Additional extracted information")


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
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_template("""
You are an expert CFD engineer. Parse the following natural language description of a fluid dynamics problem into structured parameters.

Extract all relevant information including:
- Geometry type and dimensions
- Flow conditions (velocity, pressure, temperature)
- Fluid properties (density, viscosity)
- Boundary conditions
- Analysis type (steady/unsteady, laminar/turbulent)
- Solver preferences
- Mesh preferences

Problem Description: {user_prompt}

IMPORTANT: If specific values are not provided, use reasonable defaults for the geometry type or leave as null.
For Reynolds number, calculate if velocity and characteristic length are available.
For common geometries, suggest appropriate dimensions if not specified.

Examples of common setups:
- Cylinder: diameter=0.1m, length=1m, velocity=1-10 m/s
- Airfoil: chord=0.1m, angle of attack=5-10°, velocity=10-100 m/s
- Pipe: diameter=0.05m, length=1m, velocity=0.1-5 m/s

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
        
        # Extract geometry information
        geometry_info = {
            "type": parsed_params["geometry_type"],
            "dimensions": parsed_params["geometry_dimensions"],
            "mesh_resolution": parsed_params.get("mesh_resolution", "medium")
        }
        
        # Log results if verbose
        if state["verbose"]:
            logger.info(f"NL Interpreter: Extracted geometry: {geometry_info}")
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
        
        if not velocity:
            return None
        
        # Get characteristic length based on geometry type
        characteristic_length = get_characteristic_length(geometry_info)
        
        if characteristic_length:
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
        if not params.get(key):
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
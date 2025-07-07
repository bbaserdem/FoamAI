"""Boundary Condition Agent - Generates OpenFOAM boundary conditions."""

import json
from typing import Dict, Any, Optional
from loguru import logger

from .state import CFDState, CFDStep, GeometryType, FlowType


def boundary_condition_agent(state: CFDState) -> CFDState:
    """
    Boundary Condition Agent.
    
    Generates OpenFOAM boundary condition files (0/ directory contents)
    based on flow parameters and geometry information.
    """
    try:
        if state["verbose"]:
            logger.info("Boundary Condition: Starting boundary condition generation")
        
        parsed_params = state["parsed_parameters"]
        geometry_info = state["geometry_info"]
        mesh_config = state["mesh_config"]
        
        # Generate boundary conditions
        boundary_conditions = generate_boundary_conditions(parsed_params, geometry_info, mesh_config)
        
        # Validate boundary conditions
        validation_result = validate_boundary_conditions(boundary_conditions, parsed_params)
        if not validation_result["valid"]:
            logger.warning(f"Boundary condition validation issues: {validation_result['warnings']}")
            return {
                **state,
                "errors": state["errors"] + validation_result["errors"],
                "warnings": state["warnings"] + validation_result["warnings"]
            }
        
        if state["verbose"]:
            logger.info(f"Boundary Condition: Generated {len(boundary_conditions)} field files")
        
        return {
            **state,
            "boundary_conditions": boundary_conditions,
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Boundary Condition error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Boundary condition generation failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def generate_boundary_conditions(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete boundary condition configuration."""
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    velocity = parsed_params.get("velocity", 1.0)
    pressure = parsed_params.get("pressure", 0.0)
    temperature = parsed_params.get("temperature", 293.15)
    
    # Generate field files
    boundary_conditions = {
        "U": generate_velocity_field(parsed_params, geometry_info, mesh_config),
        "p": generate_pressure_field(parsed_params, geometry_info, mesh_config),
    }
    
    # Add turbulence fields if needed
    if flow_type == FlowType.TURBULENT:
        boundary_conditions.update({
            "k": generate_turbulent_kinetic_energy_field(parsed_params, geometry_info, mesh_config),
            "omega": generate_specific_dissipation_field(parsed_params, geometry_info, mesh_config),
            "epsilon": generate_dissipation_field(parsed_params, geometry_info, mesh_config),
            "nut": generate_turbulent_viscosity_field(parsed_params, geometry_info, mesh_config)
        })
    
    # Add temperature field if needed
    if parsed_params.get("temperature"):
        boundary_conditions["T"] = generate_temperature_field(parsed_params, geometry_info, mesh_config)
    
    return boundary_conditions


def generate_velocity_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate velocity field (U) boundary conditions."""
    velocity = parsed_params.get("velocity", 1.0)
    geometry_type = geometry_info["type"]
    
    # Get boundary patches from mesh config
    boundary_patches = mesh_config.get("boundary_patches", {})
    
    # Base velocity field
    velocity_field = {
        "dimensions": "[0 1 -1 0 0 0 0]",
        "internalField": "uniform (0 0 0)",
        "boundaryField": {}
    }
    
    # Configure boundary conditions based on geometry
    if geometry_type == GeometryType.CYLINDER:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity} 0 0)"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "cylinder": {
                "type": "noSlip"
            },
            "walls": {
                "type": "slip"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity} 0 0)"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "noSlip"
            },
            "farfield": {
                "type": "freestreamVelocity",
                "freestreamValue": f"uniform ({velocity} 0 0)"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.PIPE:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity} 0 0)"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "noSlip"
            }
        }
    elif geometry_type == GeometryType.CHANNEL:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity} 0 0)"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "noSlip"
            },
            "sides": {
                "type": "symmetryPlane"
            }
        }
    elif geometry_type == GeometryType.SPHERE:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity} 0 0)"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "noSlip"
            },
            "farfield": {
                "type": "freestreamVelocity",
                "freestreamValue": f"uniform ({velocity} 0 0)"
            }
        }
    
    return velocity_field


def generate_pressure_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate pressure field (p) boundary conditions."""
    pressure = parsed_params.get("pressure", 0.0)
    geometry_type = geometry_info["type"]
    
    # Base pressure field
    pressure_field = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": f"uniform {pressure}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions based on geometry
    if geometry_type == GeometryType.CYLINDER:
        pressure_field["boundaryField"] = {
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "cylinder": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        pressure_field["boundaryField"] = {
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "airfoil": {
                "type": "zeroGradient"
            },
            "farfield": {
                "type": "freestreamPressure",
                "freestreamValue": f"uniform {pressure}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.PIPE:
        pressure_field["boundaryField"] = {
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "walls": {
                "type": "zeroGradient"
            }
        }
    elif geometry_type == GeometryType.CHANNEL:
        pressure_field["boundaryField"] = {
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "walls": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "symmetryPlane"
            }
        }
    elif geometry_type == GeometryType.SPHERE:
        pressure_field["boundaryField"] = {
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "sphere": {
                "type": "zeroGradient"
            },
            "farfield": {
                "type": "freestreamPressure",
                "freestreamValue": f"uniform {pressure}"
            }
        }
    
    return pressure_field


def generate_turbulent_kinetic_energy_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate turbulent kinetic energy field (k)."""
    velocity = parsed_params.get("velocity", 1.0)
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    
    # Calculate turbulent kinetic energy
    k_value = 1.5 * (velocity * turbulence_intensity) ** 2
    
    geometry_type = geometry_info["type"]
    
    # Base k field
    k_field = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": f"uniform {k_value}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE]:
        k_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {k_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            f"{geometry_type.value}": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "walls": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        k_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {k_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "farfield": {
                "type": "inletOutlet",
                "inletValue": f"uniform {k_value}",
                "value": f"uniform {k_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
        k_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {k_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            }
        }
        
        if geometry_type == GeometryType.CHANNEL:
            k_field["boundaryField"]["sides"] = {
                "type": "symmetryPlane"
            }
    
    return k_field


def generate_specific_dissipation_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate specific dissipation rate field (omega)."""
    velocity = parsed_params.get("velocity", 1.0)
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    turbulence_length_scale = parsed_params.get("turbulence_length_scale", 0.01)
    
    # Calculate omega
    k_value = 1.5 * (velocity * turbulence_intensity) ** 2
    omega_value = k_value**0.5 / (0.09**0.25 * turbulence_length_scale)
    
    geometry_type = geometry_info["type"]
    
    # Base omega field
    omega_field = {
        "dimensions": "[0 0 -1 0 0 0 0]",
        "internalField": f"uniform {omega_value}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE]:
        omega_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {omega_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            f"{geometry_type.value}": {
                "type": "omegaWallFunction",
                "value": f"uniform {omega_value}"
            },
            "walls": {
                "type": "omegaWallFunction", 
                "value": f"uniform {omega_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        omega_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {omega_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "omegaWallFunction",
                "value": f"uniform {omega_value}"
            },
            "farfield": {
                "type": "inletOutlet",
                "inletValue": f"uniform {omega_value}",
                "value": f"uniform {omega_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
        omega_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {omega_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "omegaWallFunction",
                "value": f"uniform {omega_value}"
            }
        }
        
        if geometry_type == GeometryType.CHANNEL:
            omega_field["boundaryField"]["sides"] = {
                "type": "symmetryPlane"
            }
    
    return omega_field


def generate_dissipation_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate dissipation rate field (epsilon)."""
    velocity = parsed_params.get("velocity", 1.0)
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    turbulence_length_scale = parsed_params.get("turbulence_length_scale", 0.01)
    
    # Calculate epsilon
    k_value = 1.5 * (velocity * turbulence_intensity) ** 2
    epsilon_value = 0.09 * k_value**1.5 / turbulence_length_scale
    
    geometry_type = geometry_info["type"]
    
    # Base epsilon field
    epsilon_field = {
        "dimensions": "[0 2 -3 0 0 0 0]",
        "internalField": f"uniform {epsilon_value}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE]:
        epsilon_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {epsilon_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            f"{geometry_type.value}": {
                "type": "epsilonWallFunction",
                "value": f"uniform {epsilon_value}"
            },
            "walls": {
                "type": "epsilonWallFunction",
                "value": f"uniform {epsilon_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        epsilon_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {epsilon_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "epsilonWallFunction",
                "value": f"uniform {epsilon_value}"
            },
            "farfield": {
                "type": "inletOutlet",
                "inletValue": f"uniform {epsilon_value}",
                "value": f"uniform {epsilon_value}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
        epsilon_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {epsilon_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "epsilonWallFunction",
                "value": f"uniform {epsilon_value}"
            }
        }
        
        if geometry_type == GeometryType.CHANNEL:
            epsilon_field["boundaryField"]["sides"] = {
                "type": "symmetryPlane"
            }
    
    return epsilon_field


def generate_turbulent_viscosity_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate turbulent viscosity field (nut)."""
    geometry_type = geometry_info["type"]
    
    # Base nut field
    nut_field = {
        "dimensions": "[0 2 -1 0 0 0 0]",
        "internalField": "uniform 0",
        "boundaryField": {}
    }
    
    # Configure boundary conditions (mostly wall functions)
    if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE]:
        nut_field["boundaryField"] = {
            "inlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "outlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            f"{geometry_type.value}": {
                "type": "nutkWallFunction",
                "value": "uniform 0"
            },
            "walls": {
                "type": "nutkWallFunction",
                "value": "uniform 0"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        nut_field["boundaryField"] = {
            "inlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "outlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "airfoil": {
                "type": "nutkWallFunction",
                "value": "uniform 0"
            },
            "farfield": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
        nut_field["boundaryField"] = {
            "inlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "outlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "walls": {
                "type": "nutkWallFunction",
                "value": "uniform 0"
            }
        }
        
        if geometry_type == GeometryType.CHANNEL:
            nut_field["boundaryField"]["sides"] = {
                "type": "symmetryPlane"
            }
    
    return nut_field


def generate_temperature_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate temperature field (T)."""
    temperature = parsed_params.get("temperature", 293.15)
    geometry_type = geometry_info["type"]
    
    # Base temperature field
    temp_field = {
        "dimensions": "[0 0 0 1 0 0 0]",
        "internalField": f"uniform {temperature}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE]:
        temp_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            f"{geometry_type.value}": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type == GeometryType.AIRFOIL:
        temp_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "zeroGradient"
            },
            "farfield": {
                "type": "inletOutlet",
                "inletValue": f"uniform {temperature}",
                "value": f"uniform {temperature}"
            },
            "sides": {
                "type": "empty"
            }
        }
    elif geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
        temp_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "zeroGradient"
            }
        }
        
        if geometry_type == GeometryType.CHANNEL:
            temp_field["boundaryField"]["sides"] = {
                "type": "symmetryPlane"
            }
    
    return temp_field


def validate_boundary_conditions(boundary_conditions: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate boundary condition configuration."""
    errors = []
    warnings = []
    
    # Check required fields
    required_fields = ["U", "p"]
    for field in required_fields:
        if field not in boundary_conditions:
            errors.append(f"Missing required field: {field}")
    
    # Check turbulence fields consistency
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    if flow_type == FlowType.TURBULENT:
        turbulence_fields = ["k", "omega", "epsilon", "nut"]
        missing_fields = [f for f in turbulence_fields if f not in boundary_conditions]
        if missing_fields:
            warnings.append(f"Missing turbulence fields: {missing_fields}")
    
    # Check velocity magnitude
    velocity = parsed_params.get("velocity", 0)
    if velocity <= 0:
        warnings.append("Zero or negative velocity specified")
    
    # Check Reynolds number
    reynolds_number = parsed_params.get("reynolds_number", 0)
    if reynolds_number > 2300 and flow_type == FlowType.LAMINAR:
        warnings.append(f"High Reynolds number ({reynolds_number}) for laminar flow")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    } 
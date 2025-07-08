"""Boundary Condition Agent - Generates OpenFOAM boundary conditions."""

import json
from typing import Dict, Any, Optional
from loguru import logger

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType


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
    """Generate velocity field (U)."""
    velocity = parsed_params.get("velocity", 1.0)
    # Ensure velocity is not None
    if velocity is None:
        logger.warning("Velocity is None, using default 1.0 m/s")
        velocity = 1.0
    
    velocity_components = parsed_params.get("velocity_components", None)
    geometry_type = geometry_info["type"]
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    flow_context = geometry_info.get("flow_context", {})
    is_external_flow = flow_context.get("is_external_flow", False)
    
    # For turbulent channel flow, consider increasing velocity for better visualization
    if geometry_type == GeometryType.CHANNEL and flow_type == FlowType.TURBULENT:
        # Scale up velocity if it seems too low for interesting turbulent features
        if velocity < 2.0:
            logger.info(f"Scaling up velocity from {velocity} to {velocity * 2.5} for better turbulent flow visualization")
            velocity = velocity * 2.5
    
    # Determine velocity vector
    if velocity_components:
        velocity_vector = f"({velocity_components[0]} {velocity_components[1]} {velocity_components[2]})"
    else:
        # Default flow direction based on geometry
        if geometry_type in [GeometryType.PIPE, GeometryType.CHANNEL]:
            velocity_vector = f"({velocity} 0 0)"
        elif geometry_type in [GeometryType.CYLINDER, GeometryType.SPHERE, GeometryType.AIRFOIL]:
            velocity_vector = f"({velocity} 0 0)"
        else:
            velocity_vector = f"({velocity} 0 0)"
    
    # Get boundary patches from mesh config
    boundary_patches = mesh_config.get("boundary_patches", {})
    mesh_topology = mesh_config.get("mesh_topology", "structured")
    
    # Base velocity field
    # For unsteady simulations, start with zero velocity for stability
    if parsed_params.get("analysis_type") == AnalysisType.UNSTEADY:
        velocity_field = {
            "dimensions": "[0 1 -1 0 0 0 0]",
            "internalField": "uniform (0 0 0)",
            "boundaryField": {}
        }
    else:
        velocity_field = {
            "dimensions": "[0 1 -1 0 0 0 0]",
            "internalField": "uniform (0 0 0)",
            "boundaryField": {}
        }
    
    # Configure boundary conditions based on geometry
    if geometry_type == GeometryType.CYLINDER:
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            velocity_field["boundaryField"] = {
                "cylinder": {
                    "type": "noSlip"  # Wall boundary on cylinder surface
                },
                "left": {  # Inlet on left side
                    "type": "fixedValue",
                    "value": f"uniform {velocity_vector}"
                },
                "right": {  # Outlet on right side
                    "type": "zeroGradient"
                },
                "up": {  # Top boundary
                    "type": "symmetryPlane"
                },
                "down": {  # Bottom boundary
                    "type": "noSlip"  # Wall for ground effect (can be changed to symmetryPlane)
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            velocity_field["boundaryField"] = {
                "cylinder": {
                    "type": "noSlip"  # Wall boundary on cylinder surface
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {velocity_vector}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "slip"  # Slip condition for far field
                },
                "bottom": {
                    "type": "slip"  # Slip condition for far field
                },
                "front": {
                    "type": "empty" if is_2d else "slip"
                },
                "back": {
                    "type": "empty" if is_2d else "slip"
                }
            }
        else:
            # Original implementation for rectangular channel
            velocity_field["boundaryField"] = {
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {velocity_vector}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "walls": {
                    "type": "noSlip"
                },
                "sides": {
                    "type": "empty"
                }
            }
    elif geometry_type == GeometryType.AIRFOIL:
        # External flow with snappyHexMesh - use background mesh patch names
        is_2d = mesh_config.get("is_2d", True)
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {velocity_vector}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "airfoil": {
                "type": "noSlip"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            },
            "front": {
                "type": "empty" if is_2d else "slip"
            },
            "back": {
                "type": "empty" if is_2d else "slip"
            }
        }
    elif geometry_type == GeometryType.PIPE:
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {velocity_vector}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "noSlip"
            }
        }
    elif geometry_type == GeometryType.CHANNEL:
        # Check if this is a 2D or 3D case
        is_2d = False
        if mesh_config and "resolution" in mesh_config:
            spanwise_cells = mesh_config.get("resolution", {}).get("spanwise", 1)
            is_2d = spanwise_cells == 1
        
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {velocity_vector}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "noSlip"
            },
            "sides": {
                "type": "empty" if is_2d else "symmetry"
            }
        }
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        velocity_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {velocity_vector}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "noSlip"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            },
            "front": {
                "type": "slip"
            },
            "back": {
                "type": "slip"
            }
        }
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube with snappyHexMesh
        is_2d = mesh_config.get("is_2d", False)
        
        velocity_field["boundaryField"] = {
            "cube": {
                "type": "noSlip"  # Wall boundary on cube surface
            },
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {velocity_vector}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "slip"  # Slip condition for far field
            },
            "bottom": {
                "type": "slip"  # Slip condition for far field
            },
            "front": {
                "type": "empty" if is_2d else "slip"
            },
            "back": {
                "type": "empty" if is_2d else "slip"
            }
        }
    
    return velocity_field


def generate_pressure_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate pressure field (p) boundary conditions."""
    pressure = parsed_params.get("pressure", 0.0)
    geometry_type = geometry_info["type"]
    flow_context = geometry_info.get("flow_context", {})
    is_external_flow = flow_context.get("is_external_flow", False)
    mesh_topology = mesh_config.get("mesh_topology", "structured")
    
    # Base pressure field
    pressure_field = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": f"uniform {pressure}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions based on geometry
    if geometry_type == GeometryType.CYLINDER:
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            pressure_field["boundaryField"] = {
                "cylinder": {
                    "type": "zeroGradient"  # No pressure gradient at wall
                },
                "left": {  # Inlet on left side
                    "type": "zeroGradient"
                },
                "right": {  # Outlet on right side
                    "type": "fixedValue",
                    "value": f"uniform {pressure}"
                },
                "up": {  # Top boundary
                    "type": "symmetryPlane"
                },
                "down": {  # Bottom boundary
                    "type": "zeroGradient"
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            pressure_field["boundaryField"] = {
                "cylinder": {
                    "type": "zeroGradient"  # No pressure gradient at wall
                },
                "inlet": {
                    "type": "zeroGradient"
                },
                "outlet": {
                    "type": "fixedValue",
                    "value": f"uniform {pressure}"
                },
                "top": {
                    "type": "zeroGradient"
                },
                "bottom": {
                    "type": "zeroGradient"
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
                }
            }
        else:
            # Original implementation for rectangular channel
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
                    "type": "empty"
                }
            }
    elif geometry_type == GeometryType.AIRFOIL:
        # External flow with snappyHexMesh - use background mesh patch names
        is_2d = mesh_config.get("is_2d", True)
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
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            },
            "front": {
                "type": "empty" if is_2d else "zeroGradient"
            },
            "back": {
                "type": "empty" if is_2d else "zeroGradient"
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
        # Check if this is a 2D or 3D case
        is_2d = False
        if mesh_config and "resolution" in mesh_config:
            spanwise_cells = mesh_config.get("resolution", {}).get("spanwise", 1)
            is_2d = spanwise_cells == 1
        
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
                "type": "empty" if is_2d else "symmetry"
            }
        }
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
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
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            },
            "front": {
                "type": "zeroGradient"
            },
            "back": {
                "type": "zeroGradient"
            }
        }
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube
        is_2d = mesh_config.get("is_2d", False)
        
        pressure_field["boundaryField"] = {
            "cube": {
                "type": "zeroGradient"  # No pressure gradient at wall
            },
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            },
            "front": {
                "type": "empty" if is_2d else "zeroGradient"
            },
            "back": {
                "type": "empty" if is_2d else "zeroGradient"
            }
        }
    
    return pressure_field


def generate_turbulent_kinetic_energy_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate turbulent kinetic energy field (k)."""
    velocity = parsed_params.get("velocity", 1.0)
    if velocity is None:
        velocity = 1.0  # Default velocity
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    if turbulence_intensity is None:
        turbulence_intensity = 0.05  # Default turbulence intensity
    turbulence_length_scale = parsed_params.get("turbulence_length_scale", 0.01)
    if turbulence_length_scale is None:
        turbulence_length_scale = 0.01  # Default length scale
    
    # Calculate k
    k_value = 1.5 * (velocity * turbulence_intensity) ** 2
    
    geometry_type = geometry_info["type"]
    flow_context = geometry_info.get("flow_context", {})
    is_external_flow = flow_context.get("is_external_flow", False)
    mesh_topology = mesh_config.get("mesh_topology", "structured")
    
    # Base k field
    k_field = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": f"uniform {k_value}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type == GeometryType.CYLINDER:
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            k_field["boundaryField"] = {
                "cylinder": {
                    "type": "kqRWallFunction",
                    "value": f"uniform {k_value}"
                },
                "left": {  # Inlet on left side
                    "type": "fixedValue",
                    "value": f"uniform {k_value}"
                },
                "right": {  # Outlet on right side
                    "type": "zeroGradient"
                },
                "up": {  # Top boundary
                    "type": "symmetryPlane"
                },
                "down": {  # Bottom boundary
                    "type": "kqRWallFunction",
                    "value": f"uniform {k_value}"
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            k_field["boundaryField"] = {
                "cylinder": {
                    "type": "kqRWallFunction",
                    "value": f"uniform {k_value}"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {k_value}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "kqRWallFunction",
                    "value": f"uniform {k_value}"
                },
                "bottom": {
                    "type": "kqRWallFunction",
                    "value": f"uniform {k_value}"
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
                }
            }
        else:
            # Original implementation
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
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        k_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {k_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            },
            "front": {
                "type": "slip"
            },
            "back": {
                "type": "slip"
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
            # Check if this is 2D or 3D based on mesh resolution
            is_2d = mesh_config.get("resolution", {}).get("spanwise", 1) == 1
            sides_type = "empty" if is_2d else "symmetry"
            k_field["boundaryField"]["sides"] = {
                "type": sides_type
            }
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube
        is_2d = mesh_config.get("is_2d", False)
        
        k_field["boundaryField"] = {
            "cube": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {k_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "bottom": {
                "type": "kqRWallFunction",
                "value": f"uniform {k_value}"
            },
            "front": {
                "type": "empty" if is_2d else "zeroGradient"
            },
            "back": {
                "type": "empty" if is_2d else "zeroGradient"
            }
        }
    
    return k_field


def generate_specific_dissipation_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate specific dissipation rate field (omega)."""
    velocity = parsed_params.get("velocity", 1.0)
    if velocity is None:
        velocity = 1.0  # Default velocity
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    if turbulence_intensity is None:
        turbulence_intensity = 0.05  # Default turbulence intensity
    turbulence_length_scale = parsed_params.get("turbulence_length_scale", 0.01)
    if turbulence_length_scale is None:
        turbulence_length_scale = 0.01  # Default length scale
    
    # Calculate omega
    k_value = 1.5 * (velocity * turbulence_intensity) ** 2
    omega_value = k_value**0.5 / (0.09**0.25 * turbulence_length_scale)
    
    geometry_type = geometry_info["type"]
    flow_context = geometry_info.get("flow_context", {})
    is_external_flow = flow_context.get("is_external_flow", False)
    mesh_topology = mesh_config.get("mesh_topology", "structured")
    
    # Base omega field
    omega_field = {
        "dimensions": "[0 0 -1 0 0 0 0]",
        "internalField": f"uniform {omega_value}",
        "boundaryField": {}
    }
    
    # Configure boundary conditions
    if geometry_type == GeometryType.CYLINDER:
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            omega_field["boundaryField"] = {
                "cylinder": {
                    "type": "omegaWallFunction",
                    "value": f"uniform {omega_value}"
                },
                "left": {  # Inlet on left side
                    "type": "fixedValue",
                    "value": f"uniform {omega_value}"
                },
                "right": {  # Outlet on right side
                    "type": "zeroGradient"
                },
                "up": {  # Top boundary
                    "type": "symmetryPlane"
                },
                "down": {  # Bottom boundary
                    "type": "omegaWallFunction",
                    "value": f"uniform {omega_value}"
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            omega_field["boundaryField"] = {
                "cylinder": {
                    "type": "omegaWallFunction",
                    "value": f"uniform {omega_value}"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {omega_value}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "slip"  # Slip condition for far field
                },
                "bottom": {
                    "type": "slip"  # Slip condition for far field
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
                }
            }
        else:
            # Original implementation
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
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        omega_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {omega_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "omegaWallFunction",
                "value": f"uniform {omega_value}"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            },
            "front": {
                "type": "slip"
            },
            "back": {
                "type": "slip"
            }
        }
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube with snappyHexMesh
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        is_2d = mesh_config.get("is_2d", False)
        
        if mesh_topology == "snappy":
            omega_field["boundaryField"] = {
                "cube": {
                    "type": "omegaWallFunction",
                    "value": f"uniform {omega_value}"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {omega_value}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "slip"
                },
                "bottom": {
                    "type": "slip"
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
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
            # Check if this is 2D or 3D based on mesh resolution
            is_2d = mesh_config.get("resolution", {}).get("spanwise", 1) == 1
            sides_type = "empty" if is_2d else "symmetry"
            omega_field["boundaryField"]["sides"] = {
                "type": sides_type
            }
    
    return omega_field


def generate_dissipation_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate dissipation rate field (epsilon)."""
    velocity = parsed_params.get("velocity", 1.0)
    if velocity is None:
        velocity = 1.0  # Default velocity
    turbulence_intensity = parsed_params.get("turbulence_intensity", 0.05)
    if turbulence_intensity is None:
        turbulence_intensity = 0.05  # Default turbulence intensity
    turbulence_length_scale = parsed_params.get("turbulence_length_scale", 0.01)
    if turbulence_length_scale is None:
        turbulence_length_scale = 0.01  # Default length scale
    
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
    if geometry_type == GeometryType.CYLINDER:
        # Check if this is O-grid mesh
        flow_context = geometry_info.get("flow_context", {})
        is_external_flow = flow_context.get("is_external_flow", False)
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            epsilon_field["boundaryField"] = {
                "cylinder": {
                    "type": "epsilonWallFunction",
                    "value": f"uniform {epsilon_value}"
                },
                "left": {  # Inlet on left side
                    "type": "fixedValue",
                    "value": f"uniform {epsilon_value}"
                },
                "right": {  # Outlet on right side
                    "type": "zeroGradient"
                },
                "up": {  # Top boundary
                    "type": "symmetryPlane"
                },
                "down": {  # Bottom boundary
                    "type": "epsilonWallFunction",
                    "value": f"uniform {epsilon_value}"
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            epsilon_field["boundaryField"] = {
                "cylinder": {
                    "type": "epsilonWallFunction",
                    "value": f"uniform {epsilon_value}"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {epsilon_value}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "slip"  # Slip condition for far field
                },
                "bottom": {
                    "type": "slip"  # Slip condition for far field
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
                }
            }
        else:
            # Original rectangular channel implementation
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
                },
                "sides": {
                    "type": "empty"
                }
            }
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        epsilon_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {epsilon_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "epsilonWallFunction",
                "value": f"uniform {epsilon_value}"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            },
            "front": {
                "type": "slip"
            },
            "back": {
                "type": "slip"
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
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube with snappyHexMesh
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        is_2d = mesh_config.get("is_2d", False)
        
        if mesh_topology == "snappy":
            epsilon_field["boundaryField"] = {
                "cube": {
                    "type": "epsilonWallFunction",
                    "value": f"uniform {epsilon_value}"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {epsilon_value}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "slip"
                },
                "bottom": {
                    "type": "slip"
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
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
            # Check if this is 2D or 3D based on mesh resolution
            is_2d = mesh_config.get("resolution", {}).get("spanwise", 1) == 1
            sides_type = "empty" if is_2d else "symmetry"
            epsilon_field["boundaryField"]["sides"] = {
                "type": sides_type
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
    if geometry_type == GeometryType.CYLINDER:
        # Check if this is O-grid mesh
        flow_context = geometry_info.get("flow_context", {})
        is_external_flow = flow_context.get("is_external_flow", False)
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        
        if is_external_flow and mesh_topology == "o-grid":
            # External flow around cylinder with O-grid mesh
            nut_field["boundaryField"] = {
                "cylinder": {
                    "type": "nutkWallFunction",
                    "value": "uniform 0"
                },
                "left": {  # Inlet on left side
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "right": {  # Outlet on right side
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "up": {  # Top boundary
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "down": {  # Bottom boundary
                    "type": "nutkWallFunction",
                    "value": "uniform 0"
                },
                "front": {  # Front face for 2D
                    "type": "empty"
                },
                "back": {  # Back face for 2D
                    "type": "empty"
                }
            }
        elif is_external_flow and mesh_topology == "snappy":
            # External flow around cylinder with snappyHexMesh
            is_2d = mesh_config.get("is_2d", True)
            
            nut_field["boundaryField"] = {
                "cylinder": {
                    "type": "nutkWallFunction",
                    "value": "uniform 0"
                },
                "inlet": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "outlet": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "top": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "bottom": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "front": {
                    "type": "empty" if is_2d else "calculated",
                    "value": "uniform 0"
                } if not is_2d else {"type": "empty"},
                "back": {
                    "type": "empty" if is_2d else "calculated", 
                    "value": "uniform 0"
                } if not is_2d else {"type": "empty"}
            }
        else:
            # Original rectangular channel implementation
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
                },
                "sides": {
                    "type": "empty"
                }
            }
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        nut_field["boundaryField"] = {
            "inlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "outlet": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "sphere": {
                "type": "nutkWallFunction",
                "value": "uniform 0"
            },
            "top": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "bottom": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "front": {
                "type": "calculated",
                "value": "uniform 0"
            },
            "back": {
                "type": "calculated",
                "value": "uniform 0"
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
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube with snappyHexMesh
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        is_2d = mesh_config.get("is_2d", False)
        
        if mesh_topology == "snappy":
            nut_field["boundaryField"] = {
                "cube": {
                    "type": "nutkWallFunction",
                    "value": "uniform 0"
                },
                "inlet": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "outlet": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "top": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "bottom": {
                    "type": "calculated",
                    "value": "uniform 0"
                },
                "front": {
                    "type": "empty" if is_2d else "calculated",
                    "value": "uniform 0"
                } if not is_2d else {"type": "empty"},
                "back": {
                    "type": "empty" if is_2d else "calculated", 
                    "value": "uniform 0"
                } if not is_2d else {"type": "empty"}
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
            # Check if this is 2D or 3D based on mesh resolution
            is_2d = mesh_config.get("resolution", {}).get("spanwise", 1) == 1
            sides_type = "empty" if is_2d else "symmetry"
            nut_field["boundaryField"]["sides"] = {
                "type": sides_type
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
    if geometry_type == GeometryType.CYLINDER:
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
    elif geometry_type == GeometryType.SPHERE:
        # External flow with snappyHexMesh - use background mesh patch names
        temp_field["boundaryField"] = {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sphere": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            },
            "front": {
                "type": "zeroGradient"
            },
            "back": {
                "type": "zeroGradient"
            }
        }
    elif geometry_type == GeometryType.CUBE:
        # External flow around cube with snappyHexMesh
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        is_2d = mesh_config.get("is_2d", False)
        
        if mesh_topology == "snappy":
            temp_field["boundaryField"] = {
                "cube": {
                    "type": "zeroGradient"
                },
                "inlet": {
                    "type": "fixedValue",
                    "value": f"uniform {temperature}"
                },
                "outlet": {
                    "type": "zeroGradient"
                },
                "top": {
                    "type": "zeroGradient"
                },
                "bottom": {
                    "type": "zeroGradient"
                },
                "front": {
                    "type": "empty" if is_2d else "zeroGradient"
                },
                "back": {
                    "type": "empty" if is_2d else "zeroGradient"
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
            # Check if this is 2D or 3D based on mesh resolution
            is_2d = mesh_config.get("resolution", {}).get("spanwise", 1) == 1
            sides_type = "empty" if is_2d else "symmetry"
            temp_field["boundaryField"]["sides"] = {
                "type": sides_type
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
    if velocity is not None and velocity <= 0:
        warnings.append("Zero or negative velocity specified")
    
    # Check Reynolds number
    reynolds_number = parsed_params.get("reynolds_number", 0)
    if reynolds_number is not None and reynolds_number > 2300 and flow_type == FlowType.LAMINAR:
        warnings.append(f"High Reynolds number ({reynolds_number}) for laminar flow")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def generate_boundary_conditions_cylinder(state: CFDState) -> Dict[str, Any]:
    """Generate boundary conditions for cylinder geometry."""
    # For simple rectangular channel (no cylinder boundary for now)
    boundary_conditions = {
        "inlet": {
            "U": {"type": "fixedValue", "value": f"uniform ({state.velocity or 1.0} 0 0)"},
            "p": {"type": "zeroGradient"}
        },
        "outlet": {
            "U": {"type": "zeroGradient"},
            "p": {"type": "fixedValue", "value": "uniform 0"}
        },
        "walls": {
            "U": {"type": "noSlip"},
            "p": {"type": "zeroGradient"}
        },
        "sides": {
            "U": {"type": "empty"},
            "p": {"type": "empty"}
        }
    }
    
    # Add turbulence fields if needed
    if state.flow_type == FlowType.TURBULENT:
        for boundary, conditions in boundary_conditions.items():
            if boundary == "inlet":
                conditions.update({
                    "k": {"type": "fixedValue", "value": "uniform 0.1"},
                    "omega": {"type": "fixedValue", "value": "uniform 1.0"},
                    "epsilon": {"type": "fixedValue", "value": "uniform 0.1"},
                    "nut": {"type": "calculated", "value": "uniform 0"}
                })
            elif boundary == "walls":
                conditions.update({
                    "k": {"type": "kqRWallFunction", "value": "uniform 0.1"},
                    "omega": {"type": "omegaWallFunction", "value": "uniform 1.0"},
                    "epsilon": {"type": "epsilonWallFunction", "value": "uniform 0.1"},
                    "nut": {"type": "nutkWallFunction", "value": "uniform 0"}
                })
            elif boundary == "sides":
                conditions.update({
                    "k": {"type": "empty"},
                    "omega": {"type": "empty"},
                    "epsilon": {"type": "empty"},
                    "nut": {"type": "empty"}
                })
            else:  # outlet
                conditions.update({
                    "k": {"type": "zeroGradient"},
                    "omega": {"type": "zeroGradient"},
                    "epsilon": {"type": "zeroGradient"},
                    "nut": {"type": "calculated", "value": "uniform 0"}
                })
    
    # Add temperature field if needed
    if state.temperature is not None:
        for boundary, conditions in boundary_conditions.items():
            if boundary == "inlet":
                conditions["T"] = {"type": "fixedValue", "value": f"uniform {state.temperature}"}
            elif boundary == "sides":
                conditions["T"] = {"type": "empty"}
            else:
                conditions["T"] = {"type": "zeroGradient"}
    
    return boundary_conditions 
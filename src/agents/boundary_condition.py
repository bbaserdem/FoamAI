"""Boundary Condition Agent - Generates OpenFOAM boundary conditions."""

from typing import Dict, Any, Optional, List
from pathlib import Path
import re
import json
import openai
from loguru import logger

from .state import CFDState, CFDStep, FlowType, GeometryType, AnalysisType, SolverType

def boundary_condition_agent(state: CFDState) -> CFDState:
    """Generate boundary conditions for CFD simulation."""
    try:
        logger.info("Boundary Condition: Starting boundary condition generation")
        
        # Extract parameters from state
        parsed_params = state["parsed_parameters"]
        geometry_info = state["geometry_info"]
        mesh_config = state["mesh_config"]
        
        # Generate boundary conditions with intelligent mapping
        boundary_conditions = generate_boundary_conditions_with_mapping(
            parsed_params, geometry_info, mesh_config, state
        )
        
        # Validate boundary conditions
        validation = validate_boundary_conditions(boundary_conditions, parsed_params)
        
        state = {
            **state,
            "boundary_conditions": boundary_conditions,
            "current_step": CFDStep.BOUNDARY_CONDITIONS,
            "warnings": state.get("warnings", []) + validation.get("warnings", [])
        }
        
        if not validation["valid"]:
            state["errors"] = state["errors"] + validation["errors"]
            state["current_step"] = CFDStep.ERROR
        
        logger.info(f"Boundary Condition: Generated {len(boundary_conditions)} field files")
        
        return state
        
    except Exception as e:
        logger.error(f"Boundary Condition error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Boundary condition generation failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def read_mesh_patches(case_directory: Path) -> List[str]:
    """Read actual mesh patches from the boundary file."""
    patches_info = read_mesh_patches_with_types(case_directory)
    return [info['name'] for info in patches_info]


def read_mesh_patches_with_types(case_directory: Path) -> List[Dict[str, str]]:
    """Read actual mesh patches with their types from the boundary file."""
    try:
        boundary_file = case_directory / "constant" / "polyMesh" / "boundary"
        if not boundary_file.exists():
            logger.warning(f"Boundary file not found: {boundary_file}")
            return []
        
        with open(boundary_file, 'r') as f:
            content = f.read()
        
        # Extract patch names and types by finding patch blocks
        patches = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for patch name (alphabetic word on its own line)
            if (line and not line.startswith('//') and not line.startswith('/*') and 
                line.isalpha() and line not in ['FoamFile']):
                
                # Check if the next line has an opening brace
                if i + 1 < len(lines) and lines[i + 1].strip() == '{':
                    patch_name = line
                    
                    # Look for type in the following lines
                    patch_type = None
                    for j in range(i + 2, min(i + 10, len(lines))):  # Look ahead from after the brace
                        if 'type' in lines[j]:
                            type_match = re.search(r'type\s+(\w+);', lines[j])
                            if type_match:
                                patch_type = type_match.group(1)
                                break
                    
                    if patch_type:
                        patches.append({
                            'name': patch_name,
                            'type': patch_type
                        })
                        logger.debug(f"Found patch: {patch_name} (type: {patch_type})")
        
        logger.info(f"Read {len(patches)} mesh patches: {[p['name'] for p in patches]}")
        return patches
        
    except Exception as e:
        logger.error(f"Error reading mesh patches: {str(e)}")
        return []


def map_boundary_conditions_to_patches(
    boundary_conditions: Dict[str, Any], 
    actual_patches: List[str],
    geometry_type: GeometryType,
    case_directory: Path = None
) -> Dict[str, Any]:
    """Map generated boundary conditions to actual mesh patches with proper type handling."""
    
    # Get patch types if case directory is provided
    patch_types = {}
    if case_directory:
        patches_info = read_mesh_patches_with_types(case_directory)
        patch_types = {info['name']: info['type'] for info in patches_info}
    
    # Define mapping rules for different geometries
    patch_mappings = {
        GeometryType.PIPE: {
            # Pipe already works - direct mapping
            "inlet": ["inlet"],
            "outlet": ["outlet"], 
            "walls": ["walls", "wall"]
        },
        GeometryType.CYLINDER: {
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "cylinder": ["cylinder"],
            "walls": ["top", "bottom"],  # Map generic walls to top/bottom
            "sides": ["front", "back"]   # Map generic sides to front/back
        },
        GeometryType.SPHERE: {
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "sphere": ["sphere"],
            "walls": ["top", "bottom"],
            "sides": ["front", "back"]
        },
        GeometryType.CUBE: {
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "cube": ["cube"],
            "walls": ["top", "bottom"],
            "sides": ["front", "back"]
        },
        GeometryType.AIRFOIL: {
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "airfoil": ["airfoil"],
            "farfield": ["farfield"],
            "sides": ["sides"]
        },
        GeometryType.CHANNEL: {
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "walls": ["walls", "top", "bottom"],
            "sides": ["sides", "front", "back"]
        }
    }
    
    mapping = patch_mappings.get(geometry_type, {})
    mapped_conditions = {}
    
    logger.info(f"Mapping boundary conditions for {geometry_type} with patches: {actual_patches}")
    
    # For each field in boundary conditions
    for field_name, field_data in boundary_conditions.items():
        if "boundaryField" not in field_data:
            mapped_conditions[field_name] = field_data
            continue
            
        new_boundary_field = {}
        
        # Map each boundary condition to actual patches
        for bc_name, bc_data in field_data["boundaryField"].items():
            target_patches = mapping.get(bc_name, [bc_name])  # Default to original name
            
            # Find which target patches actually exist in the mesh
            existing_patches = [p for p in target_patches if p in actual_patches]
            
            if existing_patches:
                # Apply the boundary condition to all existing patches
                for patch in existing_patches:
                    # Get the patch type and adjust boundary condition if needed
                    patch_type = patch_types.get(patch, "patch")
                    bc_data_adjusted = adjust_boundary_condition_for_patch_type(
                        bc_data, patch_type, field_name, patch
                    )
                    new_boundary_field[patch] = bc_data_adjusted
            else:
                # If no mapping found, keep original if it exists in mesh
                if bc_name in actual_patches:
                    patch_type = patch_types.get(bc_name, "patch")
                    bc_data_adjusted = adjust_boundary_condition_for_patch_type(
                        bc_data, patch_type, field_name, bc_name
                    )
                    new_boundary_field[bc_name] = bc_data_adjusted
                else:
                    logger.warning(f"No patch found for boundary condition {bc_name} in field {field_name}")
        
        # Create the mapped field
        mapped_conditions[field_name] = {
            **field_data,
            "boundaryField": new_boundary_field
        }
    
    return mapped_conditions


def adjust_boundary_condition_for_patch_type(
    bc_data: Dict[str, Any],
    patch_type: str,
    field_name: str,
    patch_name: str
) -> Dict[str, Any]:
    """Adjust boundary condition type based on mesh patch type."""
    
    # Handle symmetry patches
    if patch_type == "symmetry":
        # For symmetry patches, use symmetry instead of zeroGradient
        if bc_data.get("type") == "zeroGradient":
            logger.info(f"Adjusting {field_name} boundary condition for symmetry patch {patch_name}: zeroGradient -> symmetry")
            return {"type": "symmetry"}
        # For velocity fields on symmetry, use symmetry instead of noSlip
        elif bc_data.get("type") == "noSlip":
            logger.info(f"Adjusting {field_name} boundary condition for symmetry patch {patch_name}: noSlip -> symmetry")
            return {"type": "symmetry"}
        # For fixedValue on symmetry, use symmetry (symmetry overrides fixed values)
        elif bc_data.get("type") == "fixedValue":
            logger.info(f"Adjusting {field_name} boundary condition for symmetry patch {patch_name}: fixedValue -> symmetry")
            return {"type": "symmetry"}
    
    # Handle empty patches (for 2D cases)
    elif patch_type == "empty":
        logger.info(f"Adjusting {field_name} boundary condition for empty patch {patch_name}: {bc_data.get('type')} -> empty")
        return {"type": "empty"}
    
    # For other patch types, keep the original boundary condition
    return bc_data


def get_ai_boundary_conditions(
    solver_type: SolverType,
    geometry_info: Dict[str, Any], 
    parsed_params: Dict[str, Any],
    actual_patches: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Use OpenAI to determine appropriate boundary conditions for complex solvers."""
    
    try:
        # Prepare context for AI
        context = {
            "solver": solver_type.value if hasattr(solver_type, 'value') else str(solver_type),
            "geometry": str(geometry_info.get("type", "unknown")),
            "patches": actual_patches,
            "velocity": parsed_params.get("velocity", 1.0),
            "temperature": parsed_params.get("temperature", 293.15),
            "pressure": parsed_params.get("pressure", 101325),
            "reynolds_number": parsed_params.get("reynolds_number"),
            "mach_number": parsed_params.get("mach_number")
        }
        
        prompt = f"""
You are an OpenFOAM CFD expert. Generate appropriate boundary conditions for:

Solver: {context['solver']}
Geometry: {context['geometry']}
Available patches: {context['patches']}

Physical conditions:
- Velocity: {context['velocity']} m/s
- Temperature: {context['temperature']} K
- Pressure: {context['pressure']} Pa
- Reynolds number: {context['reynolds_number']}
- Mach number: {context['mach_number']}

For each patch, specify the boundary condition type and values for the main fields:
- Velocity (U)
- Pressure (p or p_rgh)
- Temperature (T) if applicable
- Turbulence fields (k, omega, epsilon, nut) if applicable
- Species fields if applicable

Return ONLY a valid JSON object with this structure:
{{
    "patch_name": {{
        "U": {{"type": "boundary_type", "value": "value_if_needed"}},
        "p": {{"type": "boundary_type", "value": "value_if_needed"}},
        "T": {{"type": "boundary_type", "value": "value_if_needed"}}
    }}
}}

Common boundary types:
- fixedValue: for specified values
- zeroGradient: for zero normal gradient
- noSlip: for wall velocity
- empty: for 2D boundaries
- inletOutlet: for pressure outlets
- symmetry: for symmetric boundaries
"""

        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI boundary condition response: {ai_response}")
            
            # Parse JSON response
            boundary_conditions = json.loads(ai_response)
            return boundary_conditions
            
        except Exception as e:
            logger.warning(f"OpenAI API error: {str(e)}")
            return {}
            
    except Exception as e:
        logger.error(f"Error in AI boundary condition generation: {str(e)}")
        return {}


def generate_boundary_conditions_with_mapping(
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    state: CFDState
) -> Dict[str, Any]:
    """Generate boundary conditions with intelligent mapping to mesh patches."""
    
    # Check if this is STL geometry
    if geometry_info.get("source") == "stl":
        return generate_stl_boundary_conditions(parsed_params, geometry_info, mesh_config, state)
    
    # For parametric geometry, use original logic
    case_directory = Path(state.get("case_directory", ""))
    
    # Generate base boundary conditions
    boundary_conditions = generate_boundary_conditions(parsed_params, geometry_info, mesh_config)
    
    # If case directory exists, map to actual patches
    if case_directory.exists():
        actual_patches = read_mesh_patches(case_directory)
        if actual_patches:
            # Map boundary conditions to actual mesh patches
            geometry_type = geometry_info.get("type", GeometryType.CYLINDER)
            boundary_conditions = map_boundary_conditions_to_patches(
                boundary_conditions, actual_patches, geometry_type, case_directory
            )
    
    return boundary_conditions


def generate_stl_boundary_conditions(
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    state: CFDState
) -> Dict[str, Any]:
    """Generate boundary conditions for STL geometry."""
    
    stl_surfaces = geometry_info.get("stl_surfaces", [])
    flow_context = geometry_info.get("flow_context", {})
    is_external_flow = flow_context.get("is_external_flow", True)
    
    if state.get("verbose"):
        logger.info(f"Generating STL boundary conditions for {len(stl_surfaces)} surfaces")
    
    # Create boundary conditions for each field
    boundary_conditions = {}
    
    # Generate velocity field
    boundary_conditions["U"] = generate_stl_velocity_field(
        parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
    )
    
    # Generate pressure field
    boundary_conditions["p"] = generate_stl_pressure_field(
        parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
    )
    
    # Generate turbulence fields if needed
    flow_type = parsed_params.get("flow_type", FlowType.TURBULENT)
    if flow_type == FlowType.TURBULENT:
        boundary_conditions["k"] = generate_stl_turbulence_field(
            "k", parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
        )
        boundary_conditions["omega"] = generate_stl_turbulence_field(
            "omega", parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
        )
        boundary_conditions["nut"] = generate_stl_turbulence_field(
            "nut", parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
        )
    
    # Generate temperature field if needed
    if parsed_params.get("temperature") is not None:
        boundary_conditions["T"] = generate_stl_temperature_field(
            parsed_params, geometry_info, mesh_config, stl_surfaces, is_external_flow
        )
    
    return boundary_conditions


def generate_stl_velocity_field(
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    stl_surfaces: List[Dict[str, Any]],
    is_external_flow: bool
) -> Dict[str, Any]:
    """Generate velocity field for STL geometry."""
    
    # Extract flow parameters
    velocity = parsed_params.get("velocity", 1.0)
    flow_direction = geometry_info.get("flow_context", {}).get("flow_direction", "x")
    
    # Convert flow direction to velocity vector
    velocity_vector = [0.0, 0.0, 0.0]
    direction_map = {"x": 0, "y": 1, "z": 2}
    if flow_direction in direction_map:
        velocity_vector[direction_map[flow_direction]] = velocity
    
    # Base velocity field structure
    velocity_field = {
        "dimensions": "[0 1 -1 0 0 0 0]",
        "internalField": f"uniform ({velocity_vector[0]} {velocity_vector[1]} {velocity_vector[2]})",
        "boundaryField": {}
    }
    
    # Add STL surface boundary conditions
    for surface in stl_surfaces:
        region_name = f"stl_{surface['name']}"
        bc_info = surface["recommended_bc"]
        
        if bc_info.get("U") == "fixedValue":
            # Inlet surface
            velocity_field["boundaryField"][region_name] = {
                "type": "fixedValue",
                "value": f"uniform ({velocity_vector[0]} {velocity_vector[1]} {velocity_vector[2]})"
            }
        elif bc_info.get("U") == "zeroGradient":
            # Outlet surface
            velocity_field["boundaryField"][region_name] = {
                "type": "zeroGradient"
            }
        else:
            # Wall surface (noSlip)
            velocity_field["boundaryField"][region_name] = {
                "type": "noSlip"
            }
    
    # Add domain boundary conditions for external flow
    if is_external_flow:
        velocity_field["boundaryField"].update({
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform ({velocity_vector[0]} {velocity_vector[1]} {velocity_vector[2]})"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "slip"
            },
            "top": {
                "type": "slip"
            },
            "bottom": {
                "type": "slip"
            }
        })
    
    return velocity_field


def generate_stl_pressure_field(
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    stl_surfaces: List[Dict[str, Any]],
    is_external_flow: bool
) -> Dict[str, Any]:
    """Generate pressure field for STL geometry."""
    
    # Extract pressure parameters
    pressure = parsed_params.get("pressure", 0.0)
    
    # Base pressure field structure
    pressure_field = {
        "dimensions": "[0 2 -2 0 0 0 0]",
        "internalField": f"uniform {pressure}",
        "boundaryField": {}
    }
    
    # Add STL surface boundary conditions
    for surface in stl_surfaces:
        region_name = f"stl_{surface['name']}"
        bc_info = surface["recommended_bc"]
        
        if bc_info.get("p") == "fixedValue":
            # Outlet surface
            pressure_field["boundaryField"][region_name] = {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            }
        else:
            # Inlet and wall surfaces (zeroGradient)
            pressure_field["boundaryField"][region_name] = {
                "type": "zeroGradient"
            }
    
    # Add domain boundary conditions for external flow
    if is_external_flow:
        pressure_field["boundaryField"].update({
            "inlet": {
                "type": "zeroGradient"
            },
            "outlet": {
                "type": "fixedValue",
                "value": f"uniform {pressure}"
            },
            "sides": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            }
        })
    
    return pressure_field


def generate_stl_turbulence_field(
    field_name: str,
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    stl_surfaces: List[Dict[str, Any]],
    is_external_flow: bool
) -> Dict[str, Any]:
    """Generate turbulence field for STL geometry."""
    
    # Calculate turbulence parameters
    velocity = parsed_params.get("velocity", 1.0)
    char_length = geometry_info.get("dimensions", {}).get("characteristic_length", 1.0)
    
    # Turbulence intensity (3-5% typical)
    turb_intensity = 0.05
    
    # Calculate turbulence values
    if field_name == "k":
        # Turbulent kinetic energy
        k_value = 1.5 * (velocity * turb_intensity) ** 2
        field_value = k_value
        dimensions = "[0 2 -2 0 0 0 0]"
    elif field_name == "omega":
        # Specific dissipation rate
        k_value = 1.5 * (velocity * turb_intensity) ** 2
        omega_value = k_value ** 0.5 / (0.09 ** 0.25 * char_length * 0.07)
        field_value = omega_value
        dimensions = "[0 0 -1 0 0 0 0]"
    elif field_name == "nut":
        # Turbulent viscosity
        field_value = 1e-5
        dimensions = "[0 2 -1 0 0 0 0]"
    else:
        field_value = 0.0
        dimensions = "[0 0 0 0 0 0 0]"
    
    # Base turbulence field structure
    turbulence_field = {
        "dimensions": dimensions,
        "internalField": f"uniform {field_value}",
        "boundaryField": {}
    }
    
    # Add STL surface boundary conditions
    for surface in stl_surfaces:
        region_name = f"stl_{surface['name']}"
        bc_info = surface["recommended_bc"]
        
        if bc_info.get("description") == "Velocity inlet":
            # Inlet surface
            turbulence_field["boundaryField"][region_name] = {
                "type": "fixedValue",
                "value": f"uniform {field_value}"
            }
        elif bc_info.get("description") == "Pressure outlet":
            # Outlet surface
            turbulence_field["boundaryField"][region_name] = {
                "type": "zeroGradient"
            }
        else:
            # Wall surface
            if field_name == "k":
                turbulence_field["boundaryField"][region_name] = {
                    "type": "kqRWallFunction",
                    "value": f"uniform {field_value}"
                }
            elif field_name == "omega":
                turbulence_field["boundaryField"][region_name] = {
                    "type": "omegaWallFunction",
                    "value": f"uniform {field_value}"
                }
            elif field_name == "nut":
                turbulence_field["boundaryField"][region_name] = {
                    "type": "nutkWallFunction",
                    "value": "uniform 0"
                }
    
    # Add domain boundary conditions for external flow
    if is_external_flow:
        turbulence_field["boundaryField"].update({
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {field_value}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            }
        })
    
    return turbulence_field


def generate_stl_temperature_field(
    parsed_params: Dict[str, Any], 
    geometry_info: Dict[str, Any], 
    mesh_config: Dict[str, Any],
    stl_surfaces: List[Dict[str, Any]],
    is_external_flow: bool
) -> Dict[str, Any]:
    """Generate temperature field for STL geometry."""
    
    # Extract temperature parameters
    temperature = parsed_params.get("temperature", 293.15)  # Default 20°C
    
    # Base temperature field structure
    temperature_field = {
        "dimensions": "[0 0 0 1 0 0 0]",
        "internalField": f"uniform {temperature}",
        "boundaryField": {}
    }
    
    # Add STL surface boundary conditions
    for surface in stl_surfaces:
        region_name = f"stl_{surface['name']}"
        bc_info = surface["recommended_bc"]
        
        if bc_info.get("description") == "Velocity inlet":
            # Inlet surface
            temperature_field["boundaryField"][region_name] = {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            }
        elif bc_info.get("description") == "Pressure outlet":
            # Outlet surface
            temperature_field["boundaryField"][region_name] = {
                "type": "zeroGradient"
            }
        else:
            # Wall surface - can be isothermal or adiabatic
            temperature_field["boundaryField"][region_name] = {
                "type": "zeroGradient"  # Adiabatic wall
            }
    
    # Add domain boundary conditions for external flow
    if is_external_flow:
        temperature_field["boundaryField"].update({
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {temperature}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "sides": {
                "type": "zeroGradient"
            },
            "top": {
                "type": "zeroGradient"
            },
            "bottom": {
                "type": "zeroGradient"
            }
        })
    
    return temperature_field


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
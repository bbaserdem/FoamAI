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
            
            # Look for patch name (valid C++ identifier on its own line)
            if (line and not line.startswith('//') and not line.startswith('/*') and 
                re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', line) and line not in ['FoamFile']):
                
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
        },
        GeometryType.CUSTOM: {
            # STL geometries - external flow around custom geometry
            "inlet": ["inlet"],
            "outlet": ["outlet"],
            "walls": ["top", "bottom", "front", "back"],  # Map walls to symmetry/farfield patches
            "farfield": ["top", "bottom", "front", "back"],  # Alternative mapping for farfield
            "geometry": ["surface_747_400", "stl_surface"],  # STL surface patches (wall treatment)
            # Handle common STL surface names
            "stl_surface": ["surface_747_400", "stl_surface", "geometry", "aircraft", "wing", "body"]
        }
    }
    
    mapping = patch_mappings.get(geometry_type, {})
    mapped_conditions = {}
    
    logger.info(f"Mapping boundary conditions for {geometry_type} with patches: {actual_patches}")
    
    # For custom geometries, dynamically add STL surface patches
    if geometry_type == GeometryType.CUSTOM:
        # Find STL surface patches (usually start with "surface_" or have "wall" type)
        stl_patches = []
        if case_directory:
            patches_info = read_mesh_patches_with_types(case_directory)
            for patch_info in patches_info:
                patch_name = patch_info['name']
                patch_type = patch_info['type']
                # Look for wall patches or patches starting with "surface_"
                if patch_type == 'wall' or patch_name.startswith('surface_'):
                    stl_patches.append(patch_name)
        
        # Add STL surface patches to mapping
        if stl_patches:
            mapping["stl_surface"] = stl_patches
            mapping["geometry"] = stl_patches
            logger.info(f"Added STL surface patches to mapping: {stl_patches}")
    
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
    """Generate boundary conditions with intelligent patch mapping."""
    
    # First, generate standard boundary conditions
    boundary_conditions = generate_boundary_conditions(parsed_params, geometry_info, mesh_config)
    
    # Check if we can read actual mesh patches (post-mesh generation)
    case_directory = state.get("case_directory")
    if case_directory and Path(case_directory).exists():
        actual_patches = read_mesh_patches(Path(case_directory))
        
        if actual_patches:
            geometry_type = geometry_info.get("type")
            
            # Map boundary conditions to actual patches
            mapped_conditions = map_boundary_conditions_to_patches(
                boundary_conditions, actual_patches, geometry_type
            )
            
            # For complex solvers, enhance with AI boundary conditions
            solver_info = state.get("solver_settings", {})
            solver_type = solver_info.get("solver_type")
            
            if solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.CHT_MULTI_REGION_FOAM, SolverType.REACTING_FOAM]:
                logger.info(f"Enhancing boundary conditions with AI for {solver_type}")
                
                ai_conditions = get_ai_boundary_conditions(
                    solver_type, geometry_info, parsed_params, actual_patches
                )
                
                if ai_conditions:
                    # Merge AI-generated conditions with mapped conditions
                    mapped_conditions = merge_ai_boundary_conditions(
                        mapped_conditions, ai_conditions, actual_patches
                    )
            
            return mapped_conditions
    
    return boundary_conditions


def merge_ai_boundary_conditions(
    existing_conditions: Dict[str, Any],
    ai_conditions: Dict[str, Dict[str, Any]], 
    actual_patches: List[str]
) -> Dict[str, Any]:
    """Merge AI-generated boundary conditions with existing ones."""
    
    # For each field in existing conditions
    for field_name, field_data in existing_conditions.items():
        if "boundaryField" not in field_data:
            continue
            
        # Update boundary conditions based on AI recommendations
        for patch_name in actual_patches:
            if patch_name in ai_conditions and field_name in ai_conditions[patch_name]:
                ai_bc = ai_conditions[patch_name][field_name]
                
                # Update the boundary condition for this patch and field
                if patch_name in field_data["boundaryField"]:
                    existing_bc = field_data["boundaryField"][patch_name]
                    
                    # Merge AI recommendations with existing structure
                    updated_bc = {**existing_bc, **ai_bc}
                    field_data["boundaryField"][patch_name] = updated_bc
                    
                    logger.info(f"Updated {field_name}.{patch_name} with AI boundary condition: {ai_bc}")
    
    return existing_conditions


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
    # Temperature is required for compressible flows, heat transfer, and reacting flows
    # Check for temperature-related keywords in the original prompt
    original_prompt = parsed_params.get("original_prompt", "").lower()
    
    has_temperature_keywords = any(keyword in original_prompt for keyword in [
        "temperature", "heat", "thermal", "compressible", "high-speed", "mach", 
        "combustion", "flame", "reaction", "burning", "ignition", "conjugate"
    ])
    
    velocity = parsed_params.get("velocity", 1.0)
    high_speed = velocity and velocity > 50  # High speed indicates compressible flow (lowered threshold)
    
    needs_temperature = (
        parsed_params.get("temperature") is not None or
        has_temperature_keywords or
        high_speed or
        parsed_params.get("is_compressible", False) or 
        parsed_params.get("has_heat_transfer", False) or
        parsed_params.get("has_reactive_flow", False)
    )
    
    logger.info(f"Temperature detection: prompt='{original_prompt}', velocity={velocity}, high_speed={high_speed}, keywords={has_temperature_keywords}, needs_temperature={needs_temperature}")
    
    if needs_temperature:
        boundary_conditions["T"] = generate_temperature_field(parsed_params, geometry_info, mesh_config)
        logger.info(f"Generated temperature field for geometry {geometry_info.get('type')}")
    
    return boundary_conditions


def generate_velocity_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate velocity field (U)."""
    velocity = parsed_params.get("velocity", None)
    
    # If velocity is not provided but Reynolds number is, calculate velocity
    if velocity is None and "reynolds_number" in parsed_params and parsed_params["reynolds_number"] is not None:
        reynolds_number = parsed_params["reynolds_number"]
        density = parsed_params.get("density", 1.225)  # kg/m³
        viscosity = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
        
        # Get characteristic length based on geometry
        if geometry_info["type"] == GeometryType.CYLINDER:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.SPHERE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CUBE:
            char_length = geometry_info.get("side_length", 0.1)
        elif geometry_info["type"] == GeometryType.AIRFOIL:
            char_length = geometry_info.get("chord_length", 0.1)
        elif geometry_info["type"] == GeometryType.PIPE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CHANNEL:
            char_length = geometry_info.get("height", 0.1)
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
        logger.info(f"Calculated velocity {velocity:.3f} m/s from Reynolds number {reynolds_number}")
    
    # Ensure velocity is not None
    if velocity is None:
        logger.warning("Velocity is None and cannot be calculated from Reynolds number, using default 1.0 m/s")
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
    elif geometry_type == GeometryType.CUSTOM:
        # Custom geometry (STL files) - external flow with snappyHexMesh
        is_2d = mesh_config.get("is_2d", False)
        
        velocity_field["boundaryField"] = {
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
            },
            # STL surface patches will be mapped to noSlip by the mapping function
            "walls": {
                "type": "noSlip"
            },
            "stl_surface": {
                "type": "noSlip"  # Wall boundary on STL surface
            },
            "geometry": {
                "type": "noSlip"  # Wall boundary on STL surface
            }
        }
        
        # Add STL surface patch if we know the STL filename
        if mesh_config.get("stl_name"):
            stl_name = mesh_config["stl_name"]
            velocity_field["boundaryField"][stl_name] = {
                "type": "noSlip"  # Wall boundary on STL surface
            }
    
    return velocity_field


def generate_pressure_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate pressure field (p) boundary conditions."""
    pressure = parsed_params.get("pressure", 0.0)
    
    # For incompressible flow simulations, use gauge pressure (0) instead of absolute pressure
    # This ensures proper pressure gradients for visualization
    # Check if pressure looks like absolute pressure (atmospheric ~101325 Pa)
    if pressure > 50000:  # Anything above 50kPa is likely absolute pressure
        # Convert to gauge pressure for incompressible flow
        logger.info(f"Converting absolute pressure ({pressure} Pa) to gauge pressure (0 Pa) for incompressible flow")
        pressure = 0.0  # Use gauge pressure for incompressible flow
    
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
    elif geometry_type == GeometryType.CUSTOM:
        # Custom geometry (STL files) - external flow with snappyHexMesh
        is_2d = mesh_config.get("is_2d", False)
        
        pressure_field["boundaryField"] = {
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
            },
            # STL surface patches will be mapped to zeroGradient by the mapping function
            "walls": {
                "type": "zeroGradient"
            },
            "stl_surface": {
                "type": "zeroGradient"  # No pressure gradient at STL surface
            },
            "geometry": {
                "type": "zeroGradient"  # No pressure gradient at STL surface
            }
        }
        
        # Add STL surface patch if we know the STL filename
        if mesh_config.get("stl_name"):
            stl_name = mesh_config["stl_name"]
            pressure_field["boundaryField"][stl_name] = {
                "type": "zeroGradient"  # No pressure gradient at STL surface
            }
    
    return pressure_field


def generate_turbulent_kinetic_energy_field(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate turbulent kinetic energy field (k)."""
    velocity = parsed_params.get("velocity", None)
    
    # If velocity is not provided but Reynolds number is, calculate velocity
    if velocity is None and "reynolds_number" in parsed_params and parsed_params["reynolds_number"] is not None:
        reynolds_number = parsed_params["reynolds_number"]
        density = parsed_params.get("density", 1.225)  # kg/m³
        viscosity = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
        
        # Get characteristic length based on geometry
        if geometry_info["type"] == GeometryType.CYLINDER:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.SPHERE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CUBE:
            char_length = geometry_info.get("side_length", 0.1)
        elif geometry_info["type"] == GeometryType.AIRFOIL:
            char_length = geometry_info.get("chord_length", 0.1)
        elif geometry_info["type"] == GeometryType.PIPE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CHANNEL:
            char_length = geometry_info.get("height", 0.1)
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
    
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
    velocity = parsed_params.get("velocity", None)
    
    # If velocity is not provided but Reynolds number is, calculate velocity
    if velocity is None and "reynolds_number" in parsed_params and parsed_params["reynolds_number"] is not None:
        reynolds_number = parsed_params["reynolds_number"]
        density = parsed_params.get("density", 1.225)  # kg/m³
        viscosity = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
        
        # Get characteristic length based on geometry
        if geometry_info["type"] == GeometryType.CYLINDER:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.SPHERE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CUBE:
            char_length = geometry_info.get("side_length", 0.1)
        elif geometry_info["type"] == GeometryType.AIRFOIL:
            char_length = geometry_info.get("chord_length", 0.1)
        elif geometry_info["type"] == GeometryType.PIPE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CHANNEL:
            char_length = geometry_info.get("height", 0.1)
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
    
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
    velocity = parsed_params.get("velocity", None)
    
    # If velocity is not provided but Reynolds number is, calculate velocity
    if velocity is None and "reynolds_number" in parsed_params and parsed_params["reynolds_number"] is not None:
        reynolds_number = parsed_params["reynolds_number"]
        density = parsed_params.get("density", 1.225)  # kg/m³
        viscosity = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
        
        # Get characteristic length based on geometry
        if geometry_info["type"] == GeometryType.CYLINDER:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.SPHERE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CUBE:
            char_length = geometry_info.get("side_length", 0.1)
        elif geometry_info["type"] == GeometryType.AIRFOIL:
            char_length = geometry_info.get("chord_length", 0.1)
        elif geometry_info["type"] == GeometryType.PIPE:
            char_length = geometry_info.get("diameter", 0.1)
        elif geometry_info["type"] == GeometryType.CHANNEL:
            char_length = geometry_info.get("height", 0.1)
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
    
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
    elif geometry_type == GeometryType.CYLINDER:
        # External flow around cylinder - use snappyHexMesh patch names
        mesh_topology = mesh_config.get("mesh_topology", "structured")
        is_2d = mesh_config.get("is_2d", True)
        
        logger.info(f"Cylinder temperature field: mesh_topology={mesh_topology}, is_2d={is_2d}")
        
        if mesh_topology == "snappy":
            temp_field["boundaryField"] = {
                "cylinder": {
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
        else:
            # O-grid topology
            temp_field["boundaryField"] = {
                "cylinder": {
                    "type": "zeroGradient"
                },
                "left": {
                    "type": "fixedValue",
                    "value": f"uniform {temperature}"
                },
                "right": {
                    "type": "zeroGradient"
                },
                "up": {
                    "type": "zeroGradient"
                },
                "down": {
                    "type": "zeroGradient"
                },
                "front": {
                    "type": "empty"
                },
                "back": {
                    "type": "empty"
                }
            }
        
        logger.info(f"Generated cylinder temperature field with patches: {list(temp_field['boundaryField'].keys())}")
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
    elif geometry_type == GeometryType.CUSTOM:
        # Custom geometry (STL files) - external flow with snappyHexMesh
        is_2d = mesh_config.get("is_2d", False)
        
        temp_field["boundaryField"] = {
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
            },
            # STL surface patches will be mapped to zeroGradient by the mapping function
            "walls": {
                "type": "zeroGradient"
            },
            "stl_surface": {
                "type": "zeroGradient"  # No temperature gradient at STL surface
            },
            "geometry": {
                "type": "zeroGradient"  # No temperature gradient at STL surface
            }
        }
    
    # Add STL surface patch if we know the STL filename
    if mesh_config.get("stl_name"):
        stl_name = mesh_config["stl_name"]
        temp_field["boundaryField"][stl_name] = {
            "type": "zeroGradient"  # No temperature gradient at STL surface
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
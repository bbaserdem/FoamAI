"""Case Writer Agent - Assembles complete OpenFOAM case directories."""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from .state import CFDState, CFDStep


def case_writer_agent(state: CFDState) -> CFDState:
    """
    Case Writer Agent.
    
    Assembles complete OpenFOAM case directory structure from generated
    mesh, boundary conditions, and solver configurations.
    """
    try:
        if state["verbose"]:
            logger.info("Case Writer: Starting case assembly")
        
        # Create case directory
        case_directory = create_case_directory(state)
        
        # Write mesh configuration
        write_mesh_files(case_directory, state)
        
        # Write boundary condition files
        write_boundary_condition_files(case_directory, state)
        
        # Write solver configuration files
        write_solver_files(case_directory, state)
        
        # Validate case completeness
        validation_result = validate_case_structure(case_directory)
        if not validation_result["valid"]:
            logger.warning(f"Case validation issues: {validation_result['warnings']}")
            return {
                **state,
                "errors": state["errors"] + validation_result["errors"],
                "warnings": state["warnings"] + validation_result["warnings"]
            }
        
        if state["verbose"]:
            logger.info(f"Case Writer: Case assembled at {case_directory}")
        
        return {
            **state,
            "case_directory": str(case_directory),
            "work_directory": str(case_directory.parent),
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Case Writer error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Case writing failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def create_case_directory(state: CFDState) -> Path:
    """Create case directory structure."""
    import sys
    sys.path.append('src')
    from foamai.config import get_settings
    
    settings = get_settings()
    settings.ensure_directories()
    
    # Generate unique case name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    geometry_type = state["geometry_info"].get("type", "unknown")
    # Convert enum to string if needed
    if hasattr(geometry_type, 'value'):
        geometry_type = geometry_type.value
    case_name = f"{timestamp}_{geometry_type}_case"
    
    case_dir = settings.get_work_dir() / case_name
    
    # Create directory structure
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "0").mkdir(exist_ok=True)
    (case_dir / "constant").mkdir(exist_ok=True)
    (case_dir / "system").mkdir(exist_ok=True)
    
    logger.info(f"Created case directory: {case_dir}")
    return case_dir


def write_mesh_files(case_directory: Path, state: CFDState) -> None:
    """Write mesh configuration files."""
    mesh_config = state["mesh_config"]
    
    # Write blockMeshDict
    blockmesh_dict = generate_blockmesh_dict(mesh_config, state)
    write_foam_dict(case_directory / "system" / "blockMeshDict", blockmesh_dict)
    
    # Write topoSet and createPatch files if needed
    if mesh_config.get("use_toposet") and mesh_config.get("geometry_type") == "cylinder":
        # Generate topoSetDict
        cylinder_info = {
            "center": mesh_config.get("cylinder_center", [1.0, 0.5, 0.05]),
            "radius": mesh_config.get("cylinder_radius", 0.05),
            "height": mesh_config.get("dimensions", {}).get("cylinder_length", 0.1)
        }
        
        toposet_dict = generate_toposet_dict(cylinder_info)
        write_foam_dict(case_directory / "system" / "topoSetDict", toposet_dict)
        
        # Generate createPatchDict
        createpatch_dict = generate_createpatch_dict(cylinder_info)
        write_foam_dict(case_directory / "system" / "createPatchDict", createpatch_dict)
        
        if state["verbose"]:
            logger.info("Case Writer: Wrote topoSetDict and createPatchDict for cylinder geometry")
    
    if state["verbose"]:
        logger.info("Case Writer: Wrote blockMeshDict")


def generate_blockmesh_dict(mesh_config: Dict[str, Any], state: CFDState) -> Dict[str, Any]:
    """Generate blockMeshDict content."""
    geometry_type = mesh_config.get("geometry_type") or state["geometry_info"]["type"]
    # Convert enum to string if needed
    if hasattr(geometry_type, 'value'):
        geometry_type = geometry_type.value
    
    dimensions = mesh_config.get("dimensions") or state["geometry_info"]["dimensions"]
    
    resolution_data = mesh_config.get("resolution", "medium")
    
    # Check if resolution is already a dictionary (from mesh generator) or a string
    if isinstance(resolution_data, dict):
        resolution = resolution_data
    else:
        # Convert resolution string to geometry-specific dictionary
        def get_resolution_for_geometry(geom_type: str, res_str: str) -> Dict[str, int]:
            base_counts = {"coarse": 20, "medium": 40, "fine": 80}
            count = base_counts.get(res_str, 40)
            
            if geom_type == "cylinder":
                return {"circumferential": count, "radial": count//2, "axial": 1}  # 1 cell for 2D
            elif geom_type == "airfoil":
                return {"chordwise": count, "normal": count//2, "spanwise": count//4}
            elif geom_type == "pipe":
                return {"circumferential": count, "radial": count//2, "axial": count*2}
            elif geom_type == "channel":
                return {"x": count, "y": count, "z": count}
            elif geom_type == "sphere":
                return {"circumferential": count, "radial": count//2, "meridional": count//2}
            else:
                return {"x": count, "y": count, "z": count}
        
        resolution = get_resolution_for_geometry(geometry_type, resolution_data)
    
    if geometry_type == "cylinder":
        return generate_cylinder_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "airfoil":
        return generate_airfoil_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "pipe":
        return generate_pipe_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "channel":
        return generate_channel_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "sphere":
        return generate_sphere_blockmesh_dict(dimensions, resolution)
    else:
        raise ValueError(f"Unsupported geometry type for blockMesh: {geometry_type}")


def generate_cylinder_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for cylinder geometry."""
    # Handle both mesh generator format (cylinder_diameter) and case writer format (diameter)
    diameter = dimensions.get("diameter") or dimensions.get("cylinder_diameter", 0.1)
    thickness = dimensions.get("cylinder_length", 0.1)  # Use cylinder_length as thickness for 2D
    
    # Create rectangular domain that will contain the cylinder
    radius = diameter / 2.0
    domain_length = diameter * 20  # 20x cylinder upstream/downstream
    domain_height = diameter * 10  # 10x cylinder height
    
    # Store cylinder info for later use by topoSet
    cylinder_info = {
        "center": [domain_length * 0.3, domain_height * 0.5, thickness * 0.5],
        "radius": radius,
        "height": thickness
    }
    
    # Simple rectangular channel - we'll add cylinder via topoSet later
    return {
        "scale": 1,
        "vertices": [
            f"(0 0 0)",
            f"({domain_length} 0 0)",
            f"({domain_length} {domain_height} 0)",
            f"(0 {domain_height} 0)",
            f"(0 0 {thickness})",
            f"({domain_length} 0 {thickness})",
            f"({domain_length} {domain_height} {thickness})",
            f"(0 {domain_height} {thickness})"
        ],
        "blocks": [
            f"hex (0 1 2 3 4 5 6 7) ({resolution.get('circumferential', 32)} {resolution.get('radial', 20)} 1) simpleGrading (1 1 1)"
        ],
        "edges": [],
        "boundary": {
            "inlet": {
                "type": "patch",
                "faces": [
                    "(0 4 7 3)"
                ]
            },
            "outlet": {
                "type": "patch", 
                "faces": [
                    "(1 2 6 5)"
                ]
            },
            "walls": {
                "type": "wall",
                "faces": [
                    "(0 1 5 4)",  # bottom
                    "(3 7 6 2)"   # top
                ]
            },
            "sides": {
                "type": "empty",
                "faces": [
                    "(0 3 2 1)",  # front
                    "(4 5 6 7)"   # back
                ]
            }
        },
        "mergePatchPairs": [],
        "_cylinder_info": cylinder_info  # Internal use for topoSet
    }


def generate_airfoil_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for airfoil geometry."""
    chord = dimensions.get("chord", 0.1)  # Default chord
    span = dimensions.get("span", 1.0)  # Default span
    # Calculate domain dimensions based on chord
    domain_length = dimensions.get("domain_length", chord * 30)  # 30x chord
    domain_height = dimensions.get("domain_height", chord * 20)  # 20x chord
    
    return {
        "convertToMeters": 1,
        "vertices": generate_airfoil_vertices(chord, span, domain_length, domain_height),
        "blocks": generate_airfoil_blocks_detailed(resolution),
        "edges": [],
        "boundary": {
            "inlet": {
                "type": "patch",
                "faces": ["(inlet faces)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(outlet faces)"]
            },
            "airfoil": {
                "type": "wall",
                "faces": ["(airfoil faces)"]
            },
            "farfield": {
                "type": "patch",
                "faces": ["(farfield faces)"]
            },
            "sides": {
                "type": "empty",
                "faces": ["(2D faces)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_pipe_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for pipe geometry."""
    diameter = dimensions["diameter"]
    length = dimensions["length"]
    
    return {
        "convertToMeters": 1,
        "vertices": generate_pipe_vertices(diameter, length),
        "blocks": generate_pipe_blocks_detailed(resolution),
        "edges": [],
        "boundary": {
            "inlet": {
                "type": "patch",
                "faces": ["(inlet faces)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(outlet faces)"]
            },
            "walls": {
                "type": "wall",
                "faces": ["(pipe wall faces)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_channel_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for channel geometry."""
    width = dimensions["width"]
    height = dimensions["height"] 
    length = dimensions["length"]
    
    # Determine if this is 2D or 3D based on spanwise resolution
    is_2d = resolution.get('spanwise', 1) == 1
    sides_type = "empty" if is_2d else "symmetry"
    
    # For channels, ensure Z-dimension (spanwise) is small for proper aspect ratio
    # Use the smaller of width or 0.1m for the Z-dimension
    z_dimension = min(width, 0.1)
    
    return {
        "convertToMeters": 1,
        "vertices": [
            f"(0 0 0)",
            f"({length} 0 0)",
            f"({length} {height} 0)",
            f"(0 {height} 0)",
            f"(0 0 {z_dimension})",
            f"({length} 0 {z_dimension})",
            f"({length} {height} {z_dimension})",
            f"(0 {height} {z_dimension})"
        ],
        "blocks": [
            f"hex (0 1 2 3 4 5 6 7) ({resolution['streamwise']} {resolution['normal']} {resolution['spanwise']}) simpleGrading (1 1 1)"
        ],
        "edges": [],
        "boundary": {
            "inlet": {
                "type": "patch",
                "faces": ["(0 4 7 3)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(1 2 6 5)"]
            },
            "walls": {
                "type": "wall",
                "faces": ["(0 1 5 4)", "(3 7 6 2)"]
            },
            "sides": {
                "type": sides_type, 
                "faces": ["(0 3 2 1)", "(4 5 6 7)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_sphere_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for sphere geometry."""
    diameter = dimensions["diameter"]
    domain_size = dimensions.get("domain_size", diameter * 10)  # 10x diameter
    
    return {
        "convertToMeters": 1,
        "vertices": generate_sphere_vertices(diameter, domain_size),
        "blocks": generate_sphere_blocks_detailed(resolution),
        "edges": [],
        "boundary": {
            "inlet": {
                "type": "patch",
                "faces": ["(inlet faces)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(outlet faces)"]
            },
            "sphere": {
                "type": "wall",
                "faces": ["(sphere faces)"]
            },
            "farfield": {
                "type": "patch",
                "faces": ["(farfield faces)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_airfoil_vertices(chord: float, span: float, domain_length: float, domain_height: float) -> list:
    """Generate vertices for airfoil geometry (simplified)."""
    return [
        f"(-{domain_length*0.3} -{domain_height/2} 0)",
        f"({domain_length*0.7} -{domain_height/2} 0)",
        f"({domain_length*0.7} {domain_height/2} 0)",
        f"(-{domain_length*0.3} {domain_height/2} 0)",
        f"(-{domain_length*0.3} -{domain_height/2} {span})",
        f"({domain_length*0.7} -{domain_height/2} {span})",
        f"({domain_length*0.7} {domain_height/2} {span})",
        f"(-{domain_length*0.3} {domain_height/2} {span})"
    ]


def generate_pipe_vertices(diameter: float, length: float) -> list:
    """Generate vertices for pipe geometry (simplified)."""
    radius = diameter / 2
    return [
        f"(0 -{radius} -{radius})",
        f"({length} -{radius} -{radius})",
        f"({length} {radius} -{radius})",
        f"(0 {radius} -{radius})",
        f"(0 -{radius} {radius})",
        f"({length} -{radius} {radius})",
        f"({length} {radius} {radius})",
        f"(0 {radius} {radius})"
    ]


def generate_sphere_vertices(diameter: float, domain_size: float) -> list:
    """Generate vertices for sphere geometry (simplified)."""
    return [
        f"(-{domain_size/2} -{domain_size/2} -{domain_size/2})",
        f"({domain_size/2} -{domain_size/2} -{domain_size/2})",
        f"({domain_size/2} {domain_size/2} -{domain_size/2})",
        f"(-{domain_size/2} {domain_size/2} -{domain_size/2})",
        f"(-{domain_size/2} -{domain_size/2} {domain_size/2})",
        f"({domain_size/2} -{domain_size/2} {domain_size/2})",
        f"({domain_size/2} {domain_size/2} {domain_size/2})",
        f"(-{domain_size/2} {domain_size/2} {domain_size/2})"
    ]


def generate_airfoil_blocks_detailed(resolution: Dict[str, int]) -> list:
    """Generate detailed blocks for airfoil geometry."""
    return [f"hex (0 1 2 3 4 5 6 7) ({resolution['chordwise']} {resolution['normal']} {resolution['spanwise']}) simpleGrading (1 1 1)"]


def generate_pipe_blocks_detailed(resolution: Dict[str, int]) -> list:
    """Generate detailed blocks for pipe geometry."""
    return [f"hex (0 1 2 3 4 5 6 7) ({resolution['circumferential']} {resolution['radial']} {resolution['axial']}) simpleGrading (1 1 1)"]


def generate_sphere_blocks_detailed(resolution: Dict[str, int]) -> list:
    """Generate detailed blocks for sphere geometry."""
    return [f"hex (0 1 2 3 4 5 6 7) ({resolution['circumferential']} {resolution['radial']} {resolution['meridional']}) simpleGrading (1 1 1)"]


def write_boundary_condition_files(case_directory: Path, state: CFDState) -> None:
    """Write boundary condition files to 0/ directory."""
    boundary_conditions = state["boundary_conditions"]
    zero_dir = case_directory / "0"
    
    for field_name, field_config in boundary_conditions.items():
        write_foam_dict(zero_dir / field_name, field_config)
    
    if state["verbose"]:
        logger.info(f"Case Writer: Wrote {len(boundary_conditions)} boundary condition files")


def write_solver_files(case_directory: Path, state: CFDState) -> None:
    """Write solver configuration files."""
    solver_settings = state["solver_settings"]
    
    # Write controlDict
    write_foam_dict(case_directory / "system" / "controlDict", solver_settings["controlDict"])
    
    # Write fvSchemes
    write_foam_dict(case_directory / "system" / "fvSchemes", solver_settings["fvSchemes"])
    
    # Write fvSolution
    write_foam_dict(case_directory / "system" / "fvSolution", solver_settings["fvSolution"])
    
    # Write turbulenceProperties
    write_foam_dict(case_directory / "constant" / "turbulenceProperties", solver_settings["turbulenceProperties"])
    
    # Write transportProperties
    write_foam_dict(case_directory / "constant" / "transportProperties", solver_settings["transportProperties"])
    
    if state["verbose"]:
        logger.info("Case Writer: Wrote solver configuration files")


def generate_allrun_script(state: CFDState) -> str:
    """Generate Allrun script for the case."""
    solver = state["solver_settings"]["solver"]
    mesh_config = state["mesh_config"]
    
    script = f"""#!/bin/sh
cd "${{0%/*}}" || exit                                # Run from this directory
. ${{WM_PROJECT_DIR:?}}/bin/tools/RunFunctions        # Tutorial run functions
#------------------------------------------------------------------------------

echo "Running {solver} case"

# Mesh generation
echo "Generating mesh..."
runApplication blockMesh

# Check mesh quality
echo "Checking mesh..."
runApplication checkMesh

# Run solver
echo "Running solver {solver}..."
runApplication {solver}

echo "Case completed successfully"

#------------------------------------------------------------------------------
"""
    return script


def write_foam_dict(file_path: Path, content: Dict[str, Any]) -> None:
    """Write OpenFOAM dictionary file."""
    with open(file_path, "w") as f:
        f.write(format_foam_dict(content, file_path.name))


def format_foam_dict(content: Dict[str, Any], file_name: str) -> str:
    """Format dictionary content as OpenFOAM file."""
    header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2312                                 |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      {file_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

"""
    
    body = format_dict_content(content, 0)
    footer = "\n// ************************************************************************* //\n"
    
    return header + body + footer


def format_dict_content(content: Any, indent_level: int = 0) -> str:
    """Recursively format dictionary content."""
    indent = "    " * indent_level
    
    if isinstance(content, dict):
        result = ""
        for key, value in content.items():
            # Skip internal keys like _cylinder_info
            if key.startswith("_"):
                continue
                
            # Convert enum keys to strings if needed
            if hasattr(key, 'value'):
                key = key.value
            
            if isinstance(value, dict):
                # Special handling for boundary in blockMeshDict - use parentheses
                if key == "boundary":
                    result += f"{indent}{key}\n{indent}(\n"
                    result += format_dict_content(value, indent_level + 1)
                    result += f"{indent});\n\n"
                # Special handling for nested dictionaries in topoSet actions
                elif "sourceInfo" in value:
                    result += f"{indent}{{\n"
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict):
                            result += f"{indent}    {sub_key}\n{indent}    {{\n"
                            for info_key, info_value in sub_value.items():
                                if isinstance(info_value, (list, tuple)) and len(info_value) == 3:
                                    # Format as vector
                                    result += f"{indent}        {info_key}    ({info_value[0]} {info_value[1]} {info_value[2]});\n"
                                else:
                                    result += f"{indent}        {info_key}    {info_value};\n"
                            result += f"{indent}    }}\n"
                        else:
                            result += f"{indent}    {sub_key}    {sub_value};\n"
                    result += f"{indent}}}\n"
                else:
                    result += f"{indent}{key}\n{indent}{{\n"
                    result += format_dict_content(value, indent_level + 1)
                    result += f"{indent}}}\n\n"
            elif isinstance(value, list):
                if key == "actions":
                    # Special handling for topoSet actions
                    result += f"{indent}{key}\n{indent}(\n"
                    for action in value:
                        result += f"{indent}    {{\n"
                        for action_key, action_value in action.items():
                            if isinstance(action_value, dict):
                                result += f"{indent}        {action_key}\n{indent}        {{\n"
                                for info_key, info_value in action_value.items():
                                    if isinstance(info_value, str) and info_value.startswith("("):
                                        # Already formatted as OpenFOAM vector
                                        result += f"{indent}            {info_key}    {info_value};\n"
                                    else:
                                        result += f"{indent}            {info_key}    {info_value};\n"
                                result += f"{indent}        }}\n"
                            else:
                                result += f"{indent}        {action_key}    {action_value};\n"
                        result += f"{indent}    }}\n"
                    result += f"{indent});\n\n"
                else:
                    result += f"{indent}{key}\n{indent}(\n"
                    for item in value:
                        # Handle dictionary items in arrays (like patches)
                        if isinstance(item, dict):
                            result += f"{indent}    {{\n"
                            for item_key, item_value in item.items():
                                if isinstance(item_value, dict):
                                    result += f"{indent}        {item_key}\n{indent}        {{\n"
                                    for sub_key, sub_value in item_value.items():
                                        result += f"{indent}            {sub_key}    {sub_value};\n"
                                    result += f"{indent}        }}\n"
                                else:
                                    result += f"{indent}        {item_key}    {item_value};\n"
                            result += f"{indent}    }}\n"
                        else:
                            # Convert enum values to strings if needed
                            if hasattr(item, 'value'):
                                item = item.value
                            result += f"{indent}    {item}\n"
                    result += f"{indent});\n\n"
            else:
                # Convert enum values to strings if needed
                if hasattr(value, 'value'):
                    value = value.value
                result += f"{indent}{key}    {value};\n"
        return result
    else:
        # Convert enum values to strings if needed
        if hasattr(content, 'value'):
            content = content.value
        return f"{indent}{content}\n"


def validate_case_structure(case_directory: Path) -> Dict[str, Any]:
    """Validate OpenFOAM case directory structure."""
    errors = []
    warnings = []
    
    # Check required directories
    required_dirs = ["0", "constant", "system"]
    for dir_name in required_dirs:
        if not (case_directory / dir_name).exists():
            errors.append(f"Missing required directory: {dir_name}")
    
    # Check required system files
    required_system_files = ["controlDict", "fvSchemes", "fvSolution", "blockMeshDict"]
    for file_name in required_system_files:
        if not (case_directory / "system" / file_name).exists():
            errors.append(f"Missing required system file: {file_name}")
    
    # Check required constant files
    required_constant_files = ["turbulenceProperties", "transportProperties"]
    for file_name in required_constant_files:
        if not (case_directory / "constant" / file_name).exists():
            errors.append(f"Missing required constant file: {file_name}")
    
    # Check boundary condition files
    zero_dir = case_directory / "0"
    if zero_dir.exists():
        bc_files = list(zero_dir.glob("*"))
        if len(bc_files) == 0:
            errors.append("No boundary condition files found in 0/ directory")
        elif len(bc_files) < 2:
            warnings.append("Very few boundary condition files - check completeness")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def generate_toposet_dict(cylinder_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate topoSetDict for creating cylinder geometry."""
    return {
        "actions": [
            {
                "name": "cylinderCells",
                "type": "cellSet",
                "action": "new",
                "source": "cylinderToCell",
                "sourceInfo": {
                    "p1": f"({cylinder_info['center'][0]} {cylinder_info['center'][1]} 0)",
                    "p2": f"({cylinder_info['center'][0]} {cylinder_info['center'][1]} {cylinder_info['height']})",
                    "radius": cylinder_info['radius']
                }
            },
            {
                "name": "cylinderFaces",
                "type": "faceSet",
                "action": "new",
                "source": "cellToFace",
                "sourceInfo": {
                    "set": "cylinderCells",
                    "option": "both"
                }
            }
        ]
    }


def generate_createpatch_dict(cylinder_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate createPatchDict for creating cylinder boundary."""
    return {
        "pointSync": "false",
        "patches": [
            {
                "name": "cylinder",
                "patchInfo": {
                    "type": "wall"
                },
                "constructFrom": "set",
                "set": "cylinderFaces"
            }
        ],
        "removeEmptyPatches": "true"
    } 
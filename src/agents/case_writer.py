"""Case Writer Agent - Assembles complete OpenFOAM case directories."""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
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
        
        # Update state with case directory for boundary condition mapping
        updated_state = {**state, "case_directory": str(case_directory)}
        
        # Write boundary condition files with intelligent mapping
        write_boundary_condition_files_with_mapping(case_directory, updated_state)
        
        # Write solver configuration files
        write_solver_files(case_directory, updated_state)
        
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
            **updated_state,
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
    mesh_type = mesh_config.get("type", "blockMesh")
    
    if mesh_type == "snappyHexMesh":
        # For snappyHexMesh, we need to:
        # 1. Write a background blockMeshDict
        # 2. Write snappyHexMeshDict
        # 3. Copy STL files if custom geometry is used
        
        # Handle STL file copying for custom geometry
        if mesh_config.get("is_custom_geometry") and mesh_config.get("stl_file"):
            copy_stl_file_to_case(case_directory, mesh_config, state)
        
        # Write background mesh
        background_mesh = mesh_config.get("background_mesh", {})
        blockmesh_dict = generate_background_blockmesh_dict(background_mesh)
        write_foam_dict(case_directory / "system" / "blockMeshDict", blockmesh_dict)
        
        # Write snappyHexMeshDict
        snappy_dict = generate_snappyhexmesh_dict(mesh_config, state)
        write_foam_dict(case_directory / "system" / "snappyHexMeshDict", snappy_dict)
        
        # For STL files, also generate surface feature extraction dict
        if mesh_config.get("is_custom_geometry") and mesh_config.get("stl_file"):
            surface_feature_dict = generate_surface_feature_extract_dict(mesh_config)
            write_foam_dict(case_directory / "system" / "surfaceFeatureExtractDict", surface_feature_dict)
        
        if state["verbose"]:
            logger.info("Case Writer: Wrote blockMeshDict (background) and snappyHexMeshDict")
            if mesh_config.get("stl_file"):
                logger.info(f"Case Writer: Copied STL file for custom geometry")
                logger.info(f"Case Writer: Wrote surfaceFeatureExtractDict for STL processing")
    else:
        # Original blockMesh approach
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


def generate_surface_feature_extract_dict(mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate surfaceFeatureExtractDict for STL surface feature extraction."""
    stl_name = mesh_config.get("stl_name", "stl_surface")
    stl_file_path = mesh_config.get("stl_file_case_path", "constant/triSurface/geometry.stl")
    
    # Clean the file path
    stl_file_path = stl_file_path.replace("\\", "/").lstrip("/")
    
    surface_dict = {
        stl_name: {
            "extractionMethod": "extractFromSurface",
            "extractFromSurfaceCoeffs": {
                "includedAngle": 150  # Degrees - features with angles greater than this will be extracted
            },
            "subsetFeatures": {
                "nonManifoldEdges": "yes",
                "openEdges": "yes"
            },
            "writeFeatureEdgeMesh": "yes"
        }
    }
    
    return surface_dict


def copy_stl_file_to_case(case_directory: Path, mesh_config: Dict[str, Any], state: CFDState) -> None:
    """Copy STL file to the case directory for snappyHexMesh."""
    import shutil
    import subprocess
    
    stl_file = mesh_config.get("stl_file")
    if not stl_file:
        return
    
    stl_source = Path(stl_file)
    if not stl_source.exists():
        logger.error(f"STL file not found: {stl_file}")
        return
    
    # Validate STL file
    if not validate_stl_file(stl_source):
        logger.warning(f"STL file validation failed for {stl_file}. Proceeding anyway, but mesh generation might fail.")
    
    # Create constant/triSurface directory for STL files
    trisurface_dir = case_directory / "constant" / "triSurface"
    trisurface_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy STL file to triSurface directory
    stl_dest = trisurface_dir / stl_source.name
    shutil.copy2(stl_source, stl_dest)
    
    # Apply rotation if requested
    rotation_info = mesh_config.get("rotation_info", {})
    if rotation_info.get("rotate", False):
        apply_stl_rotation(case_directory, stl_dest, rotation_info, state)
    
    # Update mesh config with the new path
    mesh_config["stl_file_case_path"] = f"constant/triSurface/{stl_source.name}"
    
    if state["verbose"]:
        logger.info(f"Copied STL file from {stl_source} to {stl_dest}")


def calculate_stl_center(stl_path: Path) -> list:
    """Calculate the center of an STL file."""
    import struct
    import numpy as np
    
    vertices = []
    
    with open(stl_path, 'rb') as f:
        header = f.read(80)
        
    if header.startswith(b'solid'):
        # ASCII STL
        with open(stl_path, 'r') as f:
            for line in f:
                if line.strip().startswith('vertex'):
                    parts = line.split()
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    vertices.append([x, y, z])
    else:
        # Binary STL  
        with open(stl_path, 'rb') as f:
            f.read(80)  # Skip header
            num_triangles = struct.unpack('<I', f.read(4))[0]
            
            for _ in range(num_triangles):
                data = struct.unpack('<12fH', f.read(50))
                # Extract vertices (skip normal)
                vertices.extend([data[3:6], data[6:9], data[9:12]])
    
    vertices = np.array(vertices)
    center = vertices.mean(axis=0).tolist()
    return center


def apply_stl_rotation(case_directory: Path, stl_path: Path, rotation_info: Dict[str, Any], state: CFDState) -> None:
    """Apply rotation to STL file by modifying vertices directly."""
    import math
    import struct
    import numpy as np
    
    angle_deg = rotation_info.get("rotation_angle", 0)
    axis = rotation_info.get("rotation_axis", "z").lower()
    center = rotation_info.get("rotation_center", None)
    
    if angle_deg == 0:
        return
    
    # Calculate STL center if not specified
    if center is None:
        logger.info("Calculating STL center for rotation...")
        center = calculate_stl_center(stl_path)
        logger.info(f"Using STL center: {center}")
    
    logger.info(f"Applying rotation: {angle_deg}° around {axis}-axis at center {center}")
    
    # Convert angle to radians
    angle_rad = math.radians(angle_deg)
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)
    
    # Create rotation matrix based on axis
    if axis == "x":
        rotation_matrix = np.array([
            [1, 0, 0],
            [0, cos_angle, -sin_angle],
            [0, sin_angle, cos_angle]
        ])
    elif axis == "y":
        rotation_matrix = np.array([
            [cos_angle, 0, sin_angle],
            [0, 1, 0],
            [-sin_angle, 0, cos_angle]
        ])
    else:  # z axis (default)
        rotation_matrix = np.array([
            [cos_angle, -sin_angle, 0],
            [sin_angle, cos_angle, 0],
            [0, 0, 1]
        ])
    
    # Read and rotate STL file
    rotated_path = stl_path.parent / (stl_path.stem + "_rotated" + stl_path.suffix)
    
    try:
        # Check if it's ASCII or binary STL
        with open(stl_path, 'rb') as f:
            header = f.read(80)
            
        if header.startswith(b'solid'):
            # ASCII STL
            rotate_ascii_stl(stl_path, rotated_path, rotation_matrix, center)
        else:
            # Binary STL
            rotate_binary_stl(stl_path, rotated_path, rotation_matrix, center)
        
        # Replace original with rotated version
        stl_path.unlink()
        rotated_path.rename(stl_path)
        
        if state["verbose"]:
            logger.info(f"Successfully rotated STL file: {angle_deg}° around {axis}-axis")
        
    except Exception as e:
        logger.error(f"Failed to rotate STL file: {e}")
        logger.warning("Proceeding without rotation")
        if rotated_path.exists():
            rotated_path.unlink()


def rotate_ascii_stl(input_path: Path, output_path: Path, rotation_matrix, center: list) -> None:
    """Rotate an ASCII STL file."""
    import numpy as np
    
    center_vec = np.array(center)
    
    with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
        for line in infile:
            line = line.strip()
            
            if line.startswith('vertex'):
                # Parse vertex coordinates
                parts = line.split()
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                vertex = np.array([x, y, z])
                
                # Translate to origin, rotate, translate back
                vertex = vertex - center_vec
                vertex = rotation_matrix @ vertex
                vertex = vertex + center_vec
                
                # Write rotated vertex
                outfile.write(f"      vertex {vertex[0]:.6e} {vertex[1]:.6e} {vertex[2]:.6e}\n")
                
            elif line.startswith('facet normal'):
                # Parse normal vector
                parts = line.split()
                nx, ny, nz = float(parts[2]), float(parts[3]), float(parts[4])
                normal = np.array([nx, ny, nz])
                
                # Rotate normal (no translation needed for normals)
                normal = rotation_matrix @ normal
                
                # Normalize to ensure unit vector
                normal = normal / np.linalg.norm(normal)
                
                # Write rotated normal
                outfile.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
                
            else:
                # Copy other lines as-is
                outfile.write(line + '\n')


def rotate_binary_stl(input_path: Path, output_path: Path, rotation_matrix, center: list) -> None:
    """Rotate a binary STL file."""
    import struct
    import numpy as np
    
    center_vec = np.array(center)
    
    with open(input_path, 'rb') as infile:
        # Read header
        header = infile.read(80)
        
        # Read number of triangles
        num_triangles = struct.unpack('<I', infile.read(4))[0]
        
        with open(output_path, 'wb') as outfile:
            # Write header
            outfile.write(header)
            
            # Write number of triangles
            outfile.write(struct.pack('<I', num_triangles))
            
            # Process each triangle
            for _ in range(num_triangles):
                # Read normal and vertices
                data = struct.unpack('<12fH', infile.read(50))
                
                # Extract normal
                normal = np.array(data[0:3])
                
                # Extract vertices
                v1 = np.array(data[3:6])
                v2 = np.array(data[6:9])
                v3 = np.array(data[9:12])
                
                # Extract attribute byte count
                attr = data[12]
                
                # Rotate normal
                normal = rotation_matrix @ normal
                normal = normal / np.linalg.norm(normal)  # Normalize
                
                # Rotate vertices (translate to origin, rotate, translate back)
                v1 = rotation_matrix @ (v1 - center_vec) + center_vec
                v2 = rotation_matrix @ (v2 - center_vec) + center_vec
                v3 = rotation_matrix @ (v3 - center_vec) + center_vec
                
                # Pack and write rotated data
                rotated_data = struct.pack('<12fH',
                    normal[0], normal[1], normal[2],
                    v1[0], v1[1], v1[2],
                    v2[0], v2[1], v2[2],
                    v3[0], v3[1], v3[2],
                    attr
                )
                outfile.write(rotated_data)


def validate_stl_file(stl_path: Path) -> bool:
    """Validate STL file for basic structural integrity."""
    try:
        # Check file size (should be reasonable)
        file_size = stl_path.stat().st_size
        if file_size == 0:
            logger.error(f"STL file is empty: {stl_path}")
            return False
        
        if file_size > 500_000_000:  # 500MB limit
            logger.warning(f"STL file is very large ({file_size/1024/1024:.1f}MB): {stl_path}")
        
        # Check if it's ASCII or binary STL
        with open(stl_path, 'rb') as f:
            header = f.read(80)
            
            # Check for ASCII STL (starts with "solid")
            if header.startswith(b'solid'):
                # ASCII STL - basic validation
                with open(stl_path, 'r', encoding='utf-8', errors='ignore') as f_text:
                    content = f_text.read(1000)  # Read first 1000 characters
                    
                    # Check for required keywords
                    if 'solid' not in content or 'facet' not in content or 'normal' not in content:
                        logger.error(f"ASCII STL file missing required keywords: {stl_path}")
                        return False
                    
                    return True
            else:
                # Binary STL - check header structure
                f.seek(80)  # Skip header
                triangle_count_bytes = f.read(4)
                if len(triangle_count_bytes) != 4:
                    logger.error(f"Binary STL file has invalid triangle count: {stl_path}")
                    return False
                
                triangle_count = int.from_bytes(triangle_count_bytes, byteorder='little')
                
                if triangle_count == 0:
                    logger.error(f"Binary STL file has zero triangles: {stl_path}")
                    return False
                
                if triangle_count > 10_000_000:  # 10 million triangles
                    logger.warning(f"Binary STL file has very many triangles ({triangle_count:,}): {stl_path}")
                
                return True
    
    except Exception as e:
        logger.error(f"Error validating STL file {stl_path}: {e}")
        return False


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
            elif geom_type == "cube":
                return {"x": count, "y": count, "z": count}
            else:
                return {"x": count, "y": count, "z": count}
        
        resolution = get_resolution_for_geometry(geometry_type, resolution_data)
    
    if geometry_type == "cylinder":
        return generate_cylinder_blockmesh_dict(dimensions, resolution, mesh_config)
    elif geometry_type == "airfoil":
        return generate_airfoil_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "pipe":
        return generate_pipe_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "channel":
        return generate_channel_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "sphere":
        return generate_sphere_blockmesh_dict(dimensions, resolution)
    elif geometry_type == "cube":
        return generate_cube_blockmesh_dict(dimensions, resolution)
    else:
        raise ValueError(f"Unsupported geometry type for blockMesh: {geometry_type}")


def generate_cylinder_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int], 
                                   mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate blockMeshDict for cylinder geometry."""
    # Handle both mesh generator format (cylinder_diameter) and case writer format (diameter)
    diameter = dimensions.get("diameter") or dimensions.get("cylinder_diameter", 0.1)
    thickness = dimensions.get("cylinder_length", 0.1)  # Use cylinder_length as thickness for 2D
    
    # Check if this is external flow (O-grid) or internal flow
    is_external_flow = mesh_config.get("is_external_flow", False)
    mesh_topology = mesh_config.get("mesh_topology", "structured")
    
    if is_external_flow and mesh_topology == "o-grid":
        # Generate O-grid mesh for external flow around cylinder
        return generate_cylinder_ogrid_blockmesh_dict(dimensions, resolution, mesh_config)
    else:
        # Original rectangular channel implementation (for backward compatibility)
        return generate_cylinder_channel_blockmesh_dict(dimensions, resolution)


def generate_cylinder_ogrid_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int], 
                                          mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate O-grid blockMeshDict for external flow around cylinder based on OpenFOAM tutorial."""
    import math
    
    # Extract dimensions
    diameter = dimensions.get("cylinder_diameter", 0.1)
    radius = diameter / 2.0
    thickness = dimensions.get("cylinder_length", 0.1)
    
    # Domain dimensions
    domain_size = dimensions.get("domain_length", diameter * 20) / 2  # Half domain size
    
    # Scale factor to adjust from tutorial's unit cylinder (r=0.5) to our radius
    scale = radius / 0.5
    
    # Define vertices based on OpenFOAM tutorial geometry
    # These are the key points for the O-grid structure
    # Inner ring (on cylinder surface)
    r_inner = radius
    # Intermediate ring
    r_mid = 2 * radius  # 2x cylinder radius
    # Outer boundary
    r_outer = domain_size
    
    # Key angles for the O-grid (45 degrees)
    cos45 = 0.707107
    sin45 = 0.707107
    
    # Vertices on the back plane (z = 0)
    vertices = []
    
    # Based on the tutorial's vertex numbering
    # Right side vertices
    vertices.append(f"({r_inner} 0 0)")                              # 0 - on cylinder
    vertices.append(f"({r_mid} 0 0)")                                # 1 - intermediate
    vertices.append(f"({r_outer} 0 0)")                              # 2 - outer boundary
    vertices.append(f"({r_outer} {r_outer*cos45} 0)")               # 3 - outer corner
    vertices.append(f"({r_mid*cos45} {r_mid*sin45} 0)")             # 4 - intermediate diagonal
    vertices.append(f"({r_inner*cos45} {r_inner*sin45} 0)")         # 5 - on cylinder diagonal
    
    # Top vertices
    vertices.append(f"({r_outer} {r_outer} 0)")                      # 6 - top right corner
    vertices.append(f"({r_mid*cos45} {r_outer} 0)")                 # 7 - top intermediate
    vertices.append(f"(0 {r_outer} 0)")                              # 8 - top center
    vertices.append(f"(0 {r_mid} 0)")                                # 9 - intermediate top
    vertices.append(f"(0 {r_inner} 0)")                              # 10 - on cylinder top
    
    # Left side vertices
    vertices.append(f"(-{r_inner} 0 0)")                             # 11 - on cylinder
    vertices.append(f"(-{r_mid} 0 0)")                               # 12 - intermediate
    vertices.append(f"(-{r_outer} 0 0)")                             # 13 - outer boundary
    vertices.append(f"(-{r_outer} {r_outer*cos45} 0)")              # 14 - outer corner
    vertices.append(f"(-{r_mid*cos45} {r_mid*sin45} 0)")            # 15 - intermediate diagonal
    vertices.append(f"(-{r_inner*cos45} {r_inner*sin45} 0)")        # 16 - on cylinder diagonal
    vertices.append(f"(-{r_outer} {r_outer} 0)")                     # 17 - top left corner
    vertices.append(f"(-{r_mid*cos45} {r_outer} 0)")                # 18 - top intermediate
    
    # Duplicate all vertices for the front plane (z = thickness)
    num_vertices = len(vertices)
    for i in range(num_vertices):
        coords = vertices[i].strip("()").split()
        vertices.append(f"({coords[0]} {coords[1]} {thickness})")
    
    # Resolution
    n_tangential = resolution.get("circumferential", 80) // 8  # Cells per block in tangential direction
    n_radial = resolution.get("radial", 32) // 2  # Cells in radial direction (2 layers)
    n_axial = 1  # Single cell in z-direction for 2D
    
    # Grading
    radial_grading = mesh_config.get("grading", {}).get("radial", 10.0)
    
    # Define the 10 blocks based on the tutorial
    blocks = []
    
    # Block 0 (bottom right inner)
    blocks.append(f"hex (5 4 9 10 {5+19} {4+19} {9+19} {10+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 1 (bottom center inner)
    blocks.append(f"hex (0 1 4 5 {0+19} {1+19} {4+19} {5+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 2 (bottom inner)
    blocks.append(f"hex (1 2 3 4 {1+19} {2+19} {3+19} {4+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 3 (right inner)
    blocks.append(f"hex (4 3 6 7 {4+19} {3+19} {6+19} {7+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 4 (top right inner)
    blocks.append(f"hex (9 4 7 8 {9+19} {4+19} {7+19} {8+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 5 (top left inner)
    blocks.append(f"hex (15 16 10 9 {15+19} {16+19} {10+19} {9+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 6 (top inner)
    blocks.append(f"hex (18 15 9 8 {18+19} {15+19} {9+19} {8+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 7 (left inner)
    blocks.append(f"hex (17 18 15 14 {17+19} {18+19} {15+19} {14+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 8 (bottom left inner)
    blocks.append(f"hex (14 15 12 13 {14+19} {15+19} {12+19} {13+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Block 9 (bottom center left inner)
    blocks.append(f"hex (16 15 12 11 {16+19} {15+19} {12+19} {11+19}) ({n_tangential} {n_radial} {n_axial}) simpleGrading (1 {radial_grading} 1)")
    
    # Define edges - circular arcs for cylinder surface
    edges = []
    
    # Cylinder surface arcs (inner ring) - correct midpoints for 90-degree arcs
    # Arc from point (r,0) to point (r*cos45, r*sin45), midpoint at 22.5 degrees
    cos225 = 0.92388  # cos(22.5 degrees)
    sin225 = 0.38268  # sin(22.5 degrees)
    cos675 = 0.38268  # cos(67.5 degrees)
    sin675 = 0.92388  # sin(67.5 degrees)
    
    # Back face arcs
    edges.append(f"arc 0 5 ({r_inner*cos225} {r_inner*sin225} 0)")       # Right to diagonal (0° to 45°)
    edges.append(f"arc 5 10 ({r_inner*cos675} {r_inner*sin675} 0)")      # Diagonal to top (45° to 90°)
    edges.append(f"arc 10 16 (-{r_inner*cos675} {r_inner*sin675} 0)")    # Top to diagonal (90° to 135°)
    edges.append(f"arc 16 11 (-{r_inner*cos225} {r_inner*sin225} 0)")    # Diagonal to left (135° to 180°)
    
    # Front face arcs (same pattern at z=thickness)
    edges.append(f"arc {0+19} {5+19} ({r_inner*cos225} {r_inner*sin225} {thickness})")
    edges.append(f"arc {5+19} {10+19} ({r_inner*cos675} {r_inner*sin675} {thickness})")
    edges.append(f"arc {10+19} {16+19} (-{r_inner*cos675} {r_inner*sin675} {thickness})")
    edges.append(f"arc {16+19} {11+19} (-{r_inner*cos225} {r_inner*sin225} {thickness})")
    
    # Define boundary patches
    boundary = {
        "cylinder": {
            "type": "wall",
            "faces": [
                "(0 5 24 19)",    # Right to diagonal
                "(5 10 29 24)",   # Diagonal to top
                "(10 16 35 29)",  # Top to diagonal
                "(16 11 30 35)"   # Diagonal to left
            ]
        },
        "left": {
            "type": "patch",
            "faces": [
                "(13 14 33 32)",  # Bottom section
                "(14 17 36 33)"   # Top section
            ]
        },
        "right": {
            "type": "patch",
            "faces": [
                "(2 3 22 21)",    # Bottom section
                "(3 6 25 22)"     # Top section
            ]
        },
        "down": {
            "type": "wall",
            "faces": [
                "(11 30 31 12)",  # Left section
                "(12 31 32 13)",  # Left outer
                "(0 19 20 1)",    # Right inner
                "(1 20 21 2)"     # Right outer
            ]
        },
        "up": {
            "type": "symmetryPlane",
            "faces": [
                "(6 7 26 25)",    # Right section
                "(7 8 27 26)",    # Center section
                "(8 18 37 27)",   # Left section
                "(18 17 36 37)"   # Left outer
            ]
        },
        "front": {
            "type": "empty",
            "faces": [
                "(19 20 23 24)",  # Block 1 front
                "(24 23 28 29)",  # Block 0 front
                "(20 21 22 23)",  # Block 2 front
                "(23 22 25 26)",  # Block 3 front
                "(28 23 26 27)",  # Block 4 front
                "(34 35 29 28)",  # Block 5 front
                "(37 34 28 27)",  # Block 6 front
                "(36 37 34 33)",  # Block 7 front
                "(33 34 31 32)",  # Block 8 front
                "(35 34 31 30)"   # Block 9 front
            ]
        },
        "back": {
            "type": "empty",
            "faces": [
                "(0 1 4 5)",      # Block 1 back
                "(5 4 9 10)",     # Block 0 back
                "(1 2 3 4)",      # Block 2 back
                "(4 3 6 7)",      # Block 3 back
                "(9 4 7 8)",      # Block 4 back
                "(15 16 10 9)",   # Block 5 back
                "(18 15 9 8)",    # Block 6 back
                "(17 18 15 14)",  # Block 7 back
                "(14 15 12 13)",  # Block 8 back
                "(16 15 12 11)"   # Block 9 back
            ]
        }
    }
    
    return {
        "convertToMeters": 1,
        "vertices": vertices,
        "blocks": blocks,
        "edges": edges,
        "boundary": boundary,
        "mergePatchPairs": []
    }


def generate_cylinder_channel_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate simple rectangular channel blockMeshDict (original implementation)."""
    # Original implementation for backward compatibility
    diameter = dimensions.get("diameter") or dimensions.get("cylinder_diameter", 0.1)
    thickness = dimensions.get("cylinder_length", 0.1)
    
    radius = diameter / 2.0
    domain_length = diameter * 20
    domain_height = diameter * 10
    
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
        "mergePatchPairs": []
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
                "faces": ["(0 4 7 3)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(1 2 6 5)"]
            },
            "airfoil": {
                "type": "wall",
                "faces": ["(0 1 2 3)", "(4 5 6 7)"]
            },
            "farfield": {
                "type": "patch",
                "faces": ["(0 1 5 4)", "(3 2 6 7)"]
            },
            "sides": {
                "type": "empty",
                "faces": ["(0 3 2 1)", "(4 5 6 7)"]
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
                "faces": ["(0 4 7 3)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(1 2 6 5)"]
            },
            "walls": {
                "type": "wall",
                "faces": ["(0 1 2 3)", "(4 5 6 7)", "(0 1 5 4)", "(3 2 6 7)"]
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
                "faces": ["(0 4 7 3)"]
            },
            "outlet": {
                "type": "patch",
                "faces": ["(1 2 6 5)"]
            },
            "sphere": {
                "type": "wall",
                "faces": ["(0 1 2 3)", "(4 5 6 7)"]
            },
            "farfield": {
                "type": "patch",
                "faces": ["(0 1 5 4)", "(3 2 6 7)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_cube_blockmesh_dict(dimensions: Dict[str, float], resolution: Dict[str, int]) -> Dict[str, Any]:
    """Generate blockMeshDict for cube geometry (used for background mesh only)."""
    # This is just for the background mesh when using snappyHexMesh
    # The actual cube geometry is handled by snappyHexMesh
    
    # Use the background mesh dimensions from mesh_config
    domain_length = dimensions.get("domain_length", 2.0)
    domain_height = dimensions.get("domain_height", 1.0)
    domain_width = dimensions.get("domain_width", 0.1)
    
    # Cell counts
    nx = resolution.get("x", 60)
    ny = resolution.get("y", 30)
    nz = resolution.get("z", 1)
    
    # Check if this is 2D or 3D
    is_2d = nz == 1
    
    return {
        "convertToMeters": 1.0,
        "vertices": [
            "(0 0 0)",
            f"({domain_length} 0 0)",
            f"({domain_length} {domain_height} 0)",
            f"(0 {domain_height} 0)",
            f"(0 0 {domain_width})",
            f"({domain_length} 0 {domain_width})",
            f"({domain_length} {domain_height} {domain_width})",
            f"(0 {domain_height} {domain_width})"
        ],
        "blocks": [
            f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)"
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
            "top": {
                "type": "patch",
                "faces": ["(3 7 6 2)"]
            },
            "bottom": {
                "type": "patch",
                "faces": ["(0 1 5 4)"]
            },
            "front": {
                "type": "empty" if is_2d else "patch",
                "faces": ["(0 3 2 1)"]
            },
            "back": {
                "type": "empty" if is_2d else "patch",
                "faces": ["(4 5 6 7)"]
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
    
    # Check if we have solver-specific fields that should override standard fields
    solver_settings = state.get("solver_settings", {})
    
    for field_name, field_config in boundary_conditions.items():
        # Skip standard pressure field if p_rgh is available (for interFoam)
        if field_name == "p" and "p_rgh" in solver_settings:
            continue
        
        write_foam_dict(zero_dir / field_name, field_config)
    
    if state["verbose"]:
        logger.info(f"Case Writer: Wrote {len(boundary_conditions)} boundary condition files")


def write_boundary_condition_files_with_mapping(case_directory: Path, state: CFDState) -> None:
    """Write boundary condition files with intelligent patch mapping."""
    from .boundary_condition import (
        read_mesh_patches, map_boundary_conditions_to_patches, 
        get_ai_boundary_conditions, merge_ai_boundary_conditions
    )
    
    boundary_conditions = state["boundary_conditions"]
    
    # Check if we need to do patch mapping
    # For complex geometries (cylinder, sphere, etc.) that use snappyHexMesh
    geometry_type = state["geometry_info"].get("type")
    mesh_config = state.get("mesh_config", {})
    is_snappy = mesh_config.get("type") == "snappyHexMesh" or mesh_config.get("mesh_topology") == "snappy"
    
    # Check if we can read actual mesh patches (mesh might not be generated yet)
    boundary_file = case_directory / "constant" / "polyMesh" / "boundary"
    
    if is_snappy or boundary_file.exists():
        logger.info("Case Writer: Using intelligent boundary condition mapping")
        
        # Try to read actual mesh patches
        actual_patches = read_mesh_patches(case_directory) if boundary_file.exists() else []
        
        if actual_patches:
            # Map boundary conditions to actual patches
            mapped_conditions = map_boundary_conditions_to_patches(
                boundary_conditions, actual_patches, geometry_type
            )
            
            # For complex solvers, enhance with AI boundary conditions
            solver_settings = state.get("solver_settings", {})
            solver_type = solver_settings.get("solver_type")
            
            if solver_type and hasattr(solver_type, 'value'):
                solver_name = solver_type.value
            else:
                solver_name = str(solver_type) if solver_type else ""
            
            if solver_name in ["rhoPimpleFoam", "chtMultiRegionFoam", "reactingFoam"]:
                logger.info(f"Case Writer: Enhancing boundary conditions with AI for {solver_name}")
                
                try:
                    ai_conditions = get_ai_boundary_conditions(
                        solver_type, state["geometry_info"], state["parsed_parameters"], actual_patches
                    )
                    
                    if ai_conditions:
                        # Merge AI-generated conditions with mapped conditions
                        mapped_conditions = merge_ai_boundary_conditions(
                            mapped_conditions, ai_conditions, actual_patches
                        )
                        logger.info("Case Writer: Successfully integrated AI boundary conditions")
                except Exception as e:
                    logger.warning(f"Case Writer: AI boundary condition enhancement failed: {str(e)}")
            
            boundary_conditions = mapped_conditions
        else:
            logger.info("Case Writer: Mesh not yet generated, using original boundary conditions")
    
    # Write the boundary condition files
    zero_dir = case_directory / "0"
    
    # Check if we have solver-specific fields that should override standard fields
    solver_settings = state.get("solver_settings", {})
    
    for field_name, field_config in boundary_conditions.items():
        # Skip standard pressure field if p_rgh is available (for interFoam)
        if field_name == "p" and "p_rgh" in solver_settings:
            continue
        
        write_foam_dict(zero_dir / field_name, field_config)
    
    if state["verbose"]:
        logger.info(f"Case Writer: Wrote {len(boundary_conditions)} boundary condition files with mapping")


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
    
    # Write solver-specific files
    # interFoam specific files
    if "g" in solver_settings:
        write_foam_dict(case_directory / "constant" / "g", solver_settings["g"])
        if state["verbose"]:
            logger.info("Case Writer: Wrote gravity vector g for interFoam")
    
    if "sigma" in solver_settings:
        # Surface tension is typically included in transportProperties for interFoam
        # But if provided separately, we can write it
        if state["verbose"]:
            logger.info(f"Case Writer: Surface tension sigma={solver_settings['sigma']} will be included in transportProperties")
    
    if "alpha.water" in solver_settings:
        # Write initial volume fraction field with corrected boundary conditions
        alpha_water_config = solver_settings["alpha.water"]
        
        # Apply boundary condition corrections for patch types inline
        if "boundaryField" in alpha_water_config:
            from .boundary_condition import read_mesh_patches_with_types, adjust_boundary_condition_for_patch_type
            
            # Get patch types from mesh
            patches_info = read_mesh_patches_with_types(case_directory)
            patch_types = {info['name']: info['type'] for info in patches_info}
            
            # Correct boundary conditions for each patch
            corrected_boundary_field = {}
            for patch_name, bc_data in alpha_water_config["boundaryField"].items():
                patch_type = patch_types.get(patch_name, "patch")
                corrected_bc = adjust_boundary_condition_for_patch_type(
                    bc_data, patch_type, "alpha.water", patch_name
                )
                corrected_boundary_field[patch_name] = corrected_bc
            
            alpha_water_config = {
                **alpha_water_config,
                "boundaryField": corrected_boundary_field
            }
        
        write_foam_dict(case_directory / "0" / "alpha.water", alpha_water_config)
        if state["verbose"]:
            logger.info("Case Writer: Wrote initial alpha.water field for interFoam")
    
    if "p_rgh" in solver_settings:
        # Write p_rgh field for multiphase flows with corrected boundary conditions
        p_rgh_config = solver_settings["p_rgh"]
        
        # Apply boundary condition corrections for patch types inline
        if "boundaryField" in p_rgh_config:
            from .boundary_condition import read_mesh_patches_with_types, adjust_boundary_condition_for_patch_type
            
            # Get patch types from mesh
            patches_info = read_mesh_patches_with_types(case_directory)
            patch_types = {info['name']: info['type'] for info in patches_info}
            
            # Correct boundary conditions for each patch
            corrected_boundary_field = {}
            for patch_name, bc_data in p_rgh_config["boundaryField"].items():
                patch_type = patch_types.get(patch_name, "patch")
                corrected_bc = adjust_boundary_condition_for_patch_type(
                    bc_data, patch_type, "p_rgh", patch_name
                )
                corrected_boundary_field[patch_name] = corrected_bc
            
            p_rgh_config = {
                **p_rgh_config,
                "boundaryField": corrected_boundary_field
            }
        
        write_foam_dict(case_directory / "0" / "p_rgh", p_rgh_config)
        if state["verbose"]:
            logger.info("Case Writer: Wrote p_rgh field for interFoam")
    
    # rhoPimpleFoam specific files
    if "thermophysicalProperties" in solver_settings:
        write_foam_dict(case_directory / "constant" / "thermophysicalProperties", solver_settings["thermophysicalProperties"])
        if state["verbose"]:
            logger.info("Case Writer: Wrote thermophysicalProperties for rhoPimpleFoam")
    
    if "T" in solver_settings:
        # Only write temperature field if it doesn't already exist from boundary conditions
        temp_file_path = case_directory / "0" / "T"
        if not temp_file_path.exists():
            write_foam_dict(temp_file_path, solver_settings["T"])
            if state["verbose"]:
                logger.info("Case Writer: Wrote initial temperature field T for rhoPimpleFoam")
        else:
            if state["verbose"]:
                logger.info("Case Writer: Temperature field T already exists from boundary conditions")
    
    # chtMultiRegionFoam specific files
    if "regionProperties" in solver_settings:
        # Fix regionProperties format for OpenFOAM
        region_props = solver_settings["regionProperties"]
        fixed_region_props = {}
        
        # Handle the special case of regions list - OpenFOAM expects nested parentheses
        if "regions" in region_props:
            regions_list = region_props["regions"]
            fluid_regions = region_props.get("fluidRegions", [])
            solid_regions = region_props.get("solidRegions", [])
            
            # Format regions as nested lists: regions ( fluid (air) solid (heater) );
            regions_str = "(\n"
            if fluid_regions:
                regions_str += f"    fluid ({' '.join(fluid_regions)})\n"
            if solid_regions:
                regions_str += f"    solid ({' '.join(solid_regions)})\n"
            regions_str += ")"
            fixed_region_props["regions"] = regions_str
        
        # Handle other keys normally
        for key, value in region_props.items():
            if key not in ["regions", "fluidRegions", "solidRegions"]:
                if isinstance(value, list):
                    fixed_region_props[key] = f"({' '.join(value)})"
                else:
                    fixed_region_props[key] = value
        
        write_foam_dict(case_directory / "constant" / "regionProperties", fixed_region_props)
        if state["verbose"]:
            logger.info("Case Writer: Wrote regionProperties for chtMultiRegionFoam")
    
    if "fvOptions" in solver_settings:
        write_foam_dict(case_directory / "constant" / "fvOptions", solver_settings["fvOptions"])
        if state["verbose"]:
            logger.info("Case Writer: Wrote fvOptions for chtMultiRegionFoam")
    
    # reactingFoam specific files
    if "chemistryProperties" in solver_settings:
        write_foam_dict(case_directory / "constant" / "chemistryProperties", solver_settings["chemistryProperties"])
        if state["verbose"]:
            logger.info("Case Writer: Wrote chemistryProperties for reactingFoam")
    
    if "combustionProperties" in solver_settings:
        write_foam_dict(case_directory / "constant" / "combustionProperties", solver_settings["combustionProperties"])
        if state["verbose"]:
            logger.info("Case Writer: Wrote combustionProperties for reactingFoam")
    
    # Write basic reactions file for reactingFoam
    if solver_settings.get("solver") == "reactingFoam":
        reactions_file = generate_basic_reactions_file()
        write_foam_dict(case_directory / "constant" / "reactions", reactions_file)
        if state["verbose"]:
            logger.info("Case Writer: Wrote basic reactions file for reactingFoam")
        
        # Generate initial species mass fraction fields
        species_list = reactions_file["species"]
        for species in species_list:
            species_field = generate_species_field(species, species_list)
            write_foam_dict(case_directory / "0" / species, species_field)
        if state["verbose"]:
            logger.info(f"Case Writer: Wrote {len(species_list)} species fields for reactingFoam")
    
    if state["verbose"]:
        logger.info("Case Writer: Wrote solver configuration files")


def generate_species_field(species: str, species_list: List[str]) -> Dict[str, Any]:
    """Generate initial species mass fraction field for reactingFoam."""
    # Default initial mass fractions (air + fuel mixture)
    initial_mass_fractions = {
        "CH4": 0.05,  # 5% fuel
        "O2": 0.21,   # 21% oxygen (air)
        "N2": 0.74,   # 74% nitrogen (air)
        "CO2": 0.0,   # No products initially
        "H2O": 0.0    # No products initially
    }
    
    mass_fraction = initial_mass_fractions.get(species, 0.0)
    
    return {
        "dimensions": "[0 0 0 0 0 0 0]",  # Dimensionless mass fraction
        "internalField": f"uniform {mass_fraction}",
        "boundaryField": {
            "inlet": {
                "type": "fixedValue",
                "value": f"uniform {mass_fraction}"
            },
            "outlet": {
                "type": "zeroGradient"
            },
            "walls": {
                "type": "zeroGradient"
            }
        }
    }


def generate_basic_reactions_file() -> Dict[str, Any]:
    """Generate a basic reactions file for reactingFoam."""
    return {
        "species": ["CH4", "O2", "CO2", "H2O", "N2"],
        "reactions": [
            {
                "reaction": "CH4 + 2*O2 = CO2 + 2*H2O",
                "A": 5.012e11,
                "beta": 0.0,
                "Ta": 15098
            }
        ],
        "CH4": {
            "specie": {
                "nMoles": 1,
                "molWeight": 16.04
            },
            "thermodynamics": {
                "Cp": 2220,
                "Hf": -74873
            },
            "transport": {
                "mu": 1.1e-5,
                "Pr": 0.7
            }
        },
        "O2": {
            "specie": {
                "nMoles": 1,
                "molWeight": 32.0
            },
            "thermodynamics": {
                "Cp": 920,
                "Hf": 0
            },
            "transport": {
                "mu": 2.0e-5,
                "Pr": 0.7
            }
        },
        "CO2": {
            "specie": {
                "nMoles": 1,
                "molWeight": 44.01
            },
            "thermodynamics": {
                "Cp": 850,
                "Hf": -393520
            },
            "transport": {
                "mu": 1.5e-5,
                "Pr": 0.7
            }
        },
        "H2O": {
            "specie": {
                "nMoles": 1,
                "molWeight": 18.02
            },
            "thermodynamics": {
                "Cp": 2080,
                "Hf": -241826
            },
            "transport": {
                "mu": 1.0e-5,
                "Pr": 0.7
            }
        },
        "N2": {
            "specie": {
                "nMoles": 1,
                "molWeight": 28.02
            },
            "thermodynamics": {
                "Cp": 1040,
                "Hf": 0
            },
            "transport": {
                "mu": 1.8e-5,
                "Pr": 0.7
            }
        }
    }


def generate_allrun_script(state: CFDState) -> str:
    """Generate Allrun script for the case."""
    solver = state["solver_settings"]["solver"]
    mesh_config = state["mesh_config"]
    mesh_type = mesh_config.get("type", "blockMesh")
    
    if mesh_type == "snappyHexMesh":
        # For snappyHexMesh cases (including STL files)
        has_stl = mesh_config.get("is_custom_geometry", False) and state.get("stl_file")
        
        script = f"""#!/bin/sh
cd "${{0%/*}}" || exit                                # Run from this directory
. ${{WM_PROJECT_DIR:?}}/bin/tools/RunFunctions        # Tutorial run functions
#------------------------------------------------------------------------------

echo "Running {solver} case with snappyHexMesh"

# Generate background mesh
echo "Generating background mesh..."
runApplication blockMesh

# Check background mesh quality
echo "Checking background mesh..."
runApplication checkMesh

"""
        
        # Add surface feature extraction for STL files
        if has_stl:
            script += """# Extract surface features from STL geometry
echo "Extracting surface features from STL geometry..."
runApplication surfaceFeatureExtract

"""
        
        script += f"""# Run snappyHexMesh for mesh refinement
echo "Running snappyHexMesh for mesh refinement..."
runApplication snappyHexMesh -overwrite

# Check final mesh quality
echo "Checking final mesh..."
runApplication checkMesh

# Run solver
echo "Running solver {solver}..."
runApplication {solver}

echo "Case completed successfully"

#------------------------------------------------------------------------------
"""
    else:
        # Original blockMesh approach
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
    # Get OpenFOAM variant to determine version format
    try:
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        variant = settings.openfoam_variant
        version = settings.openfoam_version
        
        # Format version string based on variant
        if variant == "Foundation":
            version_str = version  # Foundation uses plain numbers like "12"
        else:
            version_str = f"v{version}"  # ESI uses "v2312" format
    except:
        # Default to ESI format if can't determine
        version_str = "v2312"
    
    header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  {version_str}                                 |
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
            elif isinstance(value, (list, tuple)):
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
                        # Handle tuples (format as space-separated values in parentheses)
                        if isinstance(item, tuple):
                            tuple_str = " ".join(str(v) for v in item)
                            result += f"{indent}    ({tuple_str})\n"
                        # Handle dictionary items in arrays (like patches)
                        elif isinstance(item, dict):
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
                # Convert Python boolean to OpenFOAM format
                if isinstance(value, bool):
                    value = str(value).lower()
                # Special handling for regionProperties regions key - it's already formatted
                if key == "regions" and isinstance(value, str) and value.startswith("("):
                    result += f"{indent}{key}\n{indent}{value};\n"
                else:
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
    
    # Check solver-specific files
    # Read controlDict to determine solver
    control_dict_path = case_directory / "system" / "controlDict"
    if control_dict_path.exists():
        with open(control_dict_path, 'r') as f:
            content = f.read()
            # Simple regex to find application
            import re
            match = re.search(r'application\s+(\w+);', content)
            if match:
                solver = match.group(1)
                
                # Check for interFoam specific files
                if solver == "interFoam":
                    if not (case_directory / "constant" / "g").exists():
                        warnings.append("Missing gravity vector 'g' for interFoam")
                    if not (case_directory / "0" / "alpha.water").exists():
                        errors.append("Missing alpha.water field for interFoam")
                
                # Check for rhoPimpleFoam specific files
                elif solver == "rhoPimpleFoam":
                    if not (case_directory / "constant" / "thermophysicalProperties").exists():
                        errors.append("Missing thermophysicalProperties for rhoPimpleFoam")
                    if not (case_directory / "0" / "T").exists():
                        errors.append("Missing temperature field T for rhoPimpleFoam")
    
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
    """Generate createPatchDict for creating cylinder boundary patches."""
    return {
        "pointSync": False,
        "patches": [
            {
                "name": "cylinder",
                "patchInfo": {
                    "type": "wall"
                },
                "constructFrom": "set",
                "set": "cylinderPatch"
            }
        ]
    }


def generate_background_blockmesh_dict(background_mesh: Dict[str, Any]) -> Dict[str, Any]:
    """Generate simple background blockMeshDict for snappyHexMesh."""
    # Extract dimensions
    length = background_mesh.get("domain_length", 2.0)
    height = background_mesh.get("domain_height", 1.0)
    width = background_mesh.get("domain_width", 0.1)
    
    # Cell counts
    nx = background_mesh.get("n_cells_x", 60)
    ny = background_mesh.get("n_cells_y", 30)
    nz = background_mesh.get("n_cells_z", 1)
    
    # Check if this is 2D or 3D
    is_2d = nz == 1
    
    # Domain bounds - centered at origin for simplicity
    x_min = 0
    x_max = length
    y_min = 0
    y_max = height
    z_min = 0
    z_max = width
    
    return {
        "convertToMeters": 1.0,
        "vertices": [
            f"({x_min} {y_min} {z_min})",
            f"({x_max} {y_min} {z_min})",
            f"({x_max} {y_max} {z_min})",
            f"({x_min} {y_max} {z_min})",
            f"({x_min} {y_min} {z_max})",
            f"({x_max} {y_min} {z_max})",
            f"({x_max} {y_max} {z_max})",
            f"({x_min} {y_max} {z_max})"
        ],
        "blocks": [
            f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)"
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
            "top": {
                "type": "patch",
                "faces": ["(3 7 6 2)"]
            },
            "bottom": {
                "type": "patch",
                "faces": ["(0 1 5 4)"]
            },
            "front": {
                "type": "empty" if is_2d else "patch",
                "faces": ["(0 3 2 1)"]
            },
            "back": {
                "type": "empty" if is_2d else "patch",
                "faces": ["(4 5 6 7)"]
            }
        },
        "mergePatchPairs": []
    }


def generate_location_in_mesh(mesh_config: Dict[str, Any], dimensions: Dict[str, Any]) -> list:
    """Generate locationInMesh point based on geometry type."""
    geometry_type = mesh_config.get("geometry_type", "")
    is_2d = mesh_config.get("is_2d", False)
    
    # Get background mesh dimensions
    background_mesh = mesh_config.get("background_mesh", {})
    domain_width = background_mesh.get("domain_width", 0.1)
    
    # Default z-coordinate for 2D cases should be in the middle of the thin domain
    z_coord = domain_width / 2 if is_2d else 0.05
    
    if geometry_type == "cylinder":
        # Place point upstream of cylinder
        x = dimensions.get("cylinder_center_x", dimensions.get("domain_upstream", 0.8)) - dimensions.get("cylinder_diameter", 0.1)
        y = dimensions.get("cylinder_center_y", dimensions.get("domain_height", 1.0) / 2)
        return [x, y, z_coord]
    
    elif geometry_type == "sphere":
        # Place point upstream of sphere
        x = dimensions.get("sphere_center_x", dimensions.get("domain_upstream", 0.8)) - dimensions.get("sphere_diameter", 0.1)
        y = dimensions.get("sphere_center_y", dimensions.get("domain_height", 1.0) / 2)
        z = dimensions.get("sphere_center_z", dimensions.get("domain_width", 1.0) / 2) - dimensions.get("sphere_diameter", 0.1) / 2
        return [x, y, z]
    
    elif geometry_type == "cube":
        # Place point upstream of cube
        x = dimensions.get("cube_center_x", dimensions.get("domain_upstream", 0.8)) - dimensions.get("cube_side_length", 0.1)
        y = dimensions.get("cube_center_y", dimensions.get("domain_height", 0.5) / 2)
        z = dimensions.get("cube_center_z", z_coord)
        # Make sure z is within domain for 2D
        if is_2d:
            z = domain_width / 2
        return [x, y, z]
    
    elif geometry_type == "airfoil":
        # Place point upstream of airfoil
        x = dimensions.get("airfoil_center_x", dimensions.get("domain_upstream", 0.9)) - dimensions.get("airfoil_chord", 0.1)
        y = dimensions.get("airfoil_center_y", dimensions.get("domain_height", 1.5) / 2)
        # For 2D airfoil, z must be within the thin domain
        if is_2d:
            z = domain_width / 2
        else:
            z = dimensions.get("domain_width", 0.75) / 2
        return [x, y, z]
    
    else:
        # Default location
        return [0.9, 0.5, z_coord]


def generate_snappyhexmesh_dict(mesh_config: Dict[str, Any], state: CFDState) -> Dict[str, Any]:
    """Generate snappyHexMeshDict for mesh refinement around geometry."""
    geometry = mesh_config.get("geometry", {})
    snappy_settings = mesh_config.get("snappy_settings", {})
    dimensions = mesh_config.get("dimensions", {})
    is_custom_geometry = mesh_config.get("is_custom_geometry", False)
    
    # Build geometry section
    geometry_dict = {}
    
    # Handle STL files for custom geometry
    if is_custom_geometry and mesh_config.get("stl_file_case_path"):
        # Use the STL file name as the geometry name
        stl_name = mesh_config.get("stl_name", "stl_surface")
        # Ensure the file path is in the correct OpenFOAM format
        stl_file_path = mesh_config.get("stl_file_case_path", "constant/triSurface/geometry.stl")
        # Remove any leading path separators and use forward slashes
        stl_file_path = stl_file_path.replace("\\", "/").lstrip("/")
        
        # Use just the filename - OpenFOAM will look in triSurface by default
        from pathlib import Path
        stl_filename = Path(stl_file_path).name
        
        geometry_dict[stl_name] = {
            "type": "triSurfaceMesh",
            "file": f'"{stl_filename}"'  # Use just the filename
        }
    else:
        # Handle built-in geometry types
        for geom_name, geom_data in geometry.items():
            if geom_data["type"] == "cylinder":
                geometry_dict[geom_name] = {
                    "type": "searchableCylinder",
                    "point1": geom_data["point1"],
                    "point2": geom_data["point2"],
                    "radius": geom_data["radius"]
                }
            elif geom_data["type"] == "sphere":
                geometry_dict[geom_name] = {
                    "type": "searchableSphere",
                    "centre": geom_data["center"],
                    "radius": geom_data["radius"]
                }
            elif geom_data["type"] == "cube":
                geometry_dict[geom_name] = {
                    "type": "searchableBox",
                    "min": geom_data["min"],
                    "max": geom_data["max"]
                }
            elif geom_data["type"] == "airfoil":
                # Airfoils typically need STL files or custom geometry
                # For now, use a simple box approximation
                geometry_dict[geom_name] = {
                    "type": "searchableBox",
                    "min": [geom_data["center"][0] - geom_data["chord"]/2, 
                           geom_data["center"][1] - geom_data["thickness"]/2,
                           geom_data["center"][2] - geom_data["span"]/2],
                    "max": [geom_data["center"][0] + geom_data["chord"]/2, 
                           geom_data["center"][1] + geom_data["thickness"]/2,
                           geom_data["center"][2] + geom_data["span"]/2]
                }
    
    # Refinement region
    refinement_region = snappy_settings.get("refinement_region", {})
    
    # Build refinement surfaces and layers based on geometry names
    refinement_surfaces = {}
    layers_dict = {}
    
    for geom_name in geometry_dict.keys():
        refinement_surfaces[geom_name] = {
            "level": [
                snappy_settings.get("refinement_levels", {}).get("min", 0),
                snappy_settings.get("refinement_levels", {}).get("max", 2)
            ],
            "patchInfo": {
                "type": "wall"
            }
        }
        # Add layers if enabled
        if snappy_settings.get("add_layers", False):
            layers_dict[geom_name] = {
                "nSurfaceLayers": snappy_settings.get("layers", {}).get("n_layers", 3)
            }
    
    # Generate location in mesh - for custom geometry, use the specified location
    if is_custom_geometry:
        location_in_mesh = snappy_settings.get("location_in_mesh", [0.05, 0.5, 0.5])
    else:
        location_in_mesh = generate_location_in_mesh(mesh_config, dimensions)
    
    # Get mesh quality controls - use improved settings for STL files
    mesh_quality = snappy_settings.get("mesh_quality", {})
    if not mesh_quality:
        # Default quality controls
        mesh_quality = {
            "maxNonOrtho": 65,
            "maxBoundarySkewness": 20,
            "maxInternalSkewness": 4,
            "maxConcave": 80,
            "minVol": 1e-13,
            "minTetQuality": 1e-30,
            "minArea": -1,
            "minTwist": 0.02,
            "minDeterminant": 0.001,
            "minFaceWeight": 0.02,
            "minVolRatio": 0.01,
            "minTriangleTwist": -1,
            "nSmoothScale": 4,
            "errorReduction": 0.75
        }
    
    # Build the snappyHexMeshDict
    snappy_dict = {
        "castellatedMesh": snappy_settings.get("castellated_mesh", True),
        "snap": snappy_settings.get("snap", True),
        "addLayers": snappy_settings.get("add_layers", False),
        "geometry": geometry_dict,
        "castellatedMeshControls": {
            "maxLocalCells": 1000000,
            "maxGlobalCells": 20000000,
            "minRefinementCells": 0,
            "maxLoadUnbalance": 0.10,
            "nCellsBetweenLevels": 3,
            "features": [],  # Can add feature edge refinement here
            "refinementSurfaces": refinement_surfaces,
            "resolveFeatureAngle": 30,
            "refinementRegions": {},
            "locationInMesh": location_in_mesh,
            "allowFreeStandingZoneFaces": True
        },
        "snapControls": {
            "nSmoothPatch": 3,
            "tolerance": 4.0,  # Increased tolerance for complex geometries
            "nSolveIter": 100,  # More iterations for better convergence
            "nRelaxIter": 8,    # More relaxation iterations
            "nFeatureSnapIter": 15,  # More feature snapping iterations
            "implicitFeatureSnap": False,
            "explicitFeatureSnap": True,
            "multiRegionFeatureSnap": False
        },
        "addLayersControls": {
            "relativeSizes": True,
            "layers": layers_dict,
            "expansionRatio": snappy_settings.get("layers", {}).get("expansion_ratio", 1.3),
            "finalLayerThickness": snappy_settings.get("layers", {}).get("final_layer_thickness", 0.7),
            "minThickness": snappy_settings.get("layers", {}).get("min_thickness", 0.1),
            "nGrow": 0,
            "featureAngle": 60,
            "slipFeatureAngle": 30,
            "nRelaxIter": 3,
            "nSmoothSurfaceNormals": 1,
            "nSmoothNormals": 3,
            "nSmoothThickness": 10,
            "maxFaceThicknessRatio": 0.5,
            "maxThicknessToMedialRatio": 0.3,
            "minMedialAxisAngle": 90,
            "nBufferCellsNoExtrude": 0,
            "nLayerIter": 50
        },
        "meshQualityControls": mesh_quality,  # Use the improved quality controls
        "writeFlags": [],
        "mergeTolerance": 1e-6
    }
    
    # Add refinement box geometry if specified
    if refinement_region.get("min") and refinement_region.get("max"):
        geometry_dict["refinementBox"] = {
            "type": "searchableBox",
            "min": refinement_region["min"],
            "max": refinement_region["max"]
        }
        
        # Add refinement region to controls
        snappy_dict["castellatedMeshControls"]["refinementRegions"]["refinementBox"] = {
            "mode": "inside",
            "levels": [(1e15, snappy_settings.get("refinement_levels", {}).get("max", 2) - 1)]
        }
    
    return snappy_dict
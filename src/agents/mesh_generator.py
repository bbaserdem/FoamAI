"""Mesh Generator Agent - Generates mesh configurations for different geometry types."""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import struct
from loguru import logger

from .state import CFDState, CFDStep, GeometryType


def analyze_stl_bounding_box(stl_file: str) -> Dict[str, Any]:
    """
    Analyze STL file to get bounding box and dimensions.
    Returns dimensions in the original STL units without conversion.
    """
    from pathlib import Path
    import numpy as np
    
    stl_path = Path(stl_file)
    if not stl_path.exists():
        logger.error(f"STL file not found: {stl_file}")
        return get_default_stl_dimensions()
    
    try:
        # Extract vertices from STL
        vertices = extract_stl_vertices(stl_path)
        
        if not vertices:
            logger.error(f"No vertices found in STL file: {stl_file}")
            return get_default_stl_dimensions()
        
        # Convert to numpy array for easier manipulation
        vertices = np.array(vertices)
        
        # Calculate bounding box
        min_coords = vertices.min(axis=0)
        max_coords = vertices.max(axis=0)
        dimensions = max_coords - min_coords
        center = (max_coords + min_coords) / 2
        
        # Calculate characteristic length (max dimension)
        characteristic_length = float(np.max(dimensions))
        
        # NO UNIT CONVERSION - Use STL dimensions as-is
        # The user wants to keep the original size regardless of units
        logger.info(f"STL Analysis - Using original dimensions without unit conversion")
        logger.info(f"STL Bounding Box: min={min_coords.tolist()}, max={max_coords.tolist()}")
        logger.info(f"STL Dimensions: {dimensions.tolist()}")
        logger.info(f"STL Characteristic Length: {characteristic_length:.3f}")
        
        # Calculate volume estimate (sum of all triangle areas * average height)
        # This is a rough estimate
        volume = float(np.prod(dimensions)) * 0.5  # Rough estimate
        
        return {
            "bounding_box": {
                "min": min_coords.tolist(),
                "max": max_coords.tolist(),
                "dimensions": dimensions.tolist(),
                "center": center.tolist()
            },
            "characteristic_length": characteristic_length,
            "scaled_characteristic_length": characteristic_length,  # No scaling
            "dimensions": {
                "x": float(dimensions[0]),
                "y": float(dimensions[1]),
                "z": float(dimensions[2])
            },
            "center": center.tolist(),
            "volume": volume,
            "detected_units": "as-is",  # No unit detection
            "scale_factor": 1.0,  # No scaling applied
            "vertex_count": len(vertices)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing STL file {stl_file}: {e}")
        return get_default_stl_dimensions()


def extract_stl_vertices(stl_path: Path) -> List[List[float]]:
    """Extract all vertices from an STL file (ASCII or binary)."""
    vertices = []
    
    try:
        # Read first part of file to determine format
        with open(stl_path, 'rb') as f:
            header = f.read(80)
            
        # Check if it's a proper ASCII STL file
        if header.startswith(b'solid'):
            # Read more data to verify it's actually ASCII
            with open(stl_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.readlines()[:10]  # Read first 10 lines
                
            # Check if we can find valid ASCII STL content
            has_valid_ascii = False
            for line in first_lines:
                if 'vertex' in line.lower() or 'normal' in line.lower() or 'facet' in line.lower():
                    has_valid_ascii = True
                    break
            
            if has_valid_ascii:
                # Try ASCII parsing
                vertices = extract_ascii_stl_vertices(stl_path)
                if vertices:
                    logger.info(f"Successfully parsed as ASCII STL: {len(vertices)} vertices")
                else:
                    logger.warning("ASCII STL parsing failed, trying binary parsing")
                    vertices = extract_binary_stl_vertices(stl_path)
            else:
                # Header says 'solid' but no valid ASCII content found - likely binary
                logger.warning("STL file has 'solid' header but appears to be binary format")
                vertices = extract_binary_stl_vertices(stl_path)
        else:
            # Binary STL
            vertices = extract_binary_stl_vertices(stl_path)
            
        if vertices:
            logger.info(f"Successfully extracted {len(vertices)} vertices from STL file")
        else:
            logger.error(f"Failed to extract vertices from STL file: {stl_path}")
            
    except Exception as e:
        logger.error(f"Error reading STL file {stl_path}: {e}")
        
    return vertices


def extract_ascii_stl_vertices(stl_path: Path) -> List[List[float]]:
    """Extract vertices from ASCII STL file."""
    vertices = []
    
    try:
        with open(stl_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith('vertex'):
                    parts = line.split()
                    if len(parts) >= 4:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        vertices.append([x, y, z])
    except Exception as e:
        logger.error(f"Error reading ASCII STL {stl_path}: {e}")
        
    return vertices


def extract_binary_stl_vertices(stl_path: Path) -> List[List[float]]:
    """Extract vertices from binary STL file."""
    vertices = []
    
    try:
        with open(stl_path, 'rb') as f:
            # Skip header
            f.read(80)
            
            # Read number of triangles
            num_triangles_data = f.read(4)
            if len(num_triangles_data) != 4:
                logger.error(f"Invalid binary STL file: cannot read triangle count")
                return vertices
                
            num_triangles = struct.unpack('<I', num_triangles_data)[0]
            logger.info(f"Binary STL file contains {num_triangles} triangles")
            
            # Validate triangle count is reasonable
            if num_triangles > 10000000:  # 10M triangles is very large
                logger.warning(f"STL file has very large triangle count: {num_triangles}")
            
            for i in range(num_triangles):
                try:
                    # Read triangle data (normal + 3 vertices + attribute)
                    triangle_data = f.read(50)
                    if len(triangle_data) != 50:
                        logger.warning(f"Incomplete triangle data at triangle {i}")
                        break
                        
                    data = struct.unpack('<12fH', triangle_data)
                    
                    # Extract vertices (skip normal at indices 0-2)
                    v1 = [data[3], data[4], data[5]]
                    v2 = [data[6], data[7], data[8]]
                    v3 = [data[9], data[10], data[11]]
                    
                    # Validate vertices are not NaN or infinite
                    all_vertices = [v1, v2, v3]
                    for vertex in all_vertices:
                        if all(isinstance(coord, (int, float)) and not (np.isnan(coord) or np.isinf(coord)) for coord in vertex):
                            vertices.append(vertex)
                        else:
                            logger.warning(f"Invalid vertex data at triangle {i}: {vertex}")
                            
                except struct.error as e:
                    logger.warning(f"Error unpacking triangle {i}: {e}")
                    break
                except Exception as e:
                    logger.warning(f"Error processing triangle {i}: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"Error reading binary STL {stl_path}: {e}")
        
    return vertices


def detect_stl_units(characteristic_length: float) -> str:
    """
    Detect likely units based on characteristic length.
    
    Heuristic rules:
    - < 0.01: likely millimeters (very small)
    - 0.01 to 0.1: likely centimeters or small meters
    - 0.1 to 10: likely meters
    - > 10: likely millimeters (large model)
    - > 1000: definitely millimeters
    """
    if characteristic_length > 1000:
        return "mm"
    elif characteristic_length > 10:
        return "mm"  # Likely large model in mm
    elif characteristic_length > 0.1:
        return "m"   # Reasonable size in meters
    elif characteristic_length > 0.01:
        return "cm"  # Could be cm or small meters
    else:
        return "mm"  # Very small, likely mm


def get_unit_scale_factor(units: str) -> float:
    """Get scale factor to convert to meters."""
    scale_factors = {
        "mm": 0.001,  # mm to m
        "cm": 0.01,   # cm to m
        "m": 1.0,     # m to m
        "in": 0.0254, # inches to m
        "ft": 0.3048  # feet to m
    }
    return scale_factors.get(units, 1.0)


def get_default_stl_dimensions() -> Dict[str, Any]:
    """Return default STL dimensions when analysis fails."""
    return {
        "bounding_box": {
            "min": [0, 0, 0],
            "max": [10, 10, 10],  # Use larger default size
            "dimensions": [10, 10, 10],
            "center": [5, 5, 5]
        },
        "characteristic_length": 10.0,
        "scaled_characteristic_length": 10.0,
        "dimensions": {"x": 10.0, "y": 10.0, "z": 10.0},
        "center": [5, 5, 5],  # Add missing center key at root level
        "volume": 1000.0,
        "detected_units": "as-is",
        "scale_factor": 1.0,  # Add missing scale factor
        "vertex_count": 0
    }


def validate_stl_dimensions(stl_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate STL dimensions and apply safety checks.
    
    Returns updated analysis with any corrections applied.
    """
    scaled_length = stl_analysis["scaled_characteristic_length"]
    
    # Safety checks
    warnings = []
    corrections = {}
    
    # Check for extreme sizes
    if scaled_length < 0.001:  # Less than 1mm
        warnings.append(f"Very small geometry ({scaled_length*1000:.1f}mm), may cause mesh issues")
    elif scaled_length > 1000:  # Larger than 1km
        warnings.append(f"Very large geometry ({scaled_length:.1f}m), may cause mesh issues")
        # Suggest scaling
        suggested_scale = 1.0 / (scaled_length / 1.0)  # Scale to ~1m
        corrections["suggested_scale_factor"] = suggested_scale
    
    # Check aspect ratio
    dims = stl_analysis["dimensions"]
    max_dim = max(dims["x"], dims["y"], dims["z"])
    min_dim = min(dims["x"], dims["y"], dims["z"])
    aspect_ratio = max_dim / min_dim if min_dim > 0 else float('inf')
    
    if aspect_ratio > 100:
        warnings.append(f"High aspect ratio ({aspect_ratio:.1f}), may cause mesh quality issues")
    
    # Update analysis with validation results
    stl_analysis["validation"] = {
        "warnings": warnings,
        "corrections": corrections,
        "aspect_ratio": aspect_ratio
    }
    
    return stl_analysis


def calculate_adaptive_mesh_parameters(characteristic_length: float, base_resolution: int) -> Dict[str, Any]:
    """
    Calculate adaptive mesh parameters based on STL characteristic length.
    
    This ensures adequate mesh resolution around objects of any size while
    staying within computational limits.
    
    Args:
        characteristic_length: Maximum dimension of the STL object
        base_resolution: Base resolution setting (coarse=20, medium=40, fine=80)
        
    Returns:
        Dict with domain_multiplier, cell counts, and warnings
    """
    # Configuration parameters
    MIN_CELLS_PER_OBJECT = 20  # Minimum cells across object for accuracy
    TARGET_CELLS_PER_OBJECT = 30  # Target for good quality
    MAX_TOTAL_CELLS = 1_000_000  # Computational limit for background mesh
    MAX_CELLS_PER_DIRECTION = 300  # Maximum cells in any direction
    
    # Dynamic domain multiplier based on object size
    if characteristic_length < 1.0:
        # Very small objects need tighter domains
        domain_multiplier = 5.0
    elif characteristic_length < 10.0:
        # Small objects
        domain_multiplier = 10.0
    elif characteristic_length < 100.0:
        # Medium objects
        domain_multiplier = 15.0
    else:
        # Large objects can have larger domains
        domain_multiplier = 20.0
    
    # Calculate domain size
    domain_length = characteristic_length * domain_multiplier
    domain_height = domain_length * 0.5  # Typical aspect ratio
    domain_width = domain_length * 0.5
    
    # Calculate required cell size for target resolution
    target_cell_size = characteristic_length / TARGET_CELLS_PER_OBJECT
    
    # Calculate cells needed in each direction
    cells_x = int(domain_length / target_cell_size)
    cells_y = int(domain_height / target_cell_size)
    cells_z = int(domain_width / target_cell_size)
    
    # Apply limits
    cells_x = min(cells_x, MAX_CELLS_PER_DIRECTION)
    cells_y = min(cells_y, MAX_CELLS_PER_DIRECTION)
    cells_z = min(cells_z, MAX_CELLS_PER_DIRECTION)
    
    # Check total cell count
    total_cells = cells_x * cells_y * cells_z
    
    warnings = []
    if total_cells > MAX_TOTAL_CELLS:
        # Scale back proportionally
        scale_factor = (MAX_TOTAL_CELLS / total_cells) ** (1/3)
        cells_x = int(cells_x * scale_factor)
        cells_y = int(cells_y * scale_factor)
        cells_z = int(cells_z * scale_factor)
        total_cells = cells_x * cells_y * cells_z
        
        # Recalculate actual resolution
        actual_cell_size = domain_length / cells_x
        actual_cells_per_object = characteristic_length / actual_cell_size
        
        warnings.append(f"Mesh resolution limited due to cell count. Object will have ~{actual_cells_per_object:.0f} cells across.")
    
    # Calculate actual cells per object
    actual_cell_size_x = domain_length / cells_x
    cells_per_object = characteristic_length / actual_cell_size_x
    
    # Add warnings if resolution is too low
    if cells_per_object < MIN_CELLS_PER_OBJECT:
        warnings.append(f"Low resolution warning: Only {cells_per_object:.0f} cells across object. Consider scaling up the geometry.")
        
        # Suggest scale factor
        suggested_scale = MIN_CELLS_PER_OBJECT / cells_per_object
        warnings.append(f"Suggested scale factor: {suggested_scale:.1f}x to achieve minimum resolution.")
    
    # Calculate refinement levels for snappyHexMesh
    if cells_per_object < 10:
        # Very coarse - need aggressive refinement
        min_refinement = 2
        max_refinement = 4
    elif cells_per_object < 20:
        # Coarse - need good refinement
        min_refinement = 1
        max_refinement = 3
    else:
        # Adequate - normal refinement
        min_refinement = 0
        max_refinement = 2
    
    # Log the calculations
    logger.info(f"Adaptive Mesh Calculation:")
    logger.info(f"  Object size: {characteristic_length:.3f}")
    logger.info(f"  Domain multiplier: {domain_multiplier}x")
    logger.info(f"  Domain size: {domain_length:.3f} x {domain_height:.3f} x {domain_width:.3f}")
    logger.info(f"  Background mesh: {cells_x} x {cells_y} x {cells_z} = {total_cells:,} cells")
    logger.info(f"  Cells per object: {cells_per_object:.1f}")
    logger.info(f"  Refinement levels: {min_refinement}-{max_refinement}")
    
    if warnings:
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
    
    return {
        "domain_multiplier": domain_multiplier,
        "domain_length": domain_length,
        "domain_height": domain_height,
        "domain_width": domain_width,
        "cells_x": cells_x,
        "cells_y": cells_y,
        "cells_z": cells_z,
        "total_cells": total_cells,
        "cells_per_object": cells_per_object,
        "min_refinement": min_refinement,
        "max_refinement": max_refinement,
        "warnings": warnings
    }


def create_adaptive_domain_vertices(domain_length: float, domain_height: float, domain_width: float, 
                                   stl_center: List[float], characteristic_length: float, 
                                   domain_size_multiplier: float) -> List[List[float]]:
    """
    Create domain vertices that position the STL geometry optimally within the domain.
    
    Creates a background mesh domain that properly contains the entire STL geometry.
    The domain is positioned to ensure the STL is fully contained with appropriate
    upstream and downstream distances for external flow.
    """
    # For external flow, we want:
    # - More space upstream (40% of domain before object center)
    # - Less space downstream (60% of domain after object center)
    # - Centered in Y and Z directions
    
    # Calculate upstream/downstream split
    upstream_fraction = 0.4
    downstream_fraction = 0.6
    
    # Position domain to contain the entire STL with proper spacing
    # The STL center might not be at origin, so we need to account for that
    x_min = stl_center[0] - (upstream_fraction * domain_length)
    x_max = stl_center[0] + (downstream_fraction * domain_length)
    
    # Center the domain in Y and Z around the STL center
    y_min = stl_center[1] - (domain_height / 2)
    y_max = stl_center[1] + (domain_height / 2)
    
    z_min = stl_center[2] - (domain_width / 2)
    z_max = stl_center[2] + (domain_width / 2)
    
    # Create vertices for blockMesh (order matters for OpenFOAM)
    vertices = [
        [x_min, y_min, z_min],  # 0
        [x_max, y_min, z_min],  # 1
        [x_max, y_max, z_min],  # 2
        [x_min, y_max, z_min],  # 3
        [x_min, y_min, z_max],  # 4
        [x_max, y_min, z_max],  # 5
        [x_max, y_max, z_max],  # 6
        [x_min, y_max, z_max]   # 7
    ]
    
    return vertices


def calculate_adaptive_location_in_mesh(domain_vertices: List[List[float]], 
                                       stl_center: List[float]) -> List[float]:
    """
    Calculate a safe locationInMesh point for snappyHexMesh.
    
    Places the point upstream of the STL geometry in the fluid domain.
    The point must be within the background mesh domain bounds and
    outside any solid geometry.
    """
    # Get domain bounds from the background mesh vertices
    x_coords = [v[0] for v in domain_vertices]
    y_coords = [v[1] for v in domain_vertices]
    z_coords = [v[2] for v in domain_vertices]
    
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    z_min, z_max = min(z_coords), max(z_coords)
    
    # Place the point upstream of the STL center
    # Use 20% of the domain length upstream of the object center
    upstream_distance = (x_max - x_min) * 0.2
    
    location_x = stl_center[0] - upstream_distance
    location_y = stl_center[1]  # Use STL center Y
    location_z = stl_center[2]  # Use STL center Z
    
    # Ensure the point is within domain bounds with safety margin
    safety_margin = 0.05  # 5% margin from boundaries
    domain_width = x_max - x_min
    domain_height = y_max - y_min
    domain_depth = z_max - z_min
    
    # Apply safety margins
    location_x = max(x_min + domain_width * safety_margin, 
                    min(location_x, x_max - domain_width * safety_margin))
    location_y = max(y_min + domain_height * safety_margin,
                    min(location_y, y_max - domain_height * safety_margin))
    location_z = max(z_min + domain_depth * safety_margin,
                    min(location_z, z_max - domain_depth * safety_margin))
    
    logger.info(f"LocationInMesh: {[location_x, location_y, location_z]} (upstream of STL center {stl_center})")
    
    return [location_x, location_y, location_z]


# Additional imports for the existing mesh generator functionality
import os
import json


def mesh_generator_agent(state: CFDState) -> CFDState:
    """
    Mesh Generator Agent.
    
    Creates OpenFOAM mesh configuration (blockMeshDict) based on
    geometry information and mesh resolution requirements.
    """
    try:
        if state["verbose"]:
            logger.info("Mesh Generator: Starting mesh generation")
        
        geometry_info = state["geometry_info"]
        parsed_params = state["parsed_parameters"]
        
        # Generate mesh configuration based on geometry type
        mesh_config = generate_mesh_config(geometry_info, parsed_params)
        
        # Validate mesh configuration
        validation_result = validate_mesh_config(mesh_config)
        if not validation_result["valid"]:
            logger.warning(f"Mesh validation issues: {validation_result['warnings']}")
            return {
                **state,
                "errors": state["errors"] + [f"Mesh validation failed: {validation_result['errors']}"],
                "warnings": state["warnings"] + validation_result["warnings"]
            }
        
        # Calculate mesh quality estimates
        mesh_quality = estimate_mesh_quality(mesh_config, geometry_info)
        
        if state["verbose"]:
            logger.info(f"Mesh Generator: Generated mesh with {mesh_config['total_cells']} cells")
            logger.info(f"Mesh Generator: Quality score: {mesh_quality['quality_score']:.2f}")
        
        return {
            **state,
            "mesh_config": mesh_config,
            "mesh_quality": mesh_quality,
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Mesh Generator error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Mesh generation failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def generate_mesh_config(geometry_info: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration based on geometry type."""
    geometry_type = geometry_info["type"]
    dimensions = geometry_info["dimensions"]
    mesh_resolution = geometry_info.get("mesh_resolution", "medium")
    flow_context = geometry_info.get("flow_context", {})
    is_custom_geometry = geometry_info.get("is_custom_geometry", False)
    stl_file = geometry_info.get("stl_file")
    
    # Handle STL file geometry
    if is_custom_geometry and stl_file:
        return generate_stl_mesh_config(stl_file, mesh_resolution, flow_context, parsed_params)
    
    # Handle case where custom geometry is detected but no STL file (fall back to cylinder)
    if geometry_type == GeometryType.CUSTOM and not stl_file:
        logger.warning("Custom geometry detected but no STL file provided, falling back to cylinder geometry")
        geometry_type = GeometryType.CYLINDER
        # Set default cylinder dimensions
        dimensions = {
            "diameter": 0.1,
            "length": 0.1
        }
    
    # Get resolution multiplier
    resolution_multiplier = get_resolution_multiplier(mesh_resolution)
    
    # Check if this is external or internal flow
    is_external_flow = flow_context.get("is_external_flow", False)
    
    if geometry_type == GeometryType.CYLINDER:
        return generate_cylinder_mesh(dimensions, mesh_resolution, is_external_flow, flow_context)
    elif geometry_type == GeometryType.AIRFOIL:
        return generate_airfoil_mesh(dimensions, mesh_resolution, is_external_flow, flow_context)
    elif geometry_type == GeometryType.PIPE:
        return generate_pipe_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.CHANNEL:
        return generate_channel_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.SPHERE:
        return generate_sphere_mesh(dimensions, mesh_resolution, is_external_flow, flow_context)
    elif geometry_type == GeometryType.CUBE:
        return generate_cube_mesh(dimensions, mesh_resolution, is_external_flow, flow_context)
    elif geometry_type == GeometryType.NOZZLE:
        return generate_nozzle_mesh(dimensions, mesh_resolution, flow_context, parsed_params)
    else:
        raise ValueError(f"Unsupported geometry type: {geometry_type}")


def get_resolution_multiplier(mesh_resolution: str) -> float:
    """Get resolution multiplier based on mesh resolution setting."""
    resolution_map = {
        "coarse": 0.5,
        "medium": 1.0,
        "fine": 2.0,
        "very_fine": 4.0
    }
    return resolution_map.get(mesh_resolution, 1.0)


def generate_cylinder_mesh(dimensions: Dict[str, float], resolution: str = "medium", 
                          is_external_flow: bool = True, flow_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate mesh configuration for cylinder geometry."""
    diameter = dimensions.get("diameter", 0.1)  # Default 0.1m diameter
    length = dimensions.get("length", diameter * 0.1)  # Default thin slice for 2D
    
    # Determine if this is a 2D or 3D case based on length
    # If length is very small compared to diameter, it's 2D
    is_2d = length < diameter * 0.2  # Less than 20% of diameter means 2D
    
    if is_external_flow:
        # External flow around cylinder - create proper O-grid mesh
        domain_multiplier = flow_context.get("domain_size_multiplier", 20.0) if flow_context else 20.0
        
        # Domain dimensions
        domain_length = diameter * domain_multiplier
        domain_height = diameter * (domain_multiplier / 2)  # Typically half in height
        domain_upstream = diameter * (domain_multiplier * 0.4)  # 40% upstream
        domain_downstream = diameter * (domain_multiplier * 0.6)  # 60% downstream
        
        # For 3D, ensure adequate domain width
        if is_2d:
            domain_width = length
            n_cells_z = 1
        else:
            # For 3D, domain width should be wider than cylinder length
            domain_width = max(length * 4, diameter * domain_multiplier / 2)
            # Calculate z cells based on resolution
            base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
            n_cells_z = max(int(base_resolution * domain_width / domain_length), 10)
        
        # Get resolution count
        base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
        
        # Use snappyHexMesh for proper cylinder geometry
        mesh_config = {
            "type": "snappyHexMesh",
            "mesh_topology": "snappy",
            "geometry_type": "cylinder",
            "is_external_flow": True,
            "is_2d": is_2d,
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "background_mesh": {
                # Background mesh (will be refined by snappyHexMesh)
                "type": "blockMesh",
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "n_cells_x": int(base_resolution * 1.5),
                "n_cells_y": int(base_resolution * 0.75),
                "n_cells_z": n_cells_z
            },
            "geometry": {
                "cylinder": {
                    "type": "cylinder",
                    "point1": [domain_upstream, domain_height/2, (domain_width - length)/2] if not is_2d else [domain_upstream, domain_height/2, 0],
                    "point2": [domain_upstream, domain_height/2, (domain_width + length)/2] if not is_2d else [domain_upstream, domain_height/2, length],
                    "radius": diameter / 2.0
                }
            },
            "snappy_settings": {
                "castellated_mesh": True,
                "snap": True,
                "add_layers": False,  # Disabled for faster execution - can be enabled later
                "refinement_levels": {
                    "min": 1,
                    "max": 2  # Reduced for faster execution
                },
                "refinement_region": {
                    # Refinement box around cylinder
                    "min": [domain_upstream - diameter*2, domain_height/2 - diameter*2, 0],
                    "max": [domain_upstream + diameter*3, domain_height/2 + diameter*2, length]
                },
                "layers": {
                    "n_layers": 5,
                    "expansion_ratio": 1.3,
                    "final_layer_thickness": 0.7,
                    "min_thickness": 0.1
                }
            },
            "dimensions": {
                "cylinder_diameter": diameter,
                "cylinder_length": length,
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_upstream": domain_upstream,
                "domain_downstream": domain_downstream,
                "cylinder_center_x": domain_upstream,
                "cylinder_center_y": domain_height / 2,
                "diameter": diameter  # Also store standard diameter key
            },
            "resolution": {
                "background": base_resolution,
                "surface": base_resolution * 2,
                "refinement": base_resolution * 4
            },
            "total_cells": base_resolution * base_resolution * 8,  # Estimate after refinement
            "quality_metrics": {
                "aspect_ratio": 1.5,
                "quality_score": 0.9  # High quality with snappyHexMesh
            }
        }
        
        # Original O-grid implementation (commented out for now)
        """
        # O-grid mesh parameters
        circumferential_cells = base_resolution * 2  # Around cylinder
        radial_cells = int(base_resolution * 0.8)  # From cylinder to far field
        wake_cells = int(base_resolution * 1.5)  # Downstream refinement
        upstream_cells = int(base_resolution * 0.5)  # Upstream cells
        axial_cells = 1  # Force 1 cell for 2D
        
        # Mesh grading for boundary layer and wake
        radial_grading = 5.0  # Expansion ratio from cylinder surface
        wake_grading = 3.0  # Expansion in wake region
        
        # Boundary layer parameters
        first_layer_height = diameter * 1e-5  # y+ ~ 1 for Re=1000-10000
        boundary_layer_cells = min(20, int(radial_cells * 0.3))
        expansion_ratio = 1.2
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "o-grid",
            "geometry_type": "cylinder",
            "is_external_flow": True,
            "dimensions": {
                "cylinder_diameter": diameter,
                "cylinder_length": length,
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_upstream": domain_upstream,
                "domain_downstream": domain_downstream,
                "cylinder_center_x": domain_upstream,
                "cylinder_center_y": domain_height / 2
            },
            "resolution": {
                "circumferential": circumferential_cells,
                "radial": radial_cells,
                "wake": wake_cells,
                "upstream": upstream_cells,
                "axial": axial_cells
            },
            "grading": {
                "radial": radial_grading,
                "wake": wake_grading
            },
            "boundary_layer": {
                "enabled": True,
                "first_layer_height": first_layer_height,
                "layers": boundary_layer_cells,
                "expansion_ratio": expansion_ratio
            },
            "total_cells": (circumferential_cells * radial_cells + 
                          wake_cells * radial_cells + 
                          upstream_cells * radial_cells) * axial_cells,
            "quality_metrics": {
                "aspect_ratio": calculate_aspect_ratio(first_layer_height, diameter/circumferential_cells),
                "expansion_ratio": expansion_ratio,
                "y_plus_estimate": estimate_y_plus(first_layer_height, diameter, 10.0)  # Assuming Re~10000
            }
        }
        """
        
    else:
        # Internal flow (cylinder in a channel) - simplified rectangular mesh
        # This is unusual for cylinders but supported
        channel_length = dimensions.get("length", diameter * 20)
        channel_height = dimensions.get("channel_height", diameter * 5)
        channel_width = dimensions.get("channel_width", channel_height)  # Default to square cross-section
        
        base_resolution = {"coarse": 20, "medium": 40, "fine": 80}.get(resolution, 40)
        
        # Determine spanwise cells based on whether it's 2D or 3D
        if channel_width < diameter * 0.2:  # 2D case
            spanwise_cells = 1
            is_2d = True
        else:
            spanwise_cells = int(base_resolution * channel_width / channel_height)
            is_2d = False
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "structured",
            "geometry_type": "cylinder_in_channel",
            "is_external_flow": False,
            "is_2d": is_2d,
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "dimensions": {
                "cylinder_diameter": diameter,
                "channel_length": channel_length,
                "channel_height": channel_height,
                "channel_width": channel_width,
                "diameter": diameter  # Also store standard diameter key
            },
            "resolution": {
                "streamwise": base_resolution * 2,
                "normal": base_resolution,
                "spanwise": spanwise_cells
            },
            "total_cells": base_resolution * base_resolution * 2 * spanwise_cells,
            "use_toposet": False,  # Still disabled due to internal boundary issues
            "quality_metrics": {
                "aspect_ratio": 2.0,
                "quality_score": 0.8
            }
        }
    
    return mesh_config


def generate_airfoil_mesh(dimensions: Dict[str, float], resolution: str = "medium", 
                         is_external_flow: bool = True, flow_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate mesh configuration for airfoil geometry."""
    chord = dimensions.get("chord", 0.1)
    span = dimensions.get("span", chord * 0.1)  # Default thin span for 2D
    thickness = dimensions.get("thickness", chord * 0.12)  # NACA 0012 default
    
    # Determine if this is 2D or 3D
    is_2d = span < chord * 0.2  # Less than 20% of chord means 2D
    
    if is_external_flow:
        # External flow around airfoil
        domain_multiplier = flow_context.get("domain_size_multiplier", 30.0) if flow_context else 30.0
        
        # Domain dimensions
        domain_length = chord * domain_multiplier
        domain_height = chord * (domain_multiplier / 2)
        domain_upstream = chord * (domain_multiplier * 0.3)  # 30% upstream
        domain_downstream = chord * (domain_multiplier * 0.7)  # 70% downstream
        
        # For 3D, ensure adequate domain width
        if is_2d:
            domain_width = span
            n_cells_z = 1
        else:
            domain_width = max(span * 4, chord * domain_multiplier / 2)
            base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
            n_cells_z = max(int(base_resolution * domain_width / domain_length), 10)
        
        # Get resolution count
        base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
        
        # Use snappyHexMesh for proper airfoil geometry
        mesh_config = {
            "type": "snappyHexMesh",
            "mesh_topology": "snappy",
            "geometry_type": "airfoil",
            "is_external_flow": True,
            "is_2d": is_2d,
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "background_mesh": {
                "type": "blockMesh",
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "n_cells_x": int(base_resolution * 2),
                "n_cells_y": int(base_resolution * 1),
                "n_cells_z": n_cells_z
            },
            "geometry": {
                "airfoil": {
                    "type": "airfoil",
                    "chord": chord,
                    "span": span,
                    "thickness": thickness,
                    "center": [domain_upstream, domain_height/2, domain_width/2]
                }
            },
            "snappy_settings": {
                "castellated_mesh": True,
                "snap": True,
                "add_layers": True,  # Important for airfoil accuracy
                "refinement_levels": {
                    "min": 2,
                    "max": 3  # Higher refinement for airfoil
                },
                "refinement_region": {
                    # Refinement box around airfoil
                    "min": [domain_upstream - chord*0.5, domain_height/2 - chord*2, 0],
                    "max": [domain_upstream + chord*1.5, domain_height/2 + chord*2, domain_width]
                },
                "layers": {
                    "n_layers": 10,  # More layers for airfoil
                    "expansion_ratio": 1.2,
                    "final_layer_thickness": 0.5,
                    "min_thickness": 0.1
                }
            },
            "dimensions": {
                "airfoil_chord": chord,
                "airfoil_span": span,
                "airfoil_thickness": thickness,
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_upstream": domain_upstream,
                "domain_downstream": domain_downstream,
                "airfoil_center_x": domain_upstream,
                "airfoil_center_y": domain_height / 2,
                "chord": chord  # Also store standard chord key
            },
            "resolution": {
                "background": base_resolution,
                "surface": base_resolution * 3,  # Higher surface refinement for airfoil
                "refinement": base_resolution * 6
            },
            "total_cells": base_resolution * base_resolution * 12,  # Estimate after refinement
            "quality_metrics": {
                "aspect_ratio": 1.3,
                "quality_score": 0.95  # High quality needed for airfoil
            }
        }
    else:
        # Internal flow (airfoil in channel) - rare but supported
        channel_length = dimensions.get("length", chord * 20)
        channel_height = dimensions.get("channel_height", chord * 5)
        channel_width = dimensions.get("channel_width", span * 5)
        
        base_resolution = {"coarse": 20, "medium": 40, "fine": 80}.get(resolution, 40)
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "structured",
            "geometry_type": "airfoil_in_channel",
            "is_external_flow": False,
            "is_2d": is_2d,
            "dimensions": {
                "airfoil_chord": chord,
                "channel_length": channel_length,
                "channel_height": channel_height,
                "channel_width": channel_width,
                "chord": chord
            },
            "resolution": {
                "streamwise": base_resolution * 2,
                "normal": base_resolution,
                "spanwise": 1 if is_2d else int(base_resolution * 0.5)
            },
            "total_cells": base_resolution * base_resolution * 2,
            "quality_metrics": {
                "aspect_ratio": 2.0,
                "quality_score": 0.8
            }
        }
    
    return mesh_config


def generate_pipe_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for pipe geometry."""
    diameter = dimensions.get("diameter", 0.05)
    length = dimensions.get("length", 1.0)
    
    # Base mesh resolution
    base_resolution = int(30 * resolution_multiplier)
    
    mesh_config = {
        "type": "blockMesh",
        "mesh_topology": "structured",
        "geometry_type": "pipe",
        "is_external_flow": False,
        "is_2d": False,
        "is_custom_geometry": False,
        "stl_file": None,
        "stl_name": None,
        "dimensions": {
            "diameter": diameter,
            "length": length
        },
        "resolution": {
            "circumferential": max(int(base_resolution * 0.8), 16),
            "radial": max(int(base_resolution * 0.4), 8),
            "axial": max(int(base_resolution * 2.0), 40)
        },
        "blocks": generate_pipe_blocks(diameter, length, base_resolution),
        "total_cells": 0,
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch",
            "walls": "wall"
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
    return mesh_config


def generate_channel_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for channel geometry."""
    width = dimensions.get("width", 0.1)
    height = dimensions.get("height", 0.02)
    length = dimensions.get("length", 1.0)
    
    # Base mesh resolution
    base_resolution = int(40 * resolution_multiplier)
    
    mesh_config = {
        "type": "blockMesh",
        "mesh_topology": "structured",
        "geometry_type": "channel",
        "is_external_flow": False,
        "is_2d": False,
        "is_custom_geometry": False,
        "stl_file": None,
        "stl_name": None,
        "dimensions": {
            "width": width,
            "height": height,
            "length": length
        },
        "resolution": {
            "streamwise": max(int(base_resolution * 2.0), 50),
            "normal": max(int(base_resolution * 0.5), 15),
            "spanwise": max(int(base_resolution * 0.3), 8)
        },
        "blocks": generate_channel_blocks(width, height, length, base_resolution),
        "total_cells": 0,
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch",
            "walls": "wall",
            "sides": "empty"
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
    return mesh_config


def generate_sphere_mesh(dimensions: Dict[str, float], resolution: str = "medium", 
                        is_external_flow: bool = True, flow_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate mesh configuration for sphere geometry."""
    diameter = dimensions.get("diameter", 0.1)
    
    if is_external_flow:
        # External flow around sphere - must be 3D
        domain_multiplier = flow_context.get("domain_size_multiplier", 20.0) if flow_context else 20.0
        
        # Domain dimensions - sphere requires 3D domain
        domain_length = diameter * domain_multiplier
        domain_height = diameter * domain_multiplier
        domain_width = diameter * domain_multiplier
        domain_upstream = diameter * (domain_multiplier * 0.4)  # 40% upstream
        domain_downstream = diameter * (domain_multiplier * 0.6)  # 60% downstream
        
        # Get resolution count
        base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
        
        # Use snappyHexMesh for proper sphere geometry
        mesh_config = {
            "type": "snappyHexMesh",
            "mesh_topology": "snappy",
            "geometry_type": "sphere",
            "is_external_flow": True,
            "is_2d": False,  # Sphere is always 3D
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "background_mesh": {
                "type": "blockMesh",
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "n_cells_x": int(base_resolution * 1.5),
                "n_cells_y": int(base_resolution * 1.5),
                "n_cells_z": int(base_resolution * 1.5)
            },
            "geometry": {
                "sphere": {
                    "type": "sphere",
                    "center": [domain_upstream, domain_height/2, domain_width/2],
                    "radius": diameter / 2.0
                }
            },
            "snappy_settings": {
                "castellated_mesh": True,
                "snap": True,
                "add_layers": True,  # Boundary layers for sphere
                "refinement_levels": {
                    "min": 1,
                    "max": 3  # Higher refinement for curved surface
                },
                "refinement_region": {
                    # Refinement box around sphere
                    "min": [domain_upstream - diameter*2, domain_height/2 - diameter*2, domain_width/2 - diameter*2],
                    "max": [domain_upstream + diameter*3, domain_height/2 + diameter*2, domain_width/2 + diameter*2]
                },
                "layers": {
                    "n_layers": 8,
                    "expansion_ratio": 1.3,
                    "final_layer_thickness": 0.7,
                    "min_thickness": 0.1
                }
            },
            "dimensions": {
                "sphere_diameter": diameter,
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "domain_upstream": domain_upstream,
                "domain_downstream": domain_downstream,
                "sphere_center_x": domain_upstream,
                "sphere_center_y": domain_height / 2,
                "sphere_center_z": domain_width / 2,
                "diameter": diameter  # Also store standard diameter key
            },
            "resolution": {
                "background": base_resolution,
                "surface": base_resolution * 3,  # Higher for curved surface
                "refinement": base_resolution * 5
            },
            "total_cells": base_resolution * base_resolution * base_resolution * 10,  # Estimate after refinement
            "quality_metrics": {
                "aspect_ratio": 1.5,
                "quality_score": 0.9  # High quality with snappyHexMesh
            }
        }
    else:
        # Internal flow (sphere in duct) - less common
        duct_diameter = dimensions.get("duct_diameter", diameter * 3)
        duct_length = dimensions.get("duct_length", diameter * 10)
        
        base_resolution = {"coarse": 20, "medium": 40, "fine": 80}.get(resolution, 40)
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "structured",
            "geometry_type": "sphere_in_duct",
            "is_external_flow": False,
            "is_2d": False,  # Always 3D
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "dimensions": {
                "sphere_diameter": diameter,
                "duct_diameter": duct_diameter,
                "duct_length": duct_length,
                "diameter": diameter
            },
            "resolution": {
                "axial": base_resolution * 2,
                "radial": base_resolution,
                "circumferential": base_resolution
            },
            "total_cells": base_resolution * base_resolution * base_resolution * 2,
            "quality_metrics": {
                "aspect_ratio": 2.0,
                "quality_score": 0.8
            }
        }
    
    return mesh_config


def generate_cube_mesh(dimensions: Dict[str, float], resolution: str = "medium", is_external_flow: bool = True, flow_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate mesh configuration for cube geometry."""
    side_length = dimensions.get("side_length", 0.1)
    
    # Get resolution count  
    base_resolution = {"coarse": 15, "medium": 30, "fine": 60, "very_fine": 90}.get(resolution, 30)
    
    if is_external_flow:
        # External flow around cube
        domain_multiplier = flow_context.get("domain_size_multiplier", 20.0) if flow_context else 20.0
        
        # Domain dimensions
        domain_length = side_length * domain_multiplier
        domain_height = side_length * (domain_multiplier / 2)  # Typically half in height
        domain_upstream = side_length * (domain_multiplier * 0.4)  # 40% upstream
        domain_downstream = side_length * (domain_multiplier * 0.6)  # 60% downstream
        
        # For 2D (square), use thin domain width
        is_2d = dimensions.get("is_2d", False) or side_length < 0.02  # Less than 2cm suggests 2D
        if is_2d:
            domain_width = side_length * 0.1  # Thin slice for 2D
            n_cells_z = 1
        else:
            # For 3D, domain width should be similar to height
            domain_width = domain_height
            n_cells_z = int(base_resolution * 1.5)
    
        mesh_config = {
            "type": "snappyHexMesh",
            "mesh_topology": "snappy",
            "geometry_type": "cube",
            "is_external_flow": is_external_flow,
            "is_2d": is_2d,
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "background_mesh": {
                "type": "blockMesh",
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "n_cells_x": int(base_resolution * 1.5),
                "n_cells_y": int(base_resolution * 0.75),
                "n_cells_z": n_cells_z
            },
            "geometry": {
                "cube": {
                    "type": "cube",
                    "min": [domain_upstream - side_length/2, domain_height/2 - side_length/2, domain_width/2 - side_length/2],
                    "max": [domain_upstream + side_length/2, domain_height/2 + side_length/2, domain_width/2 + side_length/2]
                }
            },
            "snappy_settings": {
                "castellated_mesh": True,
                "snap": True,
                "add_layers": False,
                "refinement_levels": {
                    "min": 1,
                    "max": 2
                },
                "refinement_region": {
                    # Refinement box around cube
                    "min": [domain_upstream - side_length*2, domain_height/2 - side_length*2, 0],
                    "max": [domain_upstream + side_length*3, domain_height/2 + side_length*2, domain_width]
                },
                "layers": {
                    "n_layers": 5,
                    "expansion_ratio": 1.3,
                    "final_layer_thickness": 0.7,
                    "min_thickness": 0.1
                }
            },
            "dimensions": {
                "cube_side_length": side_length,
                "domain_length": domain_length,
                "domain_height": domain_height,
                "domain_width": domain_width,
                "domain_upstream": domain_upstream,
                "domain_downstream": domain_downstream,
                "cube_center_x": domain_upstream,
                "cube_center_y": domain_height / 2,
                "cube_center_z": domain_width / 2,
                "side_length": side_length  # Also store standard key
            },
            "resolution": {
                "background": base_resolution,
                "surface": base_resolution * 2,
                "refinement": base_resolution * 4
            },
            "total_cells": base_resolution * base_resolution * 8, # Estimate after refinement
            "quality_metrics": {
                "aspect_ratio": 1.5,
                "quality_score": 0.9
            }
        }
    else:
        # Internal flow (cube in channel) - less common
        channel_length = dimensions.get("length", side_length * 20)
        channel_height = dimensions.get("channel_height", side_length * 5)
        channel_width = dimensions.get("channel_width", channel_height)
        
        base_resolution = {"coarse": 20, "medium": 40, "fine": 80}.get(resolution, 40)
        
        # Determine if 2D or 3D
        is_2d = channel_width < side_length * 0.2
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "structured",
            "geometry_type": "cube_in_channel",
            "is_external_flow": False,
            "is_2d": is_2d,
            "is_custom_geometry": False,
            "stl_file": None,
            "stl_name": None,
            "dimensions": {
                "cube_side_length": side_length,
                "channel_length": channel_length,
                "channel_height": channel_height,
                "channel_width": channel_width,
                "side_length": side_length
            },
            "resolution": {
                "streamwise": base_resolution * 2,
                "normal": base_resolution,
                "spanwise": 1 if is_2d else int(base_resolution * 0.5)
            },
            "total_cells": base_resolution * base_resolution * 2,
            "quality_metrics": {
                "aspect_ratio": 2.0,
                "quality_score": 0.8
            }
        }
    
    return mesh_config


def generate_nozzle_mesh(dimensions: Dict[str, float], mesh_resolution: str, flow_context: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for nozzle geometry using snappyHexMesh with STL."""
    from pathlib import Path
    throat_diameter = dimensions.get("throat_diameter", 0.05)
    inlet_diameter = dimensions.get("inlet_diameter", throat_diameter * 1.5)
    outlet_diameter = dimensions.get("outlet_diameter", throat_diameter * 2.0)
    length = dimensions.get("length", throat_diameter * 10)
    convergent_length = dimensions.get("convergent_length", length * 0.3)
    divergent_length = dimensions.get("divergent_length", length * 0.7)
    
    # Get base resolution settings
    base_resolution = {"coarse": 30, "medium": 50, "fine": 80, "very_fine": 120}.get(mesh_resolution, 50)
    
    # Domain dimensions - larger for snappyHexMesh background mesh
    max_diameter = max(inlet_diameter, outlet_diameter)
    domain_height = max_diameter * 4.0  # Extra space for background mesh
    domain_width = max_diameter * 4.0   # Extra space for background mesh
    domain_length = length * 1.5       # Extra space upstream and downstream
    
    # Generate nozzle STL file
    nozzle_stl_path = generate_nozzle_stl(
        throat_diameter=throat_diameter,
        inlet_diameter=inlet_diameter,
        outlet_diameter=outlet_diameter,
        length=length,
        convergent_length=convergent_length,
        divergent_length=divergent_length
    )
    
    # Use snappyHexMesh for proper nozzle geometry
    mesh_config = {
        "type": "snappyHexMesh",
        "mesh_topology": "snappy",
        "geometry_type": "nozzle",
        "is_external_flow": False,
        "is_2d": False,
        "is_custom_geometry": True,
        "stl_file": nozzle_stl_path,
        "stl_name": "nozzle",
        "background_mesh": {
            "type": "blockMesh",
            "domain_length": domain_length,
            "domain_height": domain_height,
            "domain_width": domain_width,
            "n_cells_x": int(base_resolution * 1.5),
            "n_cells_y": int(base_resolution * 0.75),
            "n_cells_z": int(base_resolution * 0.75)
        },
        "geometry": {
            "nozzle": {
                "type": "triSurfaceMesh",
                "file": f'"{Path(nozzle_stl_path).name}"'
            }
        },
        "dimensions": {
            "throat_diameter": throat_diameter,
            "inlet_diameter": inlet_diameter,
            "outlet_diameter": outlet_diameter,
            "length": length,
            "convergent_length": convergent_length,
            "divergent_length": divergent_length,
            "domain_height": domain_height,
            "domain_width": domain_width,
            "domain_length": domain_length,
            "characteristic_length": throat_diameter  # Use throat diameter as characteristic length
        },
        "resolution": {
            "base_resolution": base_resolution,
            "surface_resolution": base_resolution * 2,  # Higher resolution on nozzle surface
            "volume_resolution": base_resolution
        },
        "snappy_settings": {
            "castellated_mesh": True,
            "snap": True,
            "add_layers": True,
            "refinement_levels": {
                "min": 1,
                "max": 2
            },
            "refinement_region": {
                # Refinement box around nozzle
                "min": [0, -max_diameter*2, -max_diameter*2],
                "max": [length, max_diameter*2, max_diameter*2]
            },
            "location_in_mesh": [domain_length/4, domain_height/2, domain_width/2],  # Fixed: place within background mesh bounds
            "layers": {
                "n_layers": 5,
                "expansion_ratio": 1.3,
                "final_layer_thickness": 0.7,
                "min_thickness": 0.1
            }
        },
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch", 
            "nozzle": "wall",  # Nozzle surface as wall
            "top": "patch",    # Background mesh boundaries
            "bottom": "patch",
            "front": "patch", 
            "back": "patch"
        },
        "total_cells": base_resolution * base_resolution * 6,  # Estimate after refinement
        "quality_metrics": {
            "aspect_ratio": 2.0,  # Expected aspect ratio for snappy mesh
            "quality_score": 0.80  # Good quality for snappy mesh
        }
    }
    
    return mesh_config


def generate_nozzle_stl(throat_diameter: float, inlet_diameter: float, outlet_diameter: float, 
                       length: float, convergent_length: float, divergent_length: float) -> str:
    """Generate STL file for nozzle geometry."""
    import math
    import os
    
    # Create nozzle STL file
    stl_filename = f"nozzle_{throat_diameter:.3f}_{inlet_diameter:.3f}_{outlet_diameter:.3f}.stl"
    stl_path = os.path.join("stl", stl_filename)
    
    # Create stl directory if it doesn't exist
    os.makedirs("stl", exist_ok=True)
    
    # Generate nozzle geometry points
    n_axial = 60  # Number of points along axis
    n_theta = 24  # Number of points around circumference
    
    # Axial positions
    x_positions = []
    radii = []
    
    # Convergent section
    for i in range(int(n_axial * 0.3)):
        x = i / (n_axial * 0.3) * convergent_length
        progress = i / (n_axial * 0.3)
        r = (inlet_diameter / 2) - progress * (inlet_diameter / 2 - throat_diameter / 2)
        x_positions.append(x)
        radii.append(r)
    
    # Throat section (short constant diameter)
    throat_section_length = length - convergent_length - divergent_length
    for i in range(int(n_axial * 0.1)):
        x = convergent_length + i / (n_axial * 0.1) * throat_section_length
        x_positions.append(x)
        radii.append(throat_diameter / 2)
    
    # Divergent section
    for i in range(int(n_axial * 0.6)):
        x = convergent_length + throat_section_length + i / (n_axial * 0.6) * divergent_length
        progress = i / (n_axial * 0.6)
        r = (throat_diameter / 2) + progress * (outlet_diameter / 2 - throat_diameter / 2)
        x_positions.append(x)
        radii.append(r)
    
    # Generate STL triangles
    triangles = []
    
    # Generate surface triangles
    for i in range(len(x_positions) - 1):
        for j in range(n_theta):
            # Current ring
            theta1 = 2 * math.pi * j / n_theta
            theta2 = 2 * math.pi * ((j + 1) % n_theta) / n_theta
            
            # Current points
            x1, r1 = x_positions[i], radii[i]
            x2, r2 = x_positions[i + 1], radii[i + 1]
            
            # Points on current ring
            p1 = (x1, r1 * math.cos(theta1), r1 * math.sin(theta1))
            p2 = (x1, r1 * math.cos(theta2), r1 * math.sin(theta2))
            
            # Points on next ring
            p3 = (x2, r2 * math.cos(theta1), r2 * math.sin(theta1))
            p4 = (x2, r2 * math.cos(theta2), r2 * math.sin(theta2))
            
            # Two triangles per quad
            triangles.append([p1, p2, p3])
            triangles.append([p2, p4, p3])
    
    # Add inlet and outlet caps
    # Inlet cap
    inlet_center = (0, 0, 0)
    for j in range(n_theta):
        theta1 = 2 * math.pi * j / n_theta
        theta2 = 2 * math.pi * ((j + 1) % n_theta) / n_theta
        
        p1 = (0, (inlet_diameter / 2) * math.cos(theta1), (inlet_diameter / 2) * math.sin(theta1))
        p2 = (0, (inlet_diameter / 2) * math.cos(theta2), (inlet_diameter / 2) * math.sin(theta2))
        
        triangles.append([inlet_center, p2, p1])  # Inward normal
    
    # Outlet cap
    outlet_center = (length, 0, 0)
    for j in range(n_theta):
        theta1 = 2 * math.pi * j / n_theta
        theta2 = 2 * math.pi * ((j + 1) % n_theta) / n_theta
        
        p1 = (length, (outlet_diameter / 2) * math.cos(theta1), (outlet_diameter / 2) * math.sin(theta1))
        p2 = (length, (outlet_diameter / 2) * math.cos(theta2), (outlet_diameter / 2) * math.sin(theta2))
        
        triangles.append([outlet_center, p1, p2])  # Outward normal
    
    # Write STL file
    with open(stl_path, 'w') as f:
        f.write("solid nozzle\n")
        
        for triangle in triangles:
            # Calculate normal vector
            v1 = [triangle[1][i] - triangle[0][i] for i in range(3)]
            v2 = [triangle[2][i] - triangle[0][i] for i in range(3)]
            normal = [
                v1[1] * v2[2] - v1[2] * v2[1],
                v1[2] * v2[0] - v1[0] * v2[2],
                v1[0] * v2[1] - v1[1] * v2[0]
            ]
            
            # Normalize
            length_n = math.sqrt(sum(n**2 for n in normal))
            if length_n > 0:
                normal = [n / length_n for n in normal]
            
            f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
            f.write("    outer loop\n")
            for point in triangle:
                f.write(f"      vertex {point[0]:.6f} {point[1]:.6f} {point[2]:.6f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        
        f.write("endsolid nozzle\n")
    
    return stl_path


def generate_nozzle_blocks(throat_diameter: float, inlet_diameter: float, outlet_diameter: float, length: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for nozzle mesh."""
    return {
        "block_count": 3,  # Convergent, throat, divergent sections
        "sections": {
            "convergent": {
                "inlet_diameter": inlet_diameter,
                "outlet_diameter": throat_diameter,
                "grading": 1.0
            },
            "throat": {
                "diameter": throat_diameter,
                "grading": 1.0
            },
            "divergent": {
                "inlet_diameter": throat_diameter,
                "outlet_diameter": outlet_diameter,
                "grading": 1.0
            }
        },
        "boundary_layer": {
            "enabled": True,
            "first_layer_thickness": throat_diameter * 1e-4,
            "expansion_ratio": 1.15,
            "layers": 8
        }
    }


def generate_cylinder_blocks(diameter: float, domain_width: float, domain_height: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for cylinder mesh."""
    # This is a simplified block structure
    # In a real implementation, this would generate the actual blockMeshDict content
    return {
        "block_count": 8,  # Typical O-grid around cylinder
        "grading": {
            "radial": 1.0,
            "circumferential": 1.0,
            "axial": 1.0
        },
        "boundary_layer": {
            "enabled": True,
            "first_layer_thickness": diameter * 1e-5,
            "expansion_ratio": 1.2,
            "layers": 10
        }
    }


def generate_airfoil_blocks(chord: float, domain_length: float, domain_height: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for airfoil mesh."""
    return {
        "block_count": 12,  # C-grid around airfoil
        "grading": {
            "chordwise": 1.0,
            "normal": 1.0,
            "spanwise": 1.0
        },
        "boundary_layer": {
            "enabled": True,
            "first_layer_thickness": chord * 1e-5,
            "expansion_ratio": 1.2,
            "layers": 15
        }
    }


def generate_pipe_blocks(diameter: float, length: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for pipe mesh."""
    return {
        "block_count": 1,  # Single block for pipe
        "grading": {
            "radial": 1.0,
            "circumferential": 1.0,
            "axial": 1.0
        },
        "boundary_layer": {
            "enabled": False  # Not typically needed for internal flow
        }
    }


def generate_channel_blocks(width: float, height: float, length: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for channel mesh."""
    return {
        "block_count": 1,  # Single block for channel
        "grading": {
            "streamwise": 1.0,
            "normal": 1.0,
            "spanwise": 1.0
        },
        "boundary_layer": {
            "enabled": True,
            "first_layer_thickness": height * 1e-4,
            "expansion_ratio": 1.15,
            "layers": 8
        }
    }


def generate_sphere_ogrid_blocks(diameter: float, domain_size: float, resolution: int) -> Dict[str, Any]:
    """Generate O-grid block structure for sphere mesh."""
    return {
        "block_count": 6,  # 6 blocks for O-grid around sphere
        "topology": "o-grid-3d",
        "inner_radius": diameter / 2,
        "outer_radius": domain_size / 2,
        "grading": {
            "radial": 5.0,  # Expansion from sphere surface
            "circumferential": 1.0,
            "meridional": 1.0
        }
    }


def generate_sphere_internal_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh for sphere in internal flow (duct)."""
    diameter = dimensions.get("diameter", 0.1)
    duct_diameter = dimensions.get("duct_diameter", diameter * 3)
    duct_length = dimensions.get("duct_length", diameter * 10)
    
    base_resolution = int(40 * resolution_multiplier)
    
    return {
        "type": "blockMesh",
        "mesh_topology": "structured",
        "geometry_type": "sphere_in_duct",
        "is_external_flow": False,
        "dimensions": {
            "sphere_diameter": diameter,
            "duct_diameter": duct_diameter,
            "duct_length": duct_length
        },
        "resolution": {
            "axial": base_resolution * 2,
            "radial": base_resolution,
            "circumferential": base_resolution
        },
        "total_cells": base_resolution * base_resolution * base_resolution * 2
    }


def generate_stl_mesh_config(stl_file: str, mesh_resolution: str, flow_context: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for STL file geometry using snappyHexMesh."""
    import os
    from pathlib import Path
    import re
    
    # Get base resolution settings
    base_resolution = {"coarse": 20, "medium": 40, "fine": 80, "very_fine": 120}.get(mesh_resolution, 40)
    
    # Analyze STL file to get actual dimensions
    logger.info(f"Analyzing STL file dimensions: {stl_file}")
    stl_analysis = analyze_stl_bounding_box(stl_file)
    characteristic_length = stl_analysis["scaled_characteristic_length"]
    stl_center = stl_analysis["center"]  # Get center from analysis
    
    # Apply validation and corrections
    stl_analysis = validate_stl_dimensions(stl_analysis)
    
    # Use actual STL dimensions
    stl_dims = stl_analysis["dimensions"]
    
    # Calculate adaptive mesh parameters
    adaptive_params = calculate_adaptive_mesh_parameters(characteristic_length, base_resolution)
    
    # Extract calculated values
    domain_length = adaptive_params["domain_length"]
    domain_height = adaptive_params["domain_height"]
    domain_width = adaptive_params["domain_width"]
    
    # Log the analysis results
    if stl_analysis.get("validation", {}).get("warnings"):
        for warning in stl_analysis["validation"]["warnings"]:
            logger.warning(f"STL Analysis: {warning}")
    
    # Add adaptive warnings to state
    if adaptive_params.get("warnings"):
        for warning in adaptive_params["warnings"]:
            logger.warning(f"Adaptive Mesh: {warning}")
    
    logger.info(f"STL Mesh Config - Characteristic length: {characteristic_length:.3f}")
    logger.info(f"STL Mesh Config - Domain: {domain_length:.3f} x {domain_height:.3f} x {domain_width:.3f}")
    logger.info(f"STL Mesh Config - Units detected: {stl_analysis['detected_units']}")
    logger.info(f"STL Mesh Config - Scale factor applied: {stl_analysis['scale_factor']}")
    
    # Create a valid OpenFOAM dictionary name from STL filename
    # Remove extension and ensure it's a valid C++ identifier
    stl_basename = Path(stl_file).stem
    # Replace invalid characters and ensure it doesn't start with a number
    surface_name = re.sub(r'[^a-zA-Z0-9_]', '_', stl_basename)
    if surface_name[0].isdigit():
        surface_name = f"surface_{surface_name}"
    
    # For STL files, we need a background mesh and snappyHexMesh configuration
    mesh_config = {
        "type": "snappyHexMesh",
        "mesh_topology": "snappy",
        "geometry_type": "custom_stl",
        "is_external_flow": True,
        "is_2d": False,  # STL files are always 3D
        "is_custom_geometry": True,
        "stl_file": stl_file,
        "stl_name": surface_name,  # Use cleaned name for OpenFOAM
        
        # Background mesh configuration with adaptive parameters
        "background_mesh": {
            "type": "blockMesh",
            "domain_length": domain_length,
            "domain_height": domain_height,
            "domain_width": domain_width,
            "n_cells_x": adaptive_params["cells_x"],
            "n_cells_y": adaptive_params["cells_y"],
            "n_cells_z": adaptive_params["cells_z"],
            # Create a box domain centered around the STL geometry
            # Place inlet upstream and outlet downstream of the STL
            "vertices": create_adaptive_domain_vertices(
                domain_length, domain_height, domain_width, 
                stl_center, characteristic_length, adaptive_params["domain_multiplier"]
            )
        },
        
        # Geometry configuration for snappyHexMesh
        "geometry": {
            surface_name: {  # Use the cleaned surface name
                "type": "triSurfaceMesh",
                "file": f"{Path(stl_file).name}",  # Just the filename, will be copied to case
                "regions": {}
            }
        },
        
        # SnappyHexMesh settings with adaptive refinement
        "snappy_settings": {
            "castellated_mesh": True,
            "snap": True,
            "add_layers": False,  # Start without layers for robustness, can be enabled later
            "refinement_levels": {
                "min": adaptive_params["min_refinement"],
                "max": adaptive_params["max_refinement"],
                "surface_level": adaptive_params["min_refinement"] + 1
            },
            "refinement_regions": {
                "global": {
                    "min": [0, 0, 0],
                    "max": [domain_length, domain_height, domain_width],
                    "level": 0  # Base level
                }
            },
            # Adaptive locationInMesh based on STL position and domain
            "location_in_mesh": calculate_adaptive_location_in_mesh(
                create_adaptive_domain_vertices(
                    domain_length, domain_height, domain_width, 
                    stl_center, characteristic_length, adaptive_params["domain_multiplier"]
                ), 
                stl_center
            ),
            "layers": {
                "n_layers": 3,
                "expansion_ratio": 1.3,
                "final_layer_thickness": 0.7,
                "min_thickness": 0.1
            },
            # Mesh quality controls - adjusted based on resolution
            "mesh_quality": {
                "maxNonOrtho": 75 if adaptive_params["cells_per_object"] < 20 else 65,
                "maxBoundarySkewness": 25,
                "maxInternalSkewness": 6,
                "maxConcave": 85,
                "minVol": 1e-15,
                "minTetQuality": -1e30,
                "minArea": -1,
                "minTwist": 0.01,
                "minDeterminant": 0.0001,
                "minFaceWeight": 0.01,
                "minVolRatio": 0.005,
                "minTriangleTwist": -1,
                "nSmoothScale": 4,
                "errorReduction": 0.75
            }
        },
        
        # Dimensions for boundary condition setup
        "dimensions": {
            "domain_length": domain_length,
            "domain_height": domain_height,
            "domain_width": domain_width,
            "characteristic_length": characteristic_length,
            "is_3d": True
        },
        
        # STL analysis results for reference
        "stl_analysis": stl_analysis,
        
        # Adaptive mesh parameters for reference
        "adaptive_params": adaptive_params,
        
        # Resolution settings
        "resolution": {
            "background": base_resolution,
            "surface": base_resolution * 1.5,
            "refinement": base_resolution * 2
        },
        
        # Estimated cell count
        "total_cells": adaptive_params["total_cells"],
        
        # Quality metrics
        "quality_metrics": {
            "aspect_ratio": 3.0,
            "quality_score": 0.75 if adaptive_params["cells_per_object"] < 20 else 0.85
        }
    }
    
    # Add flow-specific parameters
    if parsed_params.get("reynolds_number"):
        mesh_config["reynolds_number"] = parsed_params["reynolds_number"]
    
    if parsed_params.get("velocity"):
        mesh_config["inlet_velocity"] = parsed_params["velocity"]
    
    # Add rotation information if detected
    if parsed_params.get("rotation_info"):
        mesh_config["rotation_info"] = parsed_params["rotation_info"]
        logger.info(f"Mesh Generator: Added rotation info to mesh config: {parsed_params['rotation_info']}")
    
    return mesh_config


def calculate_total_cells(mesh_config: Dict[str, Any]) -> int:
    """Calculate total number of cells in the mesh."""
    resolution = mesh_config["resolution"]
    
    # Simple calculation based on resolution
    total_cells = 1
    for key, value in resolution.items():
        total_cells *= value
    
    return total_cells


def validate_mesh_config(mesh_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate mesh configuration."""
    errors = []
    warnings = []
    
    # Check total cells
    total_cells = mesh_config.get("total_cells", 0)
    if total_cells == 0:
        errors.append("Total cells is zero")
    elif total_cells > 1000000:
        warnings.append(f"Large mesh with {total_cells} cells - may be slow")
    
    # Check resolution
    resolution = mesh_config.get("resolution", {})
    for key, value in resolution.items():
        if value < 4:
            warnings.append(f"Low resolution in {key} direction: {value}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def estimate_mesh_quality(mesh_config: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate mesh quality based on configuration."""
    total_cells = mesh_config["total_cells"]
    resolution = mesh_config["resolution"]
    
    # Simple quality estimation
    quality_score = 0.8  # Base score
    
    # Penalize very low or very high cell counts
    if total_cells < 10000:
        quality_score -= 0.2
    elif total_cells > 500000:
        quality_score -= 0.1
    
    # Bonus for boundary layer mesh
    if mesh_config.get("blocks", {}).get("boundary_layer", {}).get("enabled", False):
        quality_score += 0.1
    
    # Ensure score is between 0 and 1
    quality_score = max(0.0, min(1.0, quality_score))
    
    return {
        "quality_score": quality_score,
        "total_cells": total_cells,
        "estimated_memory": total_cells * 1e-4,  # MB
        "estimated_time": total_cells * 1e-6,  # seconds per iteration
        "recommendations": generate_mesh_recommendations(mesh_config, quality_score)
    }


def generate_mesh_recommendations(mesh_config: Dict[str, Any], quality_score: float) -> list:
    """Generate mesh improvement recommendations."""
    recommendations = []
    
    if quality_score < 0.5:
        recommendations.append("Consider increasing mesh resolution")
    
    if mesh_config["total_cells"] > 500000:
        recommendations.append("Consider reducing mesh resolution for faster computation")
    
    if not mesh_config.get("blocks", {}).get("boundary_layer", {}).get("enabled", False):
        recommendations.append("Consider adding boundary layer mesh for better accuracy")
    
    return recommendations


def calculate_aspect_ratio(cell_height: float, cell_width: float) -> float:
    """Calculate mesh aspect ratio."""
    if cell_height == 0 or cell_width == 0:
        return 1.0
    return max(cell_height/cell_width, cell_width/cell_height)


def estimate_y_plus(first_layer_height: float, characteristic_length: float, velocity: float) -> float:
    """Estimate y+ value for boundary layer mesh."""
    # Simplified estimation assuming air at standard conditions
    nu = 1.5e-5  # Kinematic viscosity of air
    Re = velocity * characteristic_length / nu
    
    # Wall shear stress estimation
    Cf = 0.058 * Re**(-0.2)  # Flat plate correlation
    tau_w = 0.5 * 1.225 * velocity**2 * Cf
    u_tau = (tau_w / 1.225)**0.5
    
    # y+ calculation
    y_plus = first_layer_height * u_tau / nu
    
    return y_plus 
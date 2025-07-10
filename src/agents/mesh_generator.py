"""Mesh Generator Agent - Generates mesh configurations for different geometry types."""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import struct
from loguru import logger

from .state import CFDState, CFDStep, GeometryType


def analyze_stl_bounding_box(stl_file: str) -> Dict[str, Any]:
    """
    Analyze STL file to extract bounding box dimensions and characteristics.
    
    Returns:
        Dict containing bounding box info, characteristic length, center, etc.
    """
    stl_path = Path(stl_file)
    if not stl_path.exists():
        logger.error(f"STL file not found: {stl_file}")
        return get_default_stl_dimensions()
    
    try:
        # Read STL file and extract vertices
        vertices = extract_stl_vertices(stl_path)
        
        if not vertices:
            logger.warning(f"No vertices found in STL file: {stl_file}")
            return get_default_stl_dimensions()
        
        # Convert to numpy array for easier processing
        vertices = np.array(vertices)
        
        # Calculate bounding box
        min_coords = np.min(vertices, axis=0)
        max_coords = np.max(vertices, axis=0)
        
        # Calculate dimensions
        dimensions = max_coords - min_coords
        x_size, y_size, z_size = dimensions
        
        # Calculate characteristic length (largest dimension)
        characteristic_length = max(dimensions)
        
        # Calculate center
        center = [
            (min_coords[0] + max_coords[0]) / 2,
            (min_coords[1] + max_coords[1]) / 2,
            (min_coords[2] + max_coords[2]) / 2
        ]
        
        # Calculate volume estimate (bounding box volume)
        volume = np.prod(dimensions)
        
        # Detect likely units based on size
        units = detect_stl_units(characteristic_length)
        
        # Apply unit scaling if needed
        scale_factor = get_unit_scale_factor(units)
        
        # Calculate bounding box center
        bbox = {
            "min": min_coords.tolist(),
            "max": max_coords.tolist(),
            "dimensions": dimensions.tolist()
        }
        
        # Add center to bounding box info
        bbox['center'] = center
        
        # Prepare dimension dict
        dimensions_dict = {
            "x": float(x_size),
            "y": float(y_size), 
            "z": float(z_size)
        }
        
        result = {
            "bounding_box": bbox,
            "characteristic_length": float(characteristic_length),
            "scaled_characteristic_length": float(characteristic_length * scale_factor),
            "dimensions": dimensions_dict,
            "volume": float(volume),
            "detected_units": units,
            "scale_factor": scale_factor,
            "vertex_count": len(vertices),
            "center": center  # Add center at top level for easy access
        }
        
        logger.info(f"STL Analysis - File: {stl_path.name}")
        logger.info(f"  Dimensions: {x_size:.3f} x {y_size:.3f} x {z_size:.3f}")
        logger.info(f"  Characteristic length: {characteristic_length:.3f}")
        logger.info(f"  Detected units: {units}")
        logger.info(f"  Scale factor: {scale_factor}")
        logger.info(f"  Scaled characteristic length: {characteristic_length * scale_factor:.3f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing STL file {stl_file}: {e}")
        return get_default_stl_dimensions()


def extract_stl_vertices(stl_path: Path) -> List[List[float]]:
    """Extract all vertices from an STL file (ASCII or binary)."""
    vertices = []
    
    try:
        # Check if binary or ASCII
        with open(stl_path, 'rb') as f:
            header = f.read(80)
            
        if header.startswith(b'solid'):
            # ASCII STL
            vertices = extract_ascii_stl_vertices(stl_path)
        else:
            # Binary STL
            vertices = extract_binary_stl_vertices(stl_path)
            
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
            num_triangles = struct.unpack('<I', f.read(4))[0]
            
            for _ in range(num_triangles):
                # Read triangle data (normal + 3 vertices + attribute)
                data = struct.unpack('<12fH', f.read(50))
                
                # Extract vertices (skip normal at indices 0-2)
                v1 = [data[3], data[4], data[5]]
                v2 = [data[6], data[7], data[8]]
                v3 = [data[9], data[10], data[11]]
                
                vertices.extend([v1, v2, v3])
                
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
            "max": [0.1, 0.1, 0.1],
            "dimensions": [0.1, 0.1, 0.1],
            "center": [0.05, 0.05, 0.05]
        },
        "characteristic_length": 0.1,
        "scaled_characteristic_length": 0.1,
        "dimensions": {"x": 0.1, "y": 0.1, "z": 0.1},
        "volume": 0.001,
        "detected_units": "m",
        "scale_factor": 1.0,
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


def create_adaptive_domain_vertices(domain_length: float, domain_height: float, domain_width: float, 
                                   stl_center: List[float], characteristic_length: float, 
                                   domain_size_multiplier: float) -> List[List[float]]:
    """
    Create domain vertices that position the STL geometry optimally within the domain.
    
    Creates a background mesh domain starting from origin with positive extents.
    The STL will be positioned within this domain by snappyHexMesh.
    """
    # For background mesh, always start from origin and extend in positive directions
    # This ensures snappyHexMesh locationInMesh can be safely placed
    
    # Create a standard background mesh domain
    x_min, y_min, z_min = 0.0, 0.0, 0.0
    x_max = domain_length
    y_max = domain_height  
    z_max = domain_width
    
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
    The point must be within the background mesh domain bounds.
    """
    # Get domain bounds from the background mesh vertices
    x_coords = [v[0] for v in domain_vertices]
    y_coords = [v[1] for v in domain_vertices]
    z_coords = [v[2] for v in domain_vertices]
    
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    z_min, z_max = min(z_coords), max(z_coords)
    
    # Calculate a safe location within the background mesh bounds
    # Place it at 10% from the inlet (x_min) and centered in Y and Z
    safety_margin = 0.05  # 5% margin from boundaries
    
    location_x = x_min + (x_max - x_min) * 0.1  # 10% from inlet
    location_y = y_min + (y_max - y_min) * 0.5  # Center height  
    location_z = z_min + (z_max - z_min) * 0.5  # Center width
    
    # Apply safety margins to ensure we're well inside the domain
    location_x = max(x_min + (x_max - x_min) * safety_margin, 
                    min(location_x, x_max - (x_max - x_min) * safety_margin))
    location_y = max(y_min + (y_max - y_min) * safety_margin,
                    min(location_y, y_max - (y_max - y_min) * safety_margin))
    location_z = max(z_min + (z_max - z_min) * safety_margin,
                    min(location_z, z_max - (z_max - z_min) * safety_margin))
    
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
        "geometry_type": "pipe",
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
        "geometry_type": "channel",
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
    
    # Estimate domain size based on flow context
    domain_size_multiplier = flow_context.get("domain_size_multiplier", 20.0)
    
    # NEW: Analyze STL file to get actual dimensions
    logger.info(f"Analyzing STL file dimensions: {stl_file}")
    # Get STL analysis results
    stl_analysis = analyze_stl_bounding_box(stl_file)
    characteristic_length = stl_analysis["scaled_characteristic_length"]
    stl_center = stl_analysis["center"]  # Get center from analysis
    
    # Apply validation and corrections
    stl_analysis = validate_stl_dimensions(stl_analysis)
    
    # Use actual STL dimensions instead of hardcoded values
    stl_dims = stl_analysis["dimensions"]
    
    # Calculate domain size based on actual STL dimensions
    domain_length = characteristic_length * domain_size_multiplier
    
    # IMPROVED: Ensure minimum domain size for small geometries
    # This prevents issues with very small STL files after unit conversion
    min_domain_size = 1.0  # Minimum 1m domain for proper mesh resolution
    
    if characteristic_length < 0.05:  # If geometry is smaller than 5cm
        # Scale up the domain size multiplier to ensure adequate mesh resolution
        # This gives more cells around small objects
        effective_multiplier = domain_size_multiplier * (0.05 / characteristic_length)
        domain_length = max(min_domain_size, characteristic_length * effective_multiplier)
        logger.info(f"Small geometry detected ({characteristic_length:.3f}m), adjusting domain multiplier to {effective_multiplier:.1f}")
    else:
        domain_length = max(min_domain_size, domain_length)
    
    # Make domain proportional to STL dimensions but ensure minimum sizes
    # Use STL aspect ratios but with reasonable bounds
    stl_x, stl_y, stl_z = stl_dims["x"], stl_dims["y"], stl_dims["z"]
    max_stl_dim = max(stl_x, stl_y, stl_z)
    
    # Scale domain dimensions proportionally but ensure minimum coverage
    domain_height = max(domain_length * 0.5, (stl_y / max_stl_dim) * domain_length * 0.8)
    domain_width = max(domain_length * 0.5, (stl_z / max_stl_dim) * domain_length * 0.8)
    
    # Log the analysis results
    if stl_analysis.get("validation", {}).get("warnings"):
        for warning in stl_analysis["validation"]["warnings"]:
            logger.warning(f"STL Analysis: {warning}")
    
    logger.info(f"STL Mesh Config - Characteristic length: {characteristic_length:.3f}m")
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
        
        # Background mesh configuration
        "background_mesh": {
            "type": "blockMesh",
            "domain_length": domain_length,
            "domain_height": domain_height,
            "domain_width": domain_width,
            # Increase resolution for small geometries
            "n_cells_x": int(base_resolution * 2.0) if characteristic_length < 0.05 else int(base_resolution * 1.5),
            "n_cells_y": int(base_resolution * 1.2) if characteristic_length < 0.05 else int(base_resolution * 0.9),
            "n_cells_z": int(base_resolution * 1.2) if characteristic_length < 0.05 else int(base_resolution * 0.9),
            # Create a box domain centered around the STL geometry
            # Place inlet upstream and outlet downstream of the STL
            "vertices": create_adaptive_domain_vertices(
                domain_length, domain_height, domain_width, 
                stl_center, characteristic_length, domain_size_multiplier
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
        
        # SnappyHexMesh settings - improved for robustness
        "snappy_settings": {
            "castellated_mesh": True,
            "snap": True,
            "add_layers": False,  # Start without layers for robustness, can be enabled later
            "refinement_levels": {
                # Adaptive refinement based on geometry size
                "min": 1 if characteristic_length < 0.05 else 0,  # More refinement for small objects
                "max": 3 if characteristic_length < 0.05 else 2,  # Higher max refinement for small objects
                "surface_level": 2 if characteristic_length < 0.05 else 1
            },
            "refinement_regions": {
                "global": {
                    "min": [0, 0, 0],
                    "max": [domain_length, domain_height, domain_width],
                    "level": 0  # Start conservative
                }
            },
            # Adaptive locationInMesh based on STL position and domain
            "location_in_mesh": calculate_adaptive_location_in_mesh(
                create_adaptive_domain_vertices(
                    domain_length, domain_height, domain_width, 
                    stl_center, characteristic_length, domain_size_multiplier
                ), 
                stl_center
            ),
            "layers": {
                "n_layers": 3,
                "expansion_ratio": 1.3,
                "final_layer_thickness": 0.7,
                "min_thickness": 0.1
            },
            # Improved mesh quality controls for STL files
            "mesh_quality": {
                "maxNonOrtho": 75,  # More relaxed for complex geometry
                "maxBoundarySkewness": 25,  # More relaxed
                "maxInternalSkewness": 6,   # More relaxed
                "maxConcave": 85,           # More relaxed
                "minVol": 1e-15,           # More tolerant
                "minTetQuality": -1e30,    # Very relaxed for initial mesh
                "minArea": -1,
                "minTwist": 0.01,          # More relaxed
                "minDeterminant": 0.0001,  # More relaxed
                "minFaceWeight": 0.01,     # More relaxed
                "minVolRatio": 0.005,      # More relaxed
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
        
        # Resolution settings
        "resolution": {
            "background": base_resolution,
            "surface": base_resolution * 1.5,  # Less aggressive refinement
            "refinement": base_resolution * 2   # Less aggressive refinement
        },
        
        # Estimated cell count (will be refined during meshing)
        "total_cells": int(base_resolution * base_resolution * base_resolution * 0.3),  # More conservative estimate
        
        # Quality metrics
        "quality_metrics": {
            "aspect_ratio": 3.0,  # More relaxed for STL files
            "quality_score": 0.75  # More realistic for complex geometries
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
"""Mesh Generator Agent - Creates OpenFOAM mesh configurations."""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger

from .state import CFDState, CFDStep, GeometryType


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
    
    # Get resolution multiplier
    resolution_multiplier = get_resolution_multiplier(mesh_resolution)
    
    if geometry_type == GeometryType.CYLINDER:
        return generate_cylinder_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.AIRFOIL:
        return generate_airfoil_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.PIPE:
        return generate_pipe_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.CHANNEL:
        return generate_channel_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.SPHERE:
        return generate_sphere_mesh(dimensions, resolution_multiplier, parsed_params)
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


def generate_cylinder_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for cylinder geometry."""
    diameter = dimensions.get("diameter", 0.1)
    length = dimensions.get("length", 1.0)
    
    # Domain dimensions (should be large enough to avoid boundary effects)
    domain_width = max(diameter * 20, 2.0)
    domain_height = max(diameter * 20, 2.0)
    
    # Base mesh resolution
    base_resolution = int(40 * resolution_multiplier)
    
    # Mesh configuration
    mesh_config = {
        "type": "blockMesh",
        "geometry_type": "cylinder",
        "dimensions": {
            "cylinder_diameter": diameter,
            "cylinder_length": length,
            "domain_width": domain_width,
            "domain_height": domain_height
        },
        "resolution": {
            "circumferential": max(int(base_resolution * 0.8), 16),
            "radial": max(int(base_resolution * 0.5), 10),
            "axial": max(int(base_resolution * 0.6), 12)
        },
        "blocks": generate_cylinder_blocks(diameter, domain_width, domain_height, base_resolution),
        "total_cells": 0,  # Will be calculated
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch", 
            "walls": "wall",
            "cylinder": "wall",
            "sides": "symmetryPlane"
        }
    }
    
    # Calculate total cells
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
    return mesh_config


def generate_airfoil_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for airfoil geometry."""
    chord = dimensions.get("chord", 0.1)
    span = dimensions.get("span", 0.01)  # For 2D simulation
    
    # Domain dimensions
    domain_length = chord * 30
    domain_height = chord * 20
    
    # Base mesh resolution
    base_resolution = int(60 * resolution_multiplier)
    
    mesh_config = {
        "type": "blockMesh",
        "geometry_type": "airfoil",
        "dimensions": {
            "chord": chord,
            "span": span,
            "domain_length": domain_length,
            "domain_height": domain_height
        },
        "resolution": {
            "chordwise": max(int(base_resolution * 1.2), 48),
            "normal": max(int(base_resolution * 0.8), 32),
            "spanwise": max(int(base_resolution * 0.1), 4)
        },
        "blocks": generate_airfoil_blocks(chord, domain_length, domain_height, base_resolution),
        "total_cells": 0,
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch",
            "airfoil": "wall",
            "farfield": "patch",
            "sides": "empty"  # For 2D
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
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
            "sides": "symmetryPlane"
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
    return mesh_config


def generate_sphere_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mesh configuration for sphere geometry."""
    diameter = dimensions.get("diameter", 0.1)
    
    # Domain dimensions
    domain_size = diameter * 20
    
    # Base mesh resolution
    base_resolution = int(50 * resolution_multiplier)
    
    mesh_config = {
        "type": "blockMesh",
        "geometry_type": "sphere",
        "dimensions": {
            "diameter": diameter,
            "domain_size": domain_size
        },
        "resolution": {
            "circumferential": max(int(base_resolution * 0.8), 20),
            "radial": max(int(base_resolution * 0.6), 15),
            "meridional": max(int(base_resolution * 0.8), 20)
        },
        "blocks": generate_sphere_blocks(diameter, domain_size, base_resolution),
        "total_cells": 0,
        "boundary_patches": {
            "inlet": "patch",
            "outlet": "patch",
            "sphere": "wall",
            "farfield": "patch"
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
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


def generate_sphere_blocks(diameter: float, domain_size: float, resolution: int) -> Dict[str, Any]:
    """Generate block structure for sphere mesh."""
    return {
        "block_count": 6,  # Spherical coordinate blocks
        "grading": {
            "radial": 1.0,
            "circumferential": 1.0,
            "meridional": 1.0
        },
        "boundary_layer": {
            "enabled": True,
            "first_layer_thickness": diameter * 1e-5,
            "expansion_ratio": 1.2,
            "layers": 12
        }
    }


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
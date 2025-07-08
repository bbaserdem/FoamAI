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
    flow_context = geometry_info.get("flow_context", {})
    
    # Get resolution multiplier
    resolution_multiplier = get_resolution_multiplier(mesh_resolution)
    
    # Check if this is external or internal flow
    is_external_flow = flow_context.get("is_external_flow", False)
    
    if geometry_type == GeometryType.CYLINDER:
        return generate_cylinder_mesh(dimensions, mesh_resolution, is_external_flow, flow_context)
    elif geometry_type == GeometryType.AIRFOIL:
        return generate_airfoil_mesh(dimensions, resolution_multiplier, parsed_params, is_external_flow)
    elif geometry_type == GeometryType.PIPE:
        return generate_pipe_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.CHANNEL:
        return generate_channel_mesh(dimensions, resolution_multiplier, parsed_params)
    elif geometry_type == GeometryType.SPHERE:
        return generate_sphere_mesh(dimensions, resolution_multiplier, parsed_params, is_external_flow)
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
            "type": "snappyHexMesh",  # Use snappyHexMesh instead of blockMesh
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


def generate_airfoil_mesh(dimensions: Dict[str, float], resolution_multiplier: float, params: Dict[str, Any], is_external_flow: bool = True) -> Dict[str, Any]:
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
            "sides": "empty"
        }
    }
    
    mesh_config["total_cells"] = calculate_total_cells(mesh_config)
    
    return mesh_config


def generate_sphere_mesh(dimensions: Dict[str, float], resolution_multiplier: float, 
                        params: Dict[str, Any], is_external_flow: bool = True) -> Dict[str, Any]:
    """Generate mesh configuration for sphere geometry."""
    diameter = dimensions.get("diameter", 0.1)
    
    if is_external_flow:
        # External flow around sphere - 3D O-grid
        domain_size = diameter * 20
        
        # Base mesh resolution
        base_resolution = int(50 * resolution_multiplier)
        
        mesh_config = {
            "type": "blockMesh",
            "mesh_topology": "o-grid-3d",
            "geometry_type": "sphere",
            "is_external_flow": True,
            "dimensions": {
                "sphere_diameter": diameter,
                "domain_size": domain_size,
                "sphere_center": [domain_size/2, domain_size/2, domain_size/2]
            },
            "resolution": {
                "circumferential": max(int(base_resolution * 1.0), 24),
                "radial": max(int(base_resolution * 0.8), 20),
                "meridional": max(int(base_resolution * 1.0), 24)
            },
            "boundary_layer": {
                "enabled": True,
                "first_layer_height": diameter * 1e-5,
                "layers": 15,
                "expansion_ratio": 1.2
            },
            "blocks": generate_sphere_ogrid_blocks(diameter, domain_size, base_resolution),
            "total_cells": 0,
            "boundary_patches": {
                "inlet": "patch",
                "outlet": "patch",
                "sphere": "wall",
                "farfield": "patch"
            }
        }
    else:
        # Internal flow (sphere in duct) - less common
        mesh_config = generate_sphere_internal_mesh(dimensions, resolution_multiplier, params)
    
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
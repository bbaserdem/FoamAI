"""Mesh Convergence Agent - Orchestrates mesh convergence studies."""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import numpy as np
import json
import shutil
from loguru import logger

from .state import CFDState, CFDStep, GeometryType


def mesh_convergence_agent(state: CFDState) -> CFDState:
    """Orchestrate mesh convergence study."""
    try:
        logger.info("Mesh Convergence: Starting mesh convergence study")
        
        # Generate mesh levels
        mesh_levels = generate_mesh_convergence_levels(
            state["mesh_config"], 
            state["geometry_info"],
            state["mesh_convergence_levels"]
        )
        
        # Run simulations for each mesh level
        convergence_results = []
        for level_idx, mesh_level in enumerate(mesh_levels):
            logger.info(f"Mesh Convergence: Running simulation for mesh level {level_idx + 1}/{len(mesh_levels)}")
            
            # Create case directory for this mesh level
            level_case_dir = create_mesh_level_case_directory(
                state["case_directory"], 
                level_idx, 
                mesh_level
            )
            
            # Run simulation for this mesh level
            level_results = run_mesh_level_simulation(
                state, 
                mesh_level, 
                level_case_dir,
                level_idx
            )
            
            if level_results:
                convergence_results.append(level_results)
            else:
                logger.warning(f"Mesh Convergence: Failed to run simulation for mesh level {level_idx}")
        
        # Assess convergence
        if len(convergence_results) >= 2:
            convergence_assessment = assess_mesh_convergence(
                convergence_results,
                state["mesh_convergence_target_params"],
                state["mesh_convergence_threshold"]
            )
            
            # Generate convergence report
            convergence_report = generate_convergence_report(
                convergence_results,
                convergence_assessment,
                mesh_levels
            )
            
            # Recommend optimal mesh level
            recommended_level = recommend_optimal_mesh_level(
                convergence_results,
                convergence_assessment
            )
            
            logger.info(f"Mesh Convergence: Recommended mesh level {recommended_level}")
            
            # Copy the recommended mesh level results to main case directory for visualization
            try:
                if recommended_level < len(convergence_results):
                    # Get the recommended case directory from convergence results
                    recommended_result = convergence_results[recommended_level]
                    recommended_case_dir = Path(recommended_result["case_directory"])
                    main_case_dir = Path(state["case_directory"])
                    
                    logger.info(f"Copying mesh from {recommended_case_dir} to {main_case_dir}")
                    
                    # Copy mesh files (polyMesh directory specifically)
                    poly_mesh_src = recommended_case_dir / "constant" / "polyMesh"
                    poly_mesh_dst = main_case_dir / "constant" / "polyMesh"
                    
                    if poly_mesh_src.exists():
                        if poly_mesh_dst.exists():
                            shutil.rmtree(poly_mesh_dst)
                        shutil.copytree(poly_mesh_src, poly_mesh_dst)
                        logger.info(f"Copied polyMesh directory to main case")
                    else:
                        logger.warning(f"polyMesh directory not found in {poly_mesh_src}")
                    
                    # Copy the latest time directory with results
                    time_dirs = [d for d in recommended_case_dir.iterdir() 
                                if d.is_dir() and d.name.replace('.', '').replace('-', '').isdigit()]
                    if time_dirs:
                        latest_time_dir = max(time_dirs, key=lambda x: float(x.name))
                        target_time_dir = main_case_dir / latest_time_dir.name
                        if target_time_dir.exists():
                            shutil.rmtree(target_time_dir)
                        shutil.copytree(latest_time_dir, target_time_dir)
                        logger.info(f"Copied time directory {latest_time_dir.name} to main case")
                    else:
                        logger.warning("No time directories found in recommended case")
                    
                    # Update state to reflect the recommended mesh
                    if recommended_level < len(mesh_levels):
                        recommended_mesh = mesh_levels[recommended_level]
                        if "mesh_info" in state:
                            state["mesh_info"]["total_cells"] = recommended_mesh.get("estimated_cells", 0)
                            state["mesh_info"]["quality_score"] = recommended_mesh.get("quality_score", 0.0)
                        
            except Exception as e:
                logger.error(f"Failed to copy recommended mesh to main case: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            state = {
                **state,
                "mesh_convergence_results": {
                    "levels": convergence_results,
                    "assessment": convergence_assessment,
                    "mesh_configs": mesh_levels
                },
                "mesh_convergence_report": convergence_report,
                "recommended_mesh_level": recommended_level,
                "current_step": CFDStep.MESH_CONVERGENCE
            }
        else:
            logger.error("Mesh Convergence: Insufficient successful simulations for convergence assessment")
            state = {
                **state,
                "errors": state["errors"] + ["Insufficient mesh levels completed for convergence assessment"],
                "current_step": CFDStep.ERROR
            }
        
        return state
        
    except Exception as e:
        logger.error(f"Mesh Convergence error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Mesh convergence study failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def generate_mesh_convergence_levels(
    base_mesh_config: Dict[str, Any], 
    geometry_info: Dict[str, Any],
    num_levels: int = 4
) -> List[Dict[str, Any]]:
    """Generate systematic mesh refinement levels."""
    levels = []
    refinement_factor = 2.0  # Each level doubles linear resolution
    
    logger.info(f"Generating {num_levels} mesh convergence levels")
    
    for i in range(num_levels):
        level_config = base_mesh_config.copy()
        scale_factor = refinement_factor ** i
        
        # Calculate refinement parameters using more realistic scaling
        base_cells_per_diameter = level_config.get("cells_per_diameter", 20)
        base_refinement = level_config.get("refinement_level", 2)
        
        if i == 0:
            # Coarse mesh - reduce resolution
            level_config["cells_per_diameter"] = max(8, int(base_cells_per_diameter * 0.5))
            level_config["refinement_level"] = max(0, base_refinement - 1)
        else:
            # Progressive refinement with more reasonable scaling
            refinement_multiplier = 1.4 ** (i - 1)  # More gradual increase
            level_config["cells_per_diameter"] = int(base_cells_per_diameter * refinement_multiplier)
            level_config["refinement_level"] = base_refinement + (i - 1)
        
        # Estimate total cells
        estimated_cells = estimate_total_cells(level_config, geometry_info)
        
        levels.append({
            "level": i,
            "name": f"Level_{i}",
            "scale_factor": scale_factor,
            "estimated_cells": estimated_cells,
            "config": level_config,
            "description": get_mesh_level_description(i, estimated_cells)
        })
        
        logger.info(f"Level {i}: {estimated_cells:,} cells ({levels[-1]['description']})")
    
    return levels


def estimate_total_cells(mesh_config: Dict[str, Any], geometry_info: Dict[str, Any]) -> int:
    """Estimate total number of cells for a mesh configuration."""
    # Base estimation on cells per diameter and domain size
    cells_per_diameter = mesh_config.get("cells_per_diameter", 20)
    
    # Get domain dimensions
    domain_width = geometry_info.get("domain_width", 2.0)
    domain_height = geometry_info.get("domain_height", 2.0) 
    domain_depth = geometry_info.get("domain_depth", 0.1)
    
    # Get characteristic length
    char_length = geometry_info.get("characteristic_length", 0.1)
    
    # Estimate cells in each direction
    cells_x = int(domain_width / char_length * cells_per_diameter)
    cells_y = int(domain_height / char_length * cells_per_diameter)
    cells_z = max(1, int(domain_depth / char_length * cells_per_diameter))
    
    # Account for refinement levels
    refinement_factor = 2 ** mesh_config.get("refinement_level", 0)
    
    total_cells = int(cells_x * cells_y * cells_z * refinement_factor)
    
    return total_cells


def get_mesh_level_description(level: int, estimated_cells: int) -> str:
    """Get description for mesh level."""
    if level == 0:
        return "Coarse"
    elif level == 1:
        return "Medium"
    elif level == 2:
        return "Fine"
    elif level == 3:
        return "Very Fine"
    else:
        return f"Ultra Fine L{level}"


def create_mesh_level_case_directory(
    base_case_directory: str, 
    level_idx: int, 
    mesh_level: Dict[str, Any]
) -> Path:
    """Create case directory for specific mesh level."""
    if not base_case_directory or not Path(base_case_directory).exists():
        raise ValueError(f"Base case directory does not exist: {base_case_directory}")
    
    base_path = Path(base_case_directory)
    level_case_dir = base_path.parent / f"{base_path.name}_mesh_level_{level_idx}"
    
    # Copy base case
    if level_case_dir.exists():
        shutil.rmtree(level_case_dir)
    
    shutil.copytree(base_case_directory, level_case_dir)
    
    logger.info(f"Created mesh level case directory: {level_case_dir}")
    return level_case_dir


def run_mesh_level_simulation(
    state: CFDState,
    mesh_level: Dict[str, Any],
    case_directory: Path,
    level_idx: int
) -> Optional[Dict[str, Any]]:
    """Run simulation for specific mesh level."""
    try:
        # Create modified state for this mesh level
        level_state = state.copy()
        level_state["mesh_config"] = mesh_level["config"]
        level_state["case_directory"] = str(case_directory)
        
        # Regenerate mesh with new configuration
        from .mesh_generator import mesh_generator_agent
        level_state = mesh_generator_agent(level_state)
        
        if level_state["current_step"] == CFDStep.ERROR:
            logger.error(f"Mesh generation failed for level {level_idx}")
            return None
        
        # Run simulation
        from .simulation_executor import simulation_executor_agent
        level_state = simulation_executor_agent(level_state)
        
        if level_state["current_step"] == CFDStep.ERROR:
            logger.error(f"Simulation failed for level {level_idx}")
            return None
        
        # Extract results
        simulation_results = level_state.get("simulation_results", {})
        
        # Extract key parameters for convergence assessment
        convergence_params = extract_convergence_parameters(
            case_directory, 
            level_state["geometry_info"],
            level_state["mesh_convergence_target_params"]
        )
        
        return {
            "level": level_idx,
            "mesh_level": mesh_level,
            "case_directory": str(case_directory),
            "simulation_results": simulation_results,
            "convergence_parameters": convergence_params,
            "mesh_quality": level_state.get("mesh_quality", {}),
            "convergence_metrics": level_state.get("convergence_metrics", {})
        }
        
    except Exception as e:
        logger.error(f"Failed to run simulation for mesh level {level_idx}: {str(e)}")
        return None


def extract_convergence_parameters(
    case_directory: Path,
    geometry_info: Dict[str, Any],
    target_params: List[str]
) -> Dict[str, float]:
    """Extract key parameters for convergence assessment."""
    parameters = {}
    
    try:
        # Get geometry type
        geometry_type = geometry_info.get("type", "custom")
        
        # Universal parameters
        parameters["max_velocity"] = extract_max_velocity(case_directory)
        parameters["pressure_drop"] = extract_pressure_drop(case_directory)
        
        # Geometry-specific parameters
        if geometry_type in ["cylinder", "sphere", "cube", "custom"]:
            drag_coeff = extract_drag_coefficient(case_directory, geometry_info)
            if drag_coeff is not None:
                parameters["drag_coefficient"] = drag_coeff
        
        if geometry_type == "cylinder":
            strouhal = extract_strouhal_number(case_directory)
            if strouhal is not None:
                parameters["strouhal_number"] = strouhal
        
        if geometry_type == "pipe":
            friction_factor = extract_friction_factor(case_directory)
            if friction_factor is not None:
                parameters["friction_factor"] = friction_factor
        
        # Filter to only requested parameters if specified
        if target_params:
            filtered_params = {k: v for k, v in parameters.items() if k in target_params}
            parameters = filtered_params
        
        logger.info(f"Extracted convergence parameters: {list(parameters.keys())}")
        
    except Exception as e:
        logger.error(f"Failed to extract convergence parameters: {str(e)}")
    
    return parameters


def extract_max_velocity(case_directory: Path) -> float:
    """Extract maximum velocity from simulation results."""
    try:
        # Look for velocity data in latest time directory
        time_dirs = [d for d in case_directory.iterdir() if d.is_dir() and d.name.replace('.', '').isdigit()]
        if not time_dirs:
            return 0.0
        
        latest_time = max(time_dirs, key=lambda x: float(x.name))
        u_file = latest_time / "U"
        
        if u_file.exists():
            with open(u_file, 'r') as f:
                content = f.read()
                # Simple extraction - look for internal field max values
                # This is a simplified approach - in practice might use foamCalc or similar
                import re
                numbers = re.findall(r'[-+]?\d*\.?\d+', content)
                if numbers:
                    velocities = [abs(float(n)) for n in numbers[-100:]]  # Last 100 numbers
                    return max(velocities) if velocities else 0.0
        
        return 0.0
        
    except Exception as e:
        logger.error(f"Failed to extract max velocity: {str(e)}")
        return 0.0


def extract_pressure_drop(case_directory: Path) -> float:
    """Extract pressure drop from simulation results."""
    try:
        # Similar approach to max velocity - simplified extraction
        time_dirs = [d for d in case_directory.iterdir() if d.is_dir() and d.name.replace('.', '').isdigit()]
        if not time_dirs:
            return 0.0
        
        latest_time = max(time_dirs, key=lambda x: float(x.name))
        p_file = latest_time / "p"
        
        if p_file.exists():
            with open(p_file, 'r') as f:
                content = f.read()
                import re
                numbers = re.findall(r'[-+]?\d*\.?\d+', content)
                if numbers:
                    pressures = [float(n) for n in numbers[-100:]]
                    return max(pressures) - min(pressures) if pressures else 0.0
        
        return 0.0
        
    except Exception as e:
        logger.error(f"Failed to extract pressure drop: {str(e)}")
        return 0.0


def extract_drag_coefficient(case_directory: Path, geometry_info: Dict[str, Any]) -> Optional[float]:
    """Extract drag coefficient from forces."""
    try:
        # Look for forces file in postProcessing
        forces_dir = case_directory / "postProcessing" / "forces"
        if not forces_dir.exists():
            return None
        
        # Find latest forces file
        force_files = list(forces_dir.glob("*/forces.dat"))
        if not force_files:
            return None
        
        latest_forces = max(force_files, key=lambda x: float(x.parent.name))
        
        with open(latest_forces, 'r') as f:
            lines = f.readlines()
            if len(lines) > 1:
                # Last line contains final forces
                last_line = lines[-1].strip()
                parts = last_line.split()
                if len(parts) >= 4:
                    # Assuming format: time fx fy fz
                    drag_force = float(parts[1])  # x-component
                    
                    # Calculate drag coefficient
                    velocity = geometry_info.get("velocity", 10.0)
                    density = geometry_info.get("density", 1.0)
                    area = geometry_info.get("reference_area", 1.0)
                    
                    if velocity > 0 and area > 0:
                        q = 0.5 * density * velocity**2
                        cd = drag_force / (q * area)
                        return cd
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract drag coefficient: {str(e)}")
        return None


def extract_strouhal_number(case_directory: Path) -> Optional[float]:
    """Extract Strouhal number from unsteady simulation."""
    # Placeholder - would need frequency analysis of drag/lift forces
    # This is a simplified implementation
    return None


def extract_friction_factor(case_directory: Path) -> Optional[float]:
    """Extract friction factor for pipe flows."""
    # Placeholder - would calculate from pressure drop and flow parameters
    return None


def assess_mesh_convergence(
    convergence_results: List[Dict[str, Any]],
    target_params: List[str],
    threshold: float
) -> Dict[str, Any]:
    """Assess convergence using Richardson extrapolation."""
    assessment = {}
    
    if len(convergence_results) < 2:
        return assessment
    
    # Get all available parameters if none specified
    if not target_params:
        all_params = set()
        for result in convergence_results:
            all_params.update(result.get("convergence_parameters", {}).keys())
        target_params = list(all_params)
    
    logger.info(f"Assessing convergence for parameters: {target_params}")
    
    for param in target_params:
        param_values = []
        mesh_sizes = []
        
        # Extract parameter values and corresponding mesh sizes
        for result in convergence_results:
            param_value = result.get("convergence_parameters", {}).get(param)
            if param_value is not None:
                param_values.append(param_value)
                mesh_sizes.append(result["mesh_level"]["estimated_cells"])
        
        if len(param_values) < 2:
            continue
        
        # Calculate relative changes between levels
        relative_changes = []
        for i in range(1, len(param_values)):
            if param_values[i-1] != 0:
                rel_change = abs(param_values[i] - param_values[i-1]) / abs(param_values[i-1]) * 100
                relative_changes.append(rel_change)
        
        # Check convergence
        is_converged = len(relative_changes) > 0 and relative_changes[-1] < threshold
        
        # Calculate Grid Convergence Index (GCI)
        gci = calculate_gci(param_values, mesh_sizes)
        
        # Richardson extrapolation
        extrapolated_value = calculate_richardson_extrapolation(param_values, mesh_sizes)
        
        assessment[param] = {
            "values": param_values,
            "mesh_sizes": mesh_sizes,
            "relative_changes": relative_changes,
            "is_converged": is_converged,
            "gci": gci,
            "extrapolated_value": extrapolated_value,
            "uncertainty": gci.get("uncertainty", 0.0) if isinstance(gci, dict) else 0.0
        }
    
    return assessment


def calculate_gci(values: List[float], mesh_sizes: List[int]) -> Dict[str, float]:
    """Calculate Grid Convergence Index."""
    if len(values) < 3:
        return {"gci": 0.0, "uncertainty": 0.0}
    
    try:
        # Use last three values for GCI calculation
        f1, f2, f3 = values[-3:]  # Fine, medium, coarse
        h1, h2, h3 = [1.0/np.power(size, 1/3) for size in mesh_sizes[-3:]]  # Grid spacing
        
        # Calculate refinement ratios
        r21 = h2 / h1
        r32 = h3 / h2
        
        # Calculate apparent order of convergence
        epsilon32 = f3 - f2
        epsilon21 = f2 - f1
        
        # Check for zero differences or very small values
        if abs(epsilon32) < 1e-10 or abs(epsilon21) < 1e-10:
            return {"gci": 0.1, "uncertainty": 0.1}  # Very small uncertainty for converged solution
        
        # Check for oscillatory convergence
        if (epsilon32 * epsilon21) < 0:
            # Oscillatory convergence - use absolute values
            epsilon32 = abs(epsilon32)
            epsilon21 = abs(epsilon21)
        
        # Calculate ratio for order of convergence
        ratio = epsilon32 / epsilon21
        if abs(ratio) < 1e-10:
            ratio = 1e-10  # Prevent log(0)
        
        log_ratio = np.log(abs(ratio))
        log_r = np.log(r32 / r21)
        
        if abs(log_r) < 1e-10:
            # If refinement ratios are too similar, assume second order
            p = 2.0
        else:
            p = abs(log_ratio / log_r)
            # Bound the order of convergence to reasonable values
            p = min(max(p, 0.5), 5.0)
        
        # Safety factor
        Fs = 1.25 if len(values) == 3 else 1.15
        
        # GCI calculation
        denominator = np.power(r21, p) - 1
        if abs(denominator) < 1e-10:
            return {"gci": 0.1, "uncertainty": 0.1}
        
        gci21 = Fs * abs(epsilon21) / abs(denominator) / abs(f1) * 100
        
        # Bound GCI to reasonable values
        gci21 = min(gci21, 50.0)  # Cap at 50%
        
        return {
            "gci": gci21,
            "uncertainty": gci21,
            "order_of_convergence": p,
            "safety_factor": Fs
        }
        
    except Exception as e:
        logger.error(f"GCI calculation failed: {str(e)}")
        return {"gci": 0.0, "uncertainty": 0.0}


def calculate_richardson_extrapolation(values: List[float], mesh_sizes: List[int]) -> Optional[float]:
    """Calculate Richardson extrapolated value."""
    if len(values) < 2:
        return None
    
    try:
        # Use last two values
        f1, f2 = values[-2:]
        h1, h2 = [1.0/np.power(size, 1/3) for size in mesh_sizes[-2:]]
        
        # Assume second-order convergence
        p = 2.0
        r = h2 / h1
        
        # Richardson extrapolation
        extrapolated = f1 + (f1 - f2) / (np.power(r, p) - 1)
        
        return extrapolated
        
    except Exception as e:
        logger.error(f"Richardson extrapolation failed: {str(e)}")
        return None


def recommend_optimal_mesh_level(
    convergence_results: List[Dict[str, Any]],
    convergence_assessment: Dict[str, Any]
) -> int:
    """Recommend optimal mesh level based on convergence assessment."""
    # Strategy: Find the coarsest mesh that still meets convergence criteria
    
    if not convergence_assessment:
        return len(convergence_results) - 1  # Default to finest mesh
    
    # Check each parameter's convergence
    converged_levels = []
    
    for param, assessment in convergence_assessment.items():
        if assessment["is_converged"]:
            # Find the coarsest level where convergence is achieved
            relative_changes = assessment["relative_changes"]
            for i, change in enumerate(relative_changes):
                if change < 1.0:  # 1% threshold
                    converged_levels.append(i + 1)  # +1 because changes start from level 1
                    break
    
    if converged_levels:
        # Return the finest level among those that are converged
        # This ensures all parameters are converged
        recommended_level = max(converged_levels)
        return min(recommended_level, len(convergence_results) - 1)
    
    # If no clear convergence, recommend second-finest mesh
    return max(0, len(convergence_results) - 2)


def generate_convergence_report(
    convergence_results: List[Dict[str, Any]],
    convergence_assessment: Dict[str, Any],
    mesh_levels: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate comprehensive convergence report."""
    report = {
        "summary": {
            "total_levels": len(convergence_results),
            "successful_levels": len([r for r in convergence_results if r is not None]),
            "parameters_assessed": len(convergence_assessment),
            "converged_parameters": len([a for a in convergence_assessment.values() if a["is_converged"]])
        },
        "mesh_levels": [],
        "convergence_table": {},
        "recommendations": []
    }
    
    # Add mesh level information
    for i, result in enumerate(convergence_results):
        if result:
            level_info = {
                "level": i,
                "description": mesh_levels[i]["description"],
                "estimated_cells": mesh_levels[i]["estimated_cells"],
                "actual_cells": result.get("mesh_quality", {}).get("total_cells", "N/A"),
                "convergence_parameters": result.get("convergence_parameters", {})
            }
            report["mesh_levels"].append(level_info)
    
    # Add convergence assessment
    report["convergence_table"] = convergence_assessment
    
    # Generate recommendations
    recommendations = []
    
    for param, assessment in convergence_assessment.items():
        if assessment["is_converged"]:
            recommendations.append(f"✅ {param}: CONVERGED ({assessment['relative_changes'][-1]:.1f}% change)")
        else:
            recommendations.append(f"❌ {param}: NOT CONVERGED ({assessment['relative_changes'][-1]:.1f}% change)")
    
    report["recommendations"] = recommendations
    
    return report 
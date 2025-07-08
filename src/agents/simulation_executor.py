"""Simulation Executor Agent - Runs OpenFOAM simulations and monitors progress."""

import subprocess
import os
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger

from .state import CFDState, CFDStep, GeometryType


def _get_docker_command(case_directory: Path, command: str, settings: "FoamAISettings") -> List[str]:
    """Helper to construct a docker command."""
    if not settings.docker_container_name:
        raise ValueError("Docker container name is not set.")
    
    # Get the relative path of the case directory from the project root
    project_root = Path.cwd()
    
    # Use docker_mount_path if available, otherwise assume project root is mounted at the same path
    docker_mount_path = settings.docker_mount_path or str(project_root)
    
    try:
        relative_case_dir = case_directory.relative_to(project_root)
        container_case_dir = Path(docker_mount_path) / relative_case_dir
    except ValueError:
        # If case_directory is not inside project_root, we can't determine relative path
        # This can happen if work_dir is outside the project.
        # In this case, we assume the case_directory is mapped directly.
        # This requires the user to mount the work_dir into the container.
        container_case_dir = Path(settings.docker_mount_path or "/") / case_directory.name

    # Get the openfoam bashrc path. If a specific source script is provided, use that.
    # Otherwise, fall back to the standard bashrc from the openfoam_path.
    openfoam_source_cmd = ""
    if settings.openfoam_source_script:
        openfoam_source_cmd = f"source {settings.openfoam_source_script} && "
    elif settings.openfoam_path:
        openfoam_source_cmd = f"source {settings.openfoam_path}/etc/bashrc && "

    docker_command_str = (
        f"cd '{container_case_dir}' && "
        f"{openfoam_source_cmd}"
        f"{command}"
    )

    return ["docker", "exec", settings.docker_container_name, "bash", "-c", docker_command_str]


def simulation_executor_agent(state: CFDState) -> CFDState:
    """
    Simulation Executor Agent.
    
    Executes OpenFOAM simulation pipeline including mesh generation,
    mesh checking, and solver execution with progress monitoring.
    """
    try:
        if state["verbose"]:
            logger.info("Simulation Executor: Starting simulation execution")
        
        case_directory = Path(state["case_directory"])
        
        # Execute simulation pipeline
        simulation_results = execute_simulation_pipeline(case_directory, state)
        
        # Check simulation success
        if not simulation_results["success"]:
            error_msg = f"Simulation failed: {simulation_results.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "simulation_results": simulation_results,
                "current_step": CFDStep.ERROR
            }
        
        # Parse convergence metrics
        convergence_metrics = parse_convergence_metrics(simulation_results)
        
        if state["verbose"]:
            logger.info(f"Simulation Executor: Simulation completed successfully")
            logger.info(f"Simulation Executor: Final residuals: {convergence_metrics.get('final_residuals', {})}")
        
        return {
            **state,
            "simulation_results": simulation_results,
            "convergence_metrics": convergence_metrics,
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Simulation Executor error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Simulation execution failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def execute_simulation_pipeline(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Execute the complete OpenFOAM simulation pipeline."""
    results = {
        "success": False,
        "steps": {},
        "total_time": 0,
        "log_files": {}
    }
    
    start_time = time.time()
    
    try:
        # Step 1: Generate mesh
        if state["verbose"]:
            logger.info("Running blockMesh...")
            mesh_cells = state.get("mesh_config", {}).get("total_cells", 0)
            if mesh_cells and mesh_cells > 100000:
                logger.warning(f"Large mesh with {mesh_cells} cells - mesh generation may take a moment")
        
        mesh_result = run_blockmesh(case_directory, state)
        results["steps"]["mesh_generation"] = mesh_result
        results["log_files"]["blockMesh"] = mesh_result.get("log_file")
        
        if not mesh_result["success"]:
            results["error"] = f"Mesh generation failed: {mesh_result['error']}"
            return results
        
        if state["verbose"]:
            mesh_info = mesh_result.get("mesh_info", {})
            logger.info(f"Mesh generated successfully: {mesh_info.get('total_cells', 'unknown')} cells")
        
        # Step 1b: Run snappyHexMesh if needed
        mesh_type = state.get("mesh_config", {}).get("type", "blockMesh")
        if mesh_type == "snappyHexMesh":
            if state["verbose"]:
                logger.info("Running snappyHexMesh to refine mesh around geometry...")
            
            snappy_result = run_snappyhexmesh(case_directory, state)
            results["steps"]["snappyHexMesh"] = snappy_result
            results["log_files"]["snappyHexMesh"] = snappy_result.get("log_file")
            
            if not snappy_result["success"]:
                results["error"] = f"snappyHexMesh failed: {snappy_result['error']}"
                return results
            
            if state["verbose"]:
                logger.info("snappyHexMesh completed successfully")
                
            # Copy the latest mesh to constant/polyMesh
            copy_latest_mesh(case_directory)
        
        # Step 1.5: Create cylinder geometry if needed
        toposet_dict = case_directory / "system" / "topoSetDict"
        createpatch_dict = case_directory / "system" / "createPatchDict"
        
        if toposet_dict.exists() and createpatch_dict.exists():
            if state["verbose"]:
                logger.info("Running topoSet to create cylinder geometry...")
            
            toposet_result = run_toposet(case_directory, state)
            results["steps"]["toposet"] = toposet_result
            results["log_files"]["topoSet"] = toposet_result.get("log_file")
            
            if not toposet_result["success"]:
                results["error"] = f"topoSet failed: {toposet_result['error']}"
                return results
            
            if state["verbose"]:
                logger.info("Running createPatch to create cylinder boundary...")
            
            createpatch_result = run_createpatch(case_directory, state)
            results["steps"]["createpatch"] = createpatch_result
            results["log_files"]["createPatch"] = createpatch_result.get("log_file")
            
            if not createpatch_result["success"]:
                results["error"] = f"createPatch failed: {createpatch_result['error']}"
                return results
        
        # Step 2: Check mesh quality
        if state["verbose"]:
            logger.info("Running checkMesh...")
        
        mesh_check_result = run_checkmesh(case_directory, state)
        results["steps"]["mesh_check"] = mesh_check_result
        results["log_files"]["checkMesh"] = mesh_check_result.get("log_file")
        
        if not mesh_check_result["success"]:
            results["error"] = f"Mesh check failed: {mesh_check_result['error']}"
            return results
        
        if state["verbose"]:
            mesh_quality = mesh_check_result.get("mesh_quality", {})
            if mesh_quality.get("mesh_ok", False):
                logger.info("Mesh quality check passed")
            else:
                logger.warning("Mesh quality issues detected - simulation may have convergence problems")
        
        # Step 3: Run solver
        solver = state["solver_settings"]["solver"]
        if state["verbose"]:
            logger.info(f"Running {solver}...")
            velocity = state.get("parsed_parameters", {}).get("velocity", 1.0)
            if velocity and velocity > 100:
                logger.info(f"Note: High velocity ({velocity} m/s) simulations require small time steps for stability")
                logger.info("The solver may appear to pause but is actually computing many small time steps")
        
        solver_result = run_solver(case_directory, solver, state)
        results["steps"]["solver"] = solver_result
        results["log_files"]["solver"] = solver_result.get("log_file")
        
        if not solver_result["success"]:
            results["error"] = f"Solver execution failed: {solver_result['error']}"
            return results
        
        if state["verbose"]:
            solver_info = solver_result.get("solver_info", {})
            exec_time = solver_info.get("execution_time", 0)
            if exec_time > 0:
                logger.info(f"Solver completed successfully in {exec_time:.1f} seconds")
            else:
                logger.info("Solver completed successfully")
        
        results["success"] = True
        results["total_time"] = time.time() - start_time
        
        if state["verbose"]:
            logger.info(f"Total simulation pipeline time: {results['total_time']:.1f} seconds")
        
    except Exception as e:
        results["error"] = str(e)
        results["total_time"] = time.time() - start_time
    
    return results


def run_blockmesh(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run blockMesh to generate the computational mesh."""
    log_file = case_directory / "log.blockMesh"
    
    try:
        # Get settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment for non-docker execution
        env = prepare_openfoam_env()
        
        # Determine command
        if settings.use_docker:
            cmd = _get_docker_command(case_directory, "blockMesh", settings)
        elif settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && blockMesh"]
        else:
            # Windows/Native path - run directly
            cmd = ["blockMesh"]
        
        with open(log_file, "w") as f:
            exec_params = {
                "stdout": f,
                "stderr": subprocess.STDOUT,
                "timeout": 300
            }

            if settings.use_docker or (settings.openfoam_path and settings.openfoam_path.startswith("/")):
                # Docker or WSL, no cwd or env
                result = subprocess.run(cmd, **exec_params)
            else:
                # For native, run in case directory with env
                result = subprocess.run(cmd, cwd=case_directory, env=env, **exec_params)
        
        # Parse blockMesh output
        mesh_info = parse_blockmesh_output(log_file)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "mesh_info": mesh_info,
            "error": None if result.returncode == 0 else f"blockMesh failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "mesh_info": {},
            "error": "blockMesh timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "mesh_info": {},
            "error": str(e)
        }


def run_checkmesh(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run checkMesh to validate mesh quality."""
    log_file = case_directory / "log.checkMesh"
    
    try:
        # Get settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment for non-docker execution
        env = prepare_openfoam_env()
        
        # Determine command
        if settings.use_docker:
            cmd = _get_docker_command(case_directory, "checkMesh", settings)
        elif settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && checkMesh"]
        else:
            # Windows/Native path - run directly
            cmd = ["checkMesh"]
        
        with open(log_file, "w") as f:
            exec_params = {
                "stdout": f,
                "stderr": subprocess.STDOUT,
                "timeout": 120
            }

            if settings.use_docker or (settings.openfoam_path and settings.openfoam_path.startswith("/")):
                # Docker or WSL, no cwd or env
                result = subprocess.run(cmd, **exec_params)
            else:
                # For native, run in case directory with env
                result = subprocess.run(cmd, cwd=case_directory, env=env, **exec_params)

        # Parse checkMesh output
        mesh_quality = parse_checkmesh_output(log_file)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "mesh_quality": mesh_quality,
            "error": None if result.returncode == 0 else f"checkMesh failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "mesh_quality": {},
            "error": "checkMesh timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "mesh_quality": {},
            "error": str(e)
        }


def run_solver(case_directory: Path, solver: str, state: CFDState) -> Dict[str, Any]:
    """Run the OpenFOAM solver."""
    log_file = case_directory / f"log.{solver}"
    
    # Calculate expected runtime and steps for all flows when verbose
    if state["verbose"]:
        # Get simulation parameters
        control_dict = state.get("solver_settings", {}).get("controlDict", {})
        parsed_params = state.get("parsed_parameters", {})
        geometry_info = state.get("geometry_info", {})
        
        # Extract key parameters
        velocity = parsed_params.get("velocity", 1.0)
        start_time_sim = control_dict.get("startTime", 0.0)
        end_time = control_dict.get("endTime", 10.0)
        delta_t = control_dict.get("deltaT", 0.001)
        write_interval = control_dict.get("writeInterval", 1.0)
        
        # Calculate total simulation time and steps
        total_sim_time = end_time - start_time_sim
        total_steps = int(total_sim_time / delta_t) if delta_t and delta_t > 0 else None
        write_steps = int(total_sim_time / write_interval) if write_interval and write_interval > 0 else None
        
        logger.info("=" * 60)
        logger.info("SIMULATION PARAMETERS:")
        logger.info(f"  Solver: {solver}")
        logger.info(f"  Start Time: {start_time_sim} s")
        logger.info(f"  End Time: {end_time} s")
        logger.info(f"  Time Step (deltaT): {delta_t} s")
        logger.info(f"  Total Simulation Time: {total_sim_time} s")
        logger.info(f"  Total Time Steps: {total_steps if total_steps else 'Unknown'}")
        logger.info(f"  Write Interval: {write_interval} s")
        logger.info(f"  Output Time Steps: {write_steps if write_steps else 'Unknown'}")
        
        # Additional info for transient simulations
        if "pimple" in solver.lower() or "ico" in solver.lower():
            logger.info(f"  Velocity: {velocity} m/s")
            
            # Estimate CFL number if possible
            if geometry_info and delta_t and delta_t > 0:
                characteristic_length = get_characteristic_length_from_geometry(geometry_info)
                mesh_cells = state.get("mesh_config", {}).get("total_cells", 10000)
                approx_cell_size = characteristic_length / (mesh_cells ** (1/3))
                cfl_estimate = velocity * delta_t / approx_cell_size
                logger.info(f"  Estimated CFL number: {cfl_estimate:.2f}")
                
                if cfl_estimate > 1.0:
                    logger.warning(f"  ⚠️  CFL > 1.0 - Simulation may be unstable!")
                    recommended_dt = 0.5 * approx_cell_size / velocity
                    logger.warning(f"  Recommended deltaT: {recommended_dt:.6f} s")
        
        # Estimate runtime
        if total_steps and total_steps > 1000:
            estimated_runtime_min = total_steps * 0.01 / 60
            logger.info(f"  Estimated Runtime: {estimated_runtime_min:.1f} - {estimated_runtime_min*3:.1f} minutes")
            if total_steps > 10000:
                logger.warning(f"  ⚠️  Large number of steps ({total_steps}) - this may take a while!")
        
        logger.info("=" * 60)
    
    # Special warning for very high velocity flows
    velocity = state.get("parsed_parameters", {}).get("velocity", 1.0)
    if velocity and velocity > 50:
        logger.warning(f"High velocity ({velocity} m/s) detected - simulation may take longer due to small time steps required for stability")
    
    try:
        # Get settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment for non-docker execution
        env = prepare_openfoam_env()
        
        # Determine command
        if settings.use_docker:
            cmd = _get_docker_command(case_directory, solver, settings)
        elif settings.openfoam_path and settings.openfoam_path.startswith("/"):
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && {solver}"]
        else:
            cmd = [solver]
        
        if state["verbose"]:
            logger.info(f"Starting {solver} solver...")
            logger.info(f"Log file: {log_file}")
        
        start_time_exec = time.time()
        
        with open(log_file, "w") as f:
            popen_params = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "universal_newlines": True,
                "bufsize": 1
            }

            if settings.use_docker or (settings.openfoam_path and settings.openfoam_path.startswith("/")):
                process = subprocess.Popen(cmd, **popen_params)
            else:
                process = subprocess.Popen(cmd, cwd=case_directory, env=env, **popen_params)

            # Monitor progress in verbose mode
            last_time_reported = 0
            time_step_count = 0
            
            control_dict = state.get("solver_settings", {}).get("controlDict", {})
            start_time_sim = control_dict.get("startTime", 0.0)
            end_time = control_dict.get("endTime", 10.0)
            total_sim_time = end_time - start_time_sim

            for line in process.stdout:
                f.write(line)
                f.flush()
                
                if state["verbose"]:
                    time_match = re.search(r"Time = ([\d.e-]+)", line)
                    if time_match:
                        current_time = float(time_match.group(1))
                        time_step_count += 1
                        if time.time() - last_time_reported > 10 or time_step_count % 100 == 0:
                            elapsed = time.time() - start_time_exec
                            
                            if total_sim_time > 0:
                                time_progress_pct = (current_time - start_time_sim) / total_sim_time * 100
                                time_progress_pct = min(time_progress_pct, 100.0)
                                
                                time_per_sim_second = elapsed / (current_time - start_time_sim) if current_time > start_time_sim else 0
                                remaining_sim_time = max(0, end_time - current_time)
                                eta_seconds = remaining_sim_time * time_per_sim_second if time_per_sim_second > 0 else 0
                                eta_minutes = eta_seconds / 60
                                
                                step_progress = f"Step {time_step_count}"
                                
                                logger.info(
                                    f"Solver progress: Sim Time = {current_time:.3f}/{end_time:.1f} s ({time_progress_pct:.1f}%), "
                                    f"{step_progress}, "
                                    f"Real Time: {elapsed:.1f} s, "
                                    f"ETA: {eta_minutes:.1f} min"
                                )
                            else:
                                logger.info(f"Solver progress: Time = {current_time:.3f} s, Step {time_step_count}, Elapsed: {elapsed:.1f} s")
                            last_time_reported = time.time()
                    
                    co_match = re.search(r"Courant Number mean: ([\d.e-]+) max: ([\d.e-]+)", line)
                    if co_match and time_step_count % 50 == 0:
                        co_max = float(co_match.group(2))
                        if co_max > 1.0:
                            logger.warning(f"High Courant number detected: max = {co_max:.3f} (should be < 1)")
                    
                    if "FOAM Warning" in line:
                        logger.warning(f"Solver warning: {line.strip()}")
                    if "time step continuity errors" in line and "sum local" in line:
                        error_match = re.search(r"sum local = ([\d.e-]+)", line)
                        if error_match:
                            error = float(error_match.group(1))
                            if error > 1e-5:
                                logger.warning(f"High continuity error: {error:.2e}")
            
            timeout = state.get("max_simulation_time", 3600)
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                return {
                    "success": False,
                    "return_code": -1,
                    "log_file": str(log_file),
                    "solver_info": {},
                    "error": f"{solver} timed out after {timeout} seconds"
                }
        
        if state["verbose"]:
            elapsed_time = time.time() - start_time_exec
            logger.info("=" * 60)
            logger.info(f"SIMULATION COMPLETED:")
            logger.info(f"  Total Runtime: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
            if time_step_count > 0:
                logger.info(f"  Total Time Steps Executed: {time_step_count}")
                time_per_step = elapsed_time / time_step_count
                logger.info(f"  Average Time per Step: {time_per_step:.3f} seconds")
            logger.info("=" * 60)
        
        # Parse solver output
        solver_info = parse_solver_output(log_file, solver)
        
        return {
            "success": return_code == 0,
            "return_code": return_code,
            "log_file": str(log_file),
            "solver_info": solver_info,
            "error": None if return_code == 0 else f"{solver} failed with code {return_code}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "solver_info": {},
            "error": str(e)
        }


def prepare_openfoam_env() -> Dict[str, str]:
    """Prepare OpenFOAM environment variables."""
    env = os.environ.copy()
    
    # Get configured OpenFOAM path
    import sys
    sys.path.append('src')
    from foamai.config import get_settings
    settings = get_settings()
    
    if settings.openfoam_path:
        # Add OpenFOAM environment setup
        env["FOAM_INSTALL_DIR"] = settings.openfoam_path
        env["WM_PROJECT_VERSION"] = settings.openfoam_version
        
        # Determine platform directory based on variant
        if settings.openfoam_variant == "Foundation":
            # Foundation version typically uses linux64GccDPOpt
            platform_dir = "linux64GccDPOpt"
        else:
            # ESI version uses linux64GccDPInt32Opt
            platform_dir = "linux64GccDPInt32Opt"
        
        # Add binary path
        bin_path = f"{settings.openfoam_path}/platforms/{platform_dir}/bin"
        if "PATH" in env:
            env["PATH"] = f"{bin_path}:{env['PATH']}"
        else:
            env["PATH"] = bin_path
    
    return env


def parse_blockmesh_output(log_file: Path) -> Dict[str, Any]:
    """Parse blockMesh log file for mesh information."""
    mesh_info = {
        "total_cells": 0,
        "total_points": 0,
        "total_faces": 0,
        "boundary_patches": {},
        "warnings": [],
        "errors": []
    }
    
    try:
        with open(log_file, "r") as f:
            content = f.read()
        
        # Extract mesh statistics
        cells_match = re.search(r"cells:\s*(\d+)", content)
        if cells_match:
            mesh_info["total_cells"] = int(cells_match.group(1))
        
        points_match = re.search(r"points:\s*(\d+)", content)
        if points_match:
            mesh_info["total_points"] = int(points_match.group(1))
        
        faces_match = re.search(r"faces:\s*(\d+)", content)
        if faces_match:
            mesh_info["total_faces"] = int(faces_match.group(1))
        
        # Extract warnings and errors
        warnings = re.findall(r"Warning.*", content)
        mesh_info["warnings"] = warnings[:10]
        
        errors = re.findall(r"Error.*", content)
        mesh_info["errors"] = errors[:10]
        
    except Exception as e:
        logger.warning(f"Could not parse blockMesh output: {e}")
    
    return mesh_info


def parse_checkmesh_output(log_file: Path) -> Dict[str, Any]:
    """Parse checkMesh log file for mesh quality metrics."""
    mesh_quality = {
        "mesh_ok": False,
        "non_orthogonality": {"max": 0, "average": 0},
        "skewness": {"max": 0, "average": 0},
        "aspect_ratio": {"max": 0, "average": 0},
        "warnings": [],
        "errors": []
    }
    
    try:
        with open(log_file, "r") as f:
            content = f.read()
        
        # Check overall mesh status
        if "Mesh OK" in content:
            mesh_quality["mesh_ok"] = True
        
        # Extract non-orthogonality
        non_orth_match = re.search(r"Max non-orthogonality = ([\d.]+)", content)
        if non_orth_match:
            mesh_quality["non_orthogonality"]["max"] = float(non_orth_match.group(1))
        
        # Extract skewness
        skewness_match = re.search(r"Max skewness = ([\d.]+)", content)
        if skewness_match:
            mesh_quality["skewness"]["max"] = float(skewness_match.group(1))
        
        # Extract warnings and errors
        warnings = re.findall(r"Warning.*", content)
        mesh_quality["warnings"] = warnings[:10]
        
        errors = re.findall(r"Error.*", content)
        mesh_quality["errors"] = errors[:10]
        
    except Exception as e:
        logger.warning(f"Could not parse checkMesh output: {e}")
    
    return mesh_quality


def parse_solver_output(log_file: Path, solver: str) -> Dict[str, Any]:
    """Parse solver log file for convergence and performance metrics."""
    solver_info = {
        "converged": False,
        "iterations": 0,
        "final_residuals": {},
        "execution_time": 0,
        "warnings": [],
        "errors": []
    }
    
    try:
        with open(log_file, "r") as f:
            content = f.read()
        
        # Extract final residuals (simplified parsing)
        residual_patterns = {
            "p": r"Solving for p.*Final residual = ([\d.e-]+)",
            "Ux": r"Solving for Ux.*Final residual = ([\d.e-]+)",
            "Uy": r"Solving for Uy.*Final residual = ([\d.e-]+)",
            "Uz": r"Solving for Uz.*Final residual = ([\d.e-]+)",
            "k": r"Solving for k.*Final residual = ([\d.e-]+)",
            "omega": r"Solving for omega.*Final residual = ([\d.e-]+)",
            "epsilon": r"Solving for epsilon.*Final residual = ([\d.e-]+)"
        }
        
        for field, pattern in residual_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                solver_info["final_residuals"][field] = float(matches[-1])
        
        # Check convergence
        if "SIMPLE solution converged" in content or "PIMPLE: converged" in content:
            solver_info["converged"] = True
        elif "FOAM exiting" not in content and solver_info["final_residuals"]:
            solver_info["converged"] = True
        elif "ExecutionTime" in content and solver_info["final_residuals"]:
            solver_info["converged"] = True
        
        # Extract execution time
        time_match = re.search(r"ExecutionTime = ([\d.]+) s", content)
        if time_match:
            solver_info["execution_time"] = float(time_match.group(1))
        
        # Extract iterations/time steps
        if "steady" in solver.lower():
            iteration_matches = re.findall(r"Time = (\d+)", content)
            if iteration_matches:
                solver_info["iterations"] = int(iteration_matches[-1])
        else:
            time_matches = re.findall(r"Time = ([\d.e-]+)", content)
            if time_matches:
                solver_info["final_time"] = float(time_matches[-1])
        
        # Extract warnings and errors
        warnings = re.findall(r"Warning.*", content)
        solver_info["warnings"] = warnings[:10]
        
        errors = re.findall(r"Error.*", content)
        solver_info["errors"] = errors[:10]
        
    except Exception as e:
        logger.warning(f"Could not parse {solver} output: {e}")
    
    return solver_info


def parse_convergence_metrics(simulation_results: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and analyze convergence metrics from simulation results."""
    convergence_metrics = {
        "converged": False,
        "final_residuals": {},
        "mesh_quality_ok": False,
        "execution_time": 0,
        "recommendations": []
    }
    
    # Get solver info
    solver_info = simulation_results.get("steps", {}).get("solver", {}).get("solver_info", {})
    convergence_metrics["converged"] = solver_info.get("converged", False)
    convergence_metrics["final_residuals"] = solver_info.get("final_residuals", {})
    convergence_metrics["execution_time"] = solver_info.get("execution_time", 0)
    
    # Get mesh quality
    mesh_quality = simulation_results.get("steps", {}).get("mesh_check", {}).get("mesh_quality", {})
    convergence_metrics["mesh_quality_ok"] = mesh_quality.get("mesh_ok", False)
    
    # Generate recommendations
    recommendations = []
    
    # Check residuals
    final_residuals = convergence_metrics["final_residuals"]
    for field, residual in final_residuals.items():
        if residual > 1e-3:
            recommendations.append(f"High final residual for {field}: {residual:.2e}")
    
    # Check mesh quality
    if not convergence_metrics["mesh_quality_ok"]:
        recommendations.append("Poor mesh quality detected - consider mesh refinement")
    
    # Check convergence
    if not convergence_metrics["converged"]:
        recommendations.append("Simulation did not converge - consider adjusting solver settings")
    
    convergence_metrics["recommendations"] = recommendations
    
    return convergence_metrics


def run_toposet(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run topoSet to create cylinder cell and face sets."""
    log_file = case_directory / "log.topoSet"
    
    try:
        # Get settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment for non-docker execution
        env = prepare_openfoam_env()
        
        # Determine command
        if settings.use_docker:
            cmd = _get_docker_command(case_directory, "topoSet", settings)
        elif settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && topoSet"]
        else:
            # Windows/Native path - run directly
            cmd = ["topoSet"]
        
        with open(log_file, "w") as f:
            exec_params = {
                "stdout": f,
                "stderr": subprocess.STDOUT,
                "timeout": 120
            }

            if settings.use_docker or (settings.openfoam_path and settings.openfoam_path.startswith("/")):
                # Docker or WSL, no cwd or env
                result = subprocess.run(cmd, **exec_params)
            else:
                # For native, run in case directory with env
                result = subprocess.run(cmd, cwd=case_directory, env=env, **exec_params)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "error": None if result.returncode == 0 else f"topoSet failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "error": "topoSet timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "error": str(e)
        }


def run_createpatch(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run createPatch to create cylinder boundary patch."""
    log_file = case_directory / "log.createPatch"
    
    try:
        # Get settings
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment for non-docker execution
        env = prepare_openfoam_env()
        
        # Determine command
        if settings.use_docker:
            cmd = _get_docker_command(case_directory, "createPatch -overwrite", settings)
        elif settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && createPatch -overwrite"]
        else:
            # Windows/Native path - run directly
            cmd = ["createPatch", "-overwrite"]
        
        with open(log_file, "w") as f:
            exec_params = {
                "stdout": f,
                "stderr": subprocess.STDOUT,
                "timeout": 120
            }

            if settings.use_docker or (settings.openfoam_path and settings.openfoam_path.startswith("/")):
                # Docker or WSL, no cwd or env
                result = subprocess.run(cmd, **exec_params)
            else:
                # For native, run in case directory with env
                result = subprocess.run(cmd, cwd=case_directory, env=env, **exec_params)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "error": None if result.returncode == 0 else f"createPatch failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "error": "createPatch timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "error": str(e)
        }


def get_characteristic_length_from_geometry(geometry_info: Dict[str, Any]) -> float:
    """Get characteristic length from geometry info."""
    dimensions = geometry_info.get("dimensions", {})
    geometry_type = geometry_info.get("type")
    
    # Try to get characteristic length based on geometry type
    if geometry_type == GeometryType.CYLINDER:
        return dimensions.get("diameter", dimensions.get("cylinder_diameter", 0.1))
    elif geometry_type == GeometryType.SPHERE:
        return dimensions.get("diameter", 0.1)
    elif geometry_type == GeometryType.AIRFOIL:
        return dimensions.get("chord", 0.1)
    elif geometry_type == GeometryType.PIPE:
        return dimensions.get("diameter", 0.05)
    elif geometry_type == GeometryType.CHANNEL:
        return dimensions.get("height", 0.02)
    else:
        # Try to find any dimension
        for key in ["diameter", "length", "width", "height", "chord"]:
            if key in dimensions and dimensions[key] > 0:
                return dimensions[key]
    
    # Default
    return 0.1


def run_snappyhexmesh(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run snappyHexMesh to refine mesh around geometry."""
    log_file = case_directory / "log.snappyHexMesh"
    
    try:
        # Get settings to check if we need WSL
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        # Prepare environment
        env = prepare_openfoam_env()
        
        # Determine if we need to use WSL
        if settings.openfoam_path and settings.openfoam_path.startswith("/"):
            # WSL path - run through WSL
            wsl_case_dir = str(case_directory).replace("\\", "/").replace("C:", "/mnt/c")
            cmd = ["wsl", "-e", "bash", "-c", 
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && snappyHexMesh -overwrite"]
        else:
            # Windows path - run directly
            cmd = ["snappyHexMesh", "-overwrite"]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=600  # 10 minute timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=600  # 10 minute timeout
                )
        
        # Parse snappyHexMesh output
        snappy_info = parse_snappyhexmesh_output(log_file)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "snappy_info": snappy_info,
            "error": None if result.returncode == 0 else f"snappyHexMesh failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "snappy_info": {},
            "error": "snappyHexMesh timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "snappy_info": {},
            "error": str(e)
        }


def copy_latest_mesh(case_directory: Path) -> None:
    """Copy the latest mesh from time directory to constant/polyMesh."""
    import shutil
    
    # Find the latest time directory with a polyMesh
    time_dirs = []
    for item in case_directory.iterdir():
        if item.is_dir() and item.name.replace(".", "").replace("-", "").isdigit():
            if (item / "polyMesh").exists():
                try:
                    time_value = float(item.name)
                    time_dirs.append((time_value, item))
                except ValueError:
                    pass
    
    if time_dirs:
        # Sort by time value and get the latest
        time_dirs.sort(key=lambda x: x[0])
        latest_time, latest_dir = time_dirs[-1]
        
        # Copy to constant/polyMesh
        source = latest_dir / "polyMesh"
        dest = case_directory / "constant" / "polyMesh"
        
        # Remove existing polyMesh if it exists
        if dest.exists():
            shutil.rmtree(dest)
        
        # Copy the new mesh
        shutil.copytree(source, dest)
        
        logger.info(f"Copied mesh from {latest_dir.name}/polyMesh to constant/polyMesh")


def parse_snappyhexmesh_output(log_file: Path) -> Dict[str, Any]:
    """Parse snappyHexMesh log file for mesh information."""
    info = {
        "cells_added": 0,
        "final_cells": 0,
        "layers_added": False,
        "snapping_iterations": 0
    }
    
    try:
        with open(log_file, "r") as f:
            content = f.read()
            
            # Look for final mesh statistics
            final_cells_match = re.search(r"Mesh\s+:\s+cells:(\d+)", content)
            if final_cells_match:
                info["final_cells"] = int(final_cells_match.group(1))
            
            # Check if layers were added
            if "Layer addition iteration" in content:
                info["layers_added"] = True
            
            # Count snapping iterations
            snap_matches = re.findall(r"Morph iteration (\d+)", content)
            if snap_matches:
                info["snapping_iterations"] = len(snap_matches)
    
    except Exception as e:
        logger.warning(f"Failed to parse snappyHexMesh output: {e}")
    
    return info 
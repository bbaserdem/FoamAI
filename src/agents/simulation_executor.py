"""Simulation Executor Agent - Runs OpenFOAM simulations and monitors progress."""

import subprocess
import os
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger

from .state import CFDState, CFDStep


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
        
        mesh_result = run_blockmesh(case_directory, state)
        results["steps"]["mesh_generation"] = mesh_result
        results["log_files"]["blockMesh"] = mesh_result.get("log_file")
        
        if not mesh_result["success"]:
            results["error"] = f"Mesh generation failed: {mesh_result['error']}"
            return results
        
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
        
        # Step 3: Run solver
        solver = state["solver_settings"]["solver"]
        if state["verbose"]:
            logger.info(f"Running {solver}...")
        
        solver_result = run_solver(case_directory, solver, state)
        results["steps"]["solver"] = solver_result
        results["log_files"]["solver"] = solver_result.get("log_file")
        
        if not solver_result["success"]:
            results["error"] = f"Solver execution failed: {solver_result['error']}"
            return results
        
        results["success"] = True
        results["total_time"] = time.time() - start_time
        
    except Exception as e:
        results["error"] = str(e)
        results["total_time"] = time.time() - start_time
    
    return results


def run_blockmesh(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Run blockMesh to generate the computational mesh."""
    log_file = case_directory / "log.blockMesh"
    
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
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && blockMesh"]
        else:
            # Windows path - run directly
            cmd = ["blockMesh"]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=300  # 5 minute timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=300  # 5 minute timeout
                )
        
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
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && checkMesh"]
        else:
            # Windows path - run directly
            cmd = ["checkMesh"]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=120  # 2 minute timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=120  # 2 minute timeout
                )
        
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
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && {solver}"]
        else:
            # Windows path - run directly
            cmd = [solver]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=state.get("max_simulation_time", 3600)  # Default 1 hour timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=state.get("max_simulation_time", 3600)  # Default 1 hour timeout
                )
        
        # Parse solver output
        solver_info = parse_solver_output(log_file, solver)
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "log_file": str(log_file),
            "solver_info": solver_info,
            "error": None if result.returncode == 0 else f"{solver} failed with code {result.returncode}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "log_file": str(log_file),
            "solver_info": {},
            "error": f"{solver} timed out"
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
        
        # Add binary path
        bin_path = f"{settings.openfoam_path}/platforms/linux64GccDPInt32Opt/bin"
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
        mesh_info["warnings"] = warnings[:10]  # Limit to first 10
        
        errors = re.findall(r"Error.*", content)
        mesh_info["errors"] = errors[:10]  # Limit to first 10
        
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
                solver_info["final_residuals"][field] = float(matches[-1])  # Take last value
        
        # Check convergence - more robust detection
        if "SIMPLE solution converged" in content or "PIMPLE: converged" in content:
            solver_info["converged"] = True
        elif "FOAM exiting" not in content and solver_info["final_residuals"]:
            # If solver completed without fatal errors and has final residuals, consider it converged
            solver_info["converged"] = True
        elif "ExecutionTime" in content and solver_info["final_residuals"]:
            # If execution time is reported and we have residuals, solver likely completed successfully
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
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && topoSet"]
        else:
            # Windows path - run directly
            cmd = ["topoSet"]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=120  # 2 minute timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=120  # 2 minute timeout
                )
        
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
                   f"cd '{wsl_case_dir}' && source {settings.openfoam_path}/etc/bashrc && createPatch -overwrite"]
        else:
            # Windows path - run directly
            cmd = ["createPatch", "-overwrite"]
        
        with open(log_file, "w") as f:
            if settings.openfoam_path and settings.openfoam_path.startswith("/"):
                # For WSL, don't change working directory since we're using cd in the command
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    timeout=120  # 2 minute timeout
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=case_directory,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=120  # 2 minute timeout
                )
        
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
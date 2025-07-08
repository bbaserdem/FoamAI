"""Solver Selector Agent - Chooses appropriate OpenFOAM solvers and configurations."""

from typing import Dict, Any, Optional
from loguru import logger

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType


def solver_selector_agent(state: CFDState) -> CFDState:
    """
    Solver Selector Agent.
    
    Chooses appropriate OpenFOAM solver and generates solver configuration
    files (fvSchemes, fvSolution, controlDict) based on flow parameters.
    """
    try:
        if state["verbose"]:
            logger.info("Solver Selector: Starting solver selection")
        
        parsed_params = state["parsed_parameters"]
        geometry_info = state["geometry_info"]
        boundary_conditions = state["boundary_conditions"]
        
        # Select appropriate solver
        solver_settings = select_solver(parsed_params, geometry_info)
        
        # Generate solver configuration files
        solver_config = generate_solver_config(solver_settings, parsed_params, geometry_info)
        
        # Validate solver configuration
        validation_result = validate_solver_config(solver_config, parsed_params)
        if not validation_result["valid"]:
            logger.warning(f"Solver validation issues: {validation_result['warnings']}")
            return {
                **state,
                "errors": state["errors"] + validation_result["errors"],
                "warnings": state["warnings"] + validation_result["warnings"]
            }
        
        if state["verbose"]:
            logger.info(f"Solver Selector: Selected {solver_settings['solver']} solver")
            logger.info(f"Solver Selector: Analysis type: {solver_settings['analysis_type']}")
        
        return {
            **state,
            "solver_settings": solver_config,
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Solver Selector error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Solver selection failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def select_solver(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Select appropriate OpenFOAM solver based on flow conditions."""
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    # Default to transient (UNSTEADY) analysis unless explicitly specified as steady
    analysis_type = parsed_params.get("analysis_type", AnalysisType.UNSTEADY)
    compressible = parsed_params.get("compressible", False)
    heat_transfer = parsed_params.get("heat_transfer", False)
    reynolds_number = parsed_params.get("reynolds_number", 0)
    mach_number = parsed_params.get("mach_number", 0)
    
    # For turbulent flows, consider using transient solver for better visualization
    # unless explicitly requested as steady
    if flow_type == FlowType.TURBULENT and geometry_info["type"] == GeometryType.CHANNEL:
        if analysis_type == AnalysisType.UNSTEADY:
            logger.info("Using transient solver for turbulent channel flow to capture unsteady features")
    
    # Determine solver name based on flow conditions
    if compressible:
        if flow_type == FlowType.TURBULENT:
            solver_name = "rhoPimpleFoam" if analysis_type == AnalysisType.UNSTEADY else "rhoSimpleFoam"
        else:
            solver_name = "rhoPimpleFoam" if analysis_type == AnalysisType.UNSTEADY else "rhoSimpleFoam"
    else:
        if flow_type == FlowType.TURBULENT:
            solver_name = "pimpleFoam" if analysis_type == AnalysisType.UNSTEADY else "simpleFoam"
        else:
            solver_name = "pimpleFoam" if analysis_type == AnalysisType.UNSTEADY else "simpleFoam"
    
    # Build complete solver settings dictionary
    solver_settings = {
        "solver": solver_name,
        "flow_type": flow_type,
        "analysis_type": analysis_type,
        "reynolds_number": reynolds_number,
        "mach_number": mach_number,
        "compressible": compressible
    }
    
    # Turbulence model selection
    if flow_type == FlowType.TURBULENT:
        if reynolds_number is not None and reynolds_number < 10000:
            solver_settings["turbulence_model"] = "kOmegaSST"
        elif reynolds_number is not None and reynolds_number >= 10000:
            solver_settings["turbulence_model"] = "kEpsilon"
        else:
            # Default for turbulent flow when Reynolds number is unknown
            solver_settings["turbulence_model"] = "kOmegaSST"
    else:
        solver_settings["turbulence_model"] = "laminar"
    
    return solver_settings


def generate_solver_config(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete solver configuration."""
    solver_config = {
        "solver": solver_settings["solver"],
        "controlDict": generate_control_dict(solver_settings["solver"], solver_settings["analysis_type"], parsed_params, geometry_info),
        "fvSchemes": generate_fv_schemes(solver_settings, parsed_params),
        "fvSolution": generate_fv_solution(solver_settings, parsed_params),
        "turbulenceProperties": generate_turbulence_properties(solver_settings, parsed_params),
        "transportProperties": generate_transport_properties(solver_settings, parsed_params),
        "analysis_type": solver_settings["analysis_type"],
        "flow_type": solver_settings["flow_type"]
    }
    
    return solver_config


def generate_control_dict(solver: str, analysis_type: AnalysisType, parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate controlDict configuration."""
    # For transient simulations, use smaller time steps and more frequent output
    if analysis_type == AnalysisType.UNSTEADY or "pimple" in solver.lower():
        # Calculate appropriate time step based on flow parameters
        velocity = parsed_params.get("velocity", 1.0)
        
        # Ensure velocity is valid
        if velocity is None or velocity <= 0:
            logger.warning(f"Invalid velocity ({velocity}), using default 1.0 m/s")
            velocity = 1.0
        
        # Get characteristic length from geometry
        characteristic_length = None
        
        # First try parsed parameters
        if "characteristic_length" in parsed_params and parsed_params["characteristic_length"] > 0:
            characteristic_length = parsed_params["characteristic_length"]
            logger.info(f"Using characteristic length from parsed params: {characteristic_length} m")
        
        # Then try geometry dimensions
        if characteristic_length is None and geometry_info:
            dimensions = geometry_info.get("dimensions", {})
            if dimensions:
                # Try diameter-like dimensions first
                diameter_keys = ['diameter', 'cylinder_diameter', 'sphere_diameter', 'pipe_diameter']
                for key in diameter_keys:
                    if key in dimensions and dimensions[key] is not None and dimensions[key] > 0:
                        characteristic_length = dimensions[key]
                        logger.info(f"Using {key} as characteristic length: {characteristic_length} m")
                        break
                
                # If no diameter found, use height/width for channels
                if characteristic_length is None:
                    for key in ['height', 'width']:
                        if key in dimensions and dimensions[key] is not None and dimensions[key] > 0:
                            characteristic_length = dimensions[key]
                            logger.info(f"Using {key} as characteristic length: {characteristic_length} m")
                            break
                
                # Last resort - use any valid dimension
                if characteristic_length is None:
                    valid_dims = [(k, v) for k, v in dimensions.items() 
                                  if v is not None and isinstance(v, (int, float)) and v > 0]
                    if valid_dims:
                        key, value = min(valid_dims, key=lambda x: x[1])
                        characteristic_length = value
                        logger.info(f"Using {key} as characteristic length: {characteristic_length} m")
        
        # Final fallback with appropriate default based on geometry type
        if characteristic_length is None:
            geometry_type = geometry_info.get("type", "unknown")
            # Convert enum to string if needed
            if hasattr(geometry_type, 'value'):
                geometry_type_str = geometry_type.value
            else:
                geometry_type_str = str(geometry_type).lower()
                
            if "cylinder" in geometry_type_str:
                characteristic_length = 0.01  # 1cm cylinder
            elif "channel" in geometry_type_str:
                characteristic_length = 0.02  # 2cm channel height
            elif "pipe" in geometry_type_str:
                characteristic_length = 0.05  # 5cm pipe diameter
            else:
                characteristic_length = 0.1   # 10cm default
            logger.warning(f"No valid dimensions found, using default characteristic length for {geometry_type_str}: {characteristic_length} m")
        
        # Calculate time step with Courant number consideration
        target_courant = 0.5
        # Estimate cell size (assuming ~20-40 cells across characteristic length)
        mesh_resolution = parsed_params.get("mesh_resolution", "medium")
        cells_per_length = {"coarse": 20, "medium": 30, "fine": 40}.get(mesh_resolution, 30)
        cell_size = characteristic_length / cells_per_length
        
        # Calculate time step
        estimated_dt = target_courant * cell_size / velocity
        
        # Apply reasonable bounds
        min_dt = 1e-6  # Minimum time step
        max_dt = 0.01  # Maximum time step for transient flows
        
        if estimated_dt < min_dt:
            logger.warning(f"Calculated deltaT ({estimated_dt:.2e}) too small, using minimum {min_dt}")
            estimated_dt = min_dt
        elif estimated_dt > max_dt:
            logger.info(f"Calculated deltaT ({estimated_dt:.2e}) limited to maximum {max_dt}")
            estimated_dt = max_dt
        
        # Log final deltaT calculation
        logger.info(f"Calculated deltaT: {estimated_dt:.6f} s (velocity={velocity} m/s, characteristic_length={characteristic_length} m, cell_size={cell_size:.6f} m)")
        
        # Time settings with user control
        # Default to 1 second for quick demonstrations
        end_time = parsed_params.get("simulation_time", 1.0)
        if end_time is None:
            end_time = 1.0
        # Write 10 snapshots or every 0.1s, whichever is smaller
        write_interval = min(0.1, end_time / 10.0)
        
        # Check if user wants fixed time stepping
        # Support both time_step and fixed_time_step parameter names
        fixed_dt = parsed_params.get("fixed_time_step") or parsed_params.get("time_step")
        use_adaptive = fixed_dt is None  # Adaptive by default unless user specifies fixed dt
        
        control_dict = {
            "application": solver,
            "startFrom": "startTime",
            "startTime": 0,
            "stopAt": "endTime",
            "endTime": end_time,
            "deltaT": fixed_dt if fixed_dt else estimated_dt,
            "writeControl": "adjustableRunTime" if use_adaptive else "runTime",
            "writeInterval": write_interval,
            "purgeWrite": 0,
            "writeFormat": "ascii",
            "writePrecision": 6,
            "writeCompression": "off",
            "timeFormat": "general",
            "timePrecision": 6,
            "runTimeModifiable": "true"
        }
        
        # Add adaptive time stepping controls if not using fixed time step
        if use_adaptive:
            control_dict.update({
                "adjustTimeStep": "yes",
                "maxCo": 0.9,  # Maximum Courant number
                "maxDeltaT": min(0.01, estimated_dt * 10)  # Cap at 10x initial estimate
            })
            logger.info(f"Using adaptive time stepping with maxCo=0.9, initial deltaT={estimated_dt:.6f}")
        else:
            control_dict["adjustTimeStep"] = "no"
            logger.info(f"Using fixed time step: deltaT={fixed_dt}")
        
        return control_dict
    else:
        # Steady state configuration
        return {
            "application": solver,
            "startFrom": "startTime",
            "startTime": 0,
            "stopAt": "endTime",
            "endTime": 1000,
            "deltaT": 1,
            "writeControl": "runTime",
            "writeInterval": 100,
            "purgeWrite": 0,
            "writeFormat": "ascii",
            "writePrecision": 6,
            "writeCompression": "off",
            "timeFormat": "general",
            "timePrecision": 6,
            "runTimeModifiable": "true"
        }


def generate_fv_schemes(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate fvSchemes file."""
    analysis_type = solver_settings.get("analysis_type", AnalysisType.UNSTEADY)
    flow_type = solver_settings.get("flow_type", FlowType.LAMINAR)
    
    # Base schemes
    fv_schemes = {
        "ddtSchemes": {},
        "gradSchemes": {
            "default": "Gauss linear",
            "grad(p)": "Gauss linear",
            "grad(U)": "Gauss linear"
        },
        "divSchemes": {
            "default": "none"
        },
        "laplacianSchemes": {
            "default": "Gauss linear orthogonal"
        },
        "interpolationSchemes": {
            "default": "linear"
        },
        "snGradSchemes": {
            "default": "orthogonal"
        }
    }
    
    # Add wallDist for turbulent flows
    if flow_type == FlowType.TURBULENT:
        fv_schemes["wallDist"] = {
            "method": "meshWave"
        }
    
    # Time derivative schemes
    if analysis_type == AnalysisType.STEADY:
        fv_schemes["ddtSchemes"]["default"] = "steadyState"
    else:
        fv_schemes["ddtSchemes"]["default"] = "backward"
    
    # Divergence schemes
    if flow_type == FlowType.LAMINAR:
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "bounded Gauss linearUpwind grad(U)",
            "div(phi,p)": "bounded Gauss upwind",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear"
        })
    else:
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "bounded Gauss linearUpwindV grad(U)",
            "div(phi,k)": "bounded Gauss upwind",
            "div(phi,omega)": "bounded Gauss upwind",
            "div(phi,epsilon)": "bounded Gauss upwind",
            "div((nuEff*dev2(T(grad(U)))))": "Gauss linear"
        })
    
    return fv_schemes


def generate_fv_solution(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate fvSolution file."""
    analysis_type = solver_settings.get("analysis_type", AnalysisType.UNSTEADY)
    flow_type = solver_settings.get("flow_type", FlowType.LAMINAR)
    
    # Base solution settings
    fv_solution = {
        "solvers": {},
        "SIMPLE": {},
        "PIMPLE": {},
        "relaxationFactors": {},
        "residualControl": {}
    }
    
    # Pressure solver
    fv_solution["solvers"]["p"] = {
        "solver": "GAMG",
        "tolerance": 1e-06,
        "relTol": 0.1,
        "smoother": "GaussSeidel",
        "nPreSweeps": 0,
        "nPostSweeps": 2,
        "cacheAgglomeration": "true",
        "nCellsInCoarsestLevel": 10,
        "agglomerator": "faceAreaPair",
        "mergeLevels": 1
    }
    
    # Velocity solver
    fv_solution["solvers"]["U"] = {
        "solver": "smoothSolver",
        "smoother": "GaussSeidel",
        "tolerance": 1e-05,
        "relTol": 0.1
    }
    
    # For PIMPLE, we need UFinal as well
    if analysis_type == AnalysisType.UNSTEADY:
        fv_solution["solvers"]["UFinal"] = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0
        }
        fv_solution["solvers"]["pFinal"] = {
            "solver": "GAMG",
            "tolerance": 1e-06,
            "relTol": 0,
            "smoother": "GaussSeidel",
            "nPreSweeps": 0,
            "nPostSweeps": 2,
            "cacheAgglomeration": "true",
            "nCellsInCoarsestLevel": 10,
            "agglomerator": "faceAreaPair",
            "mergeLevels": 1
        }
    
    # Turbulence field solvers
    if flow_type == FlowType.TURBULENT:
        turbulence_solver = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel", 
            "tolerance": 1e-05,
            "relTol": 0.1
        }
        fv_solution["solvers"]["k"] = turbulence_solver.copy()
        fv_solution["solvers"]["omega"] = turbulence_solver.copy()
        fv_solution["solvers"]["epsilon"] = turbulence_solver.copy()
        
        # For PIMPLE, we need final versions as well
        if analysis_type == AnalysisType.UNSTEADY:
            turbulence_solver_final = {
                "solver": "smoothSolver",
                "smoother": "GaussSeidel",
                "tolerance": 1e-06,
                "relTol": 0
            }
            fv_solution["solvers"]["kFinal"] = turbulence_solver_final.copy()
            fv_solution["solvers"]["omegaFinal"] = turbulence_solver_final.copy()
            fv_solution["solvers"]["epsilonFinal"] = turbulence_solver_final.copy()
    
    # Algorithm settings
    if analysis_type == AnalysisType.STEADY:
        fv_solution["SIMPLE"] = {
            "nNonOrthogonalCorrectors": 0,
            "consistent": "true",
            "residualControl": {
                "p": 1e-02,
                "U": 1e-03
            }
        }
        
        if flow_type == FlowType.TURBULENT:
            fv_solution["SIMPLE"]["residualControl"].update({
                "k": 1e-03,
                "omega": 1e-03,
                "epsilon": 1e-03
            })
        
        # Relaxation factors
        fv_solution["relaxationFactors"] = {
            "fields": {"p": 0.3},
            "equations": {"U": 0.7}
        }
        
        if flow_type == FlowType.TURBULENT:
            fv_solution["relaxationFactors"]["equations"].update({
                "k": 0.8,
                "omega": 0.8,
                "epsilon": 0.8
            })
    
    else:
        # Transient PIMPLE settings - simplified for better stability
        fv_solution["PIMPLE"] = {
            "nOuterCorrectors": 1,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1
        }
    
    return fv_solution


def generate_turbulence_properties(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate turbulenceProperties file."""
    flow_type = solver_settings.get("flow_type", FlowType.LAMINAR)
    turbulence_model = solver_settings.get("turbulence_model", "laminar")
    
    if flow_type == FlowType.LAMINAR:
        return {
            "simulationType": "laminar"
        }
    else:
        return {
            "simulationType": "RAS",
            "RAS": {
                "RASModel": turbulence_model,
                "turbulence": "true",
                "printCoeffs": "true"
            }
        }


def generate_transport_properties(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate transportProperties file."""
    density = parsed_params.get("density", 1.225)
    viscosity = parsed_params.get("viscosity", 1.81e-5)
    
    # Handle None values
    if density is None:
        density = 1.225
    if viscosity is None:
        viscosity = 1.81e-5
    
    # Ensure we don't divide by zero
    if density == 0:
        density = 1.225
    
    return {
        "transportModel": "Newtonian",
        "nu": viscosity / density,  # Kinematic viscosity
        "rho": density,  # For compressible flows
        "mu": viscosity  # Dynamic viscosity
    }


def validate_solver_config(solver_config: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate solver configuration."""
    errors = []
    warnings = []
    
    # Check required files
    required_files = ["controlDict", "fvSchemes", "fvSolution", "turbulenceProperties", "transportProperties"]
    for file in required_files:
        if file not in solver_config:
            errors.append(f"Missing required file: {file}")
    
    # Check solver compatibility
    solver = solver_config.get("solver")
    if not solver:
        errors.append("No solver specified")
    elif solver not in ["simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam"]:
        warnings.append(f"Unknown solver: {solver}")
    
    # Check time step for transient simulations
    if solver and "pimple" in solver.lower():
        control_dict = solver_config.get("controlDict", {})
        delta_t = control_dict.get("deltaT", 0)
        if delta_t is not None and delta_t <= 0:
            errors.append("Invalid time step for transient simulation")
    
    # Check Reynolds number vs turbulence model
    reynolds_number = parsed_params.get("reynolds_number", 0)
    turbulence_props = solver_config.get("turbulenceProperties", {})
    simulation_type = turbulence_props.get("simulationType", "")
    
    if reynolds_number is not None and reynolds_number > 2300 and simulation_type == "laminar":
        warnings.append("High Reynolds number with laminar simulation")
    elif reynolds_number is not None and reynolds_number < 2300 and simulation_type == "RAS":
        warnings.append("Low Reynolds number with turbulent simulation")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def get_solver_recommendations(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> list:
    """Generate solver optimization recommendations."""
    recommendations = []
    
    reynolds_number = parsed_params.get("reynolds_number", 0)
    flow_type = solver_settings.get("flow_type", FlowType.LAMINAR)
    analysis_type = solver_settings.get("analysis_type", AnalysisType.UNSTEADY)
    
    # Reynolds number based recommendations
    if reynolds_number is not None and reynolds_number > 100000:
        recommendations.append("Consider using wall functions for high Reynolds number")
    
    # Time step recommendations for transient flows
    if analysis_type == AnalysisType.UNSTEADY:
        geometry_info = parsed_params.get("geometry_info", {})
        velocity = parsed_params.get("velocity", 1.0)
        if velocity is not None and velocity > 10:
            recommendations.append("Use small time step for high velocity flows")
    
    # Turbulence model recommendations
    if flow_type == FlowType.TURBULENT:
        if reynolds_number < 10000:
            recommendations.append("k-omega SST model recommended for low Re turbulence")
        else:
            recommendations.append("k-epsilon model suitable for high Re turbulence")
    
    return recommendations 
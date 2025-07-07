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
    analysis_type = parsed_params.get("analysis_type", AnalysisType.STEADY)
    reynolds_number = parsed_params.get("reynolds_number", 0)
    mach_number = parsed_params.get("mach_number", 0)
    
    # Decision logic for solver selection
    solver_settings = {
        "flow_type": flow_type,
        "analysis_type": analysis_type,
        "reynolds_number": reynolds_number,
        "mach_number": mach_number
    }
    
    # Compressible vs incompressible
    if mach_number and mach_number > 0.3:
        # Compressible flow
        if analysis_type == AnalysisType.STEADY:
            solver_settings["solver"] = "rhoSimpleFoam"
        else:
            solver_settings["solver"] = "rhoPimpleFoam"
        solver_settings["compressible"] = True
    else:
        # Incompressible flow
        if analysis_type == AnalysisType.STEADY:
            if flow_type == FlowType.LAMINAR:
                solver_settings["solver"] = "simpleFoam"
            else:
                solver_settings["solver"] = "simpleFoam"  # Can handle turbulent steady
        else:
            if flow_type == FlowType.LAMINAR:
                solver_settings["solver"] = "pimpleFoam"
            else:
                solver_settings["solver"] = "pimpleFoam"  # Can handle turbulent transient
        solver_settings["compressible"] = False
    
    # Turbulence model selection
    if flow_type == FlowType.TURBULENT:
        if reynolds_number < 10000:
            solver_settings["turbulence_model"] = "kOmegaSST"
        else:
            solver_settings["turbulence_model"] = "kEpsilon"
    else:
        solver_settings["turbulence_model"] = "laminar"
    
    return solver_settings


def generate_solver_config(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete solver configuration."""
    solver_config = {
        "solver": solver_settings["solver"],
        "controlDict": generate_control_dict(solver_settings, parsed_params),
        "fvSchemes": generate_fv_schemes(solver_settings, parsed_params),
        "fvSolution": generate_fv_solution(solver_settings, parsed_params),
        "turbulenceProperties": generate_turbulence_properties(solver_settings, parsed_params),
        "transportProperties": generate_transport_properties(solver_settings, parsed_params)
    }
    
    return solver_config


def generate_control_dict(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate controlDict file."""
    analysis_type = solver_settings.get("analysis_type", AnalysisType.STEADY)
    
    # Base control settings
    control_dict = {
        "application": solver_settings["solver"],
        "startFrom": "startTime",
        "startTime": 0,
        "stopAt": "endTime",
        "writeControl": "timeStep",
        "writeInterval": 100,
        "purgeWrite": 0,
        "writeFormat": "ascii",
        "writePrecision": 6,
        "writeCompression": "off",
        "timeFormat": "general",
        "timePrecision": 6,
        "runTimeModifiable": "true"
    }
    
    if analysis_type == AnalysisType.STEADY:
        # Steady state simulation
        control_dict.update({
            "endTime": 1000,  # Number of iterations
            "deltaT": 1,
            "writeControl": "runTime",
            "writeInterval": 100
        })
    else:
        # Transient simulation
        end_time = parsed_params.get("end_time", 1.0)
        time_step = parsed_params.get("time_step", 0.001)
        
        control_dict.update({
            "endTime": end_time,
            "deltaT": time_step,
            "writeControl": "adjustableRunTime",
            "writeInterval": end_time / 100,  # 100 output files
            "adjustTimeStep": "true",
            "maxCo": 0.5
        })
    
    return control_dict


def generate_fv_schemes(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate fvSchemes file."""
    analysis_type = solver_settings.get("analysis_type", AnalysisType.STEADY)
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
        fv_schemes["ddtSchemes"]["default"] = "Euler"
    
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
    analysis_type = solver_settings.get("analysis_type", AnalysisType.STEADY)
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
        # Transient PIMPLE settings
        fv_solution["PIMPLE"] = {
            "nOuterCorrectors": 1,
            "nCorrectors": 2,
            "nNonOrthogonalCorrectors": 1,
            "residualControl": {
                "p": 1e-02,
                "U": 1e-03
            }
        }
        
        if flow_type == FlowType.TURBULENT:
            fv_solution["PIMPLE"]["residualControl"].update({
                "k": 1e-03,
                "omega": 1e-03,
                "epsilon": 1e-03
            })
    
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
    if "pimple" in solver.lower():
        control_dict = solver_config.get("controlDict", {})
        delta_t = control_dict.get("deltaT", 0)
        if delta_t <= 0:
            errors.append("Invalid time step for transient simulation")
    
    # Check Reynolds number vs turbulence model
    reynolds_number = parsed_params.get("reynolds_number", 0)
    turbulence_props = solver_config.get("turbulenceProperties", {})
    simulation_type = turbulence_props.get("simulationType", "")
    
    if reynolds_number > 2300 and simulation_type == "laminar":
        warnings.append("High Reynolds number with laminar simulation")
    elif reynolds_number < 2300 and simulation_type == "RAS":
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
    analysis_type = solver_settings.get("analysis_type", AnalysisType.STEADY)
    
    # Reynolds number based recommendations
    if reynolds_number > 100000:
        recommendations.append("Consider using wall functions for high Reynolds number")
    
    # Time step recommendations for transient flows
    if analysis_type == AnalysisType.UNSTEADY:
        geometry_info = parsed_params.get("geometry_info", {})
        velocity = parsed_params.get("velocity", 1.0)
        if velocity > 10:
            recommendations.append("Use small time step for high velocity flows")
    
    # Turbulence model recommendations
    if flow_type == FlowType.TURBULENT:
        if reynolds_number < 10000:
            recommendations.append("k-omega SST model recommended for low Re turbulence")
        else:
            recommendations.append("k-epsilon model suitable for high Re turbulence")
    
    return recommendations 
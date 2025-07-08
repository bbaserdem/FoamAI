"""Solver Selector Agent - Chooses appropriate OpenFOAM solvers and configurations."""

from typing import Dict, Any, Optional, List
from loguru import logger
import re

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType, SolverType


# Solver Registry - defines available solvers and their characteristics
SOLVER_REGISTRY = {
    SolverType.SIMPLE_FOAM: {
        "name": "simpleFoam",
        "description": "Steady-state incompressible flow solver using SIMPLE algorithm",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["steady"],
            "turbulence": ["laminar", "RANS"],
            "heat_transfer": False,
            "multiphase": False,
            "compressible": False
        },
        "recommended_for": [
            "Low Reynolds number flows (Re < 40-50 for cylinders)",
            "Steady aerodynamic analysis",
            "Pressure drop calculations",
            "Design optimization studies",
            "Flows without vortex shedding"
        ],
        "not_recommended_for": [
            "Vortex shedding analysis",
            "Transient phenomena",
            "Startup/shutdown simulations",
            "Time-periodic flows"
        ],
        "typical_applications": [
            "Internal flows in pipes/ducts",
            "External aerodynamics at low Re",
            "HVAC system design",
            "Steady heat exchanger flows"
        ]
    },
    SolverType.PIMPLE_FOAM: {
        "name": "pimpleFoam",
        "description": "Transient incompressible flow solver using PIMPLE algorithm",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["transient", "steady"],  # Can do both
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": False,
            "multiphase": False,
            "compressible": False
        },
        "recommended_for": [
            "Vortex shedding analysis",
            "Moderate to high Reynolds number flows",
            "Time-dependent phenomena",
            "Flow development studies",
            "Unsteady aerodynamics"
        ],
        "not_recommended_for": [
            "Quick steady-state solutions",
            "Very low Reynolds number flows",
            "Cases where only final state matters"
        ],
        "typical_applications": [
            "Bluff body flows",
            "Turbulent wakes",
            "Oscillating flows",
            "Transient HVAC scenarios"
        ]
    }
}


def solver_selector_agent(state: CFDState) -> CFDState:
    """
    Enhanced Solver Selector Agent using AI-based decision making.
    
    Chooses appropriate OpenFOAM solver and generates solver configuration
    files (fvSchemes, fvSolution, controlDict) based on flow parameters.
    """
    try:
        if state["verbose"]:
            logger.info("Solver Selector: Starting solver selection")
        
        parsed_params = state["parsed_parameters"]
        geometry_info = state["geometry_info"]
        
        # Extract problem features for AI decision
        problem_features = extract_problem_features(state)
        
        # Get AI recommendation for solver
        solver_recommendation = get_ai_solver_recommendation(
            problem_features, 
            SOLVER_REGISTRY
        )
        
        # Build solver settings with the recommended solver
        solver_settings = build_solver_settings(
            solver_recommendation,
            parsed_params,
            geometry_info
        )
        
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


def extract_problem_features(state: CFDState) -> Dict[str, Any]:
    """Extract key features for solver selection."""
    params = state["parsed_parameters"]
    geometry = state["geometry_info"]
    
    # Calculate dimensionless numbers
    reynolds_number = params.get("reynolds_number", 0)
    velocity = params.get("velocity", None)
    density = params.get("density", 1.225)
    viscosity = params.get("viscosity", 1.81e-5)
    
    # If velocity is not provided but Reynolds number is, calculate velocity
    if velocity is None and reynolds_number > 0:
        # Get characteristic length based on geometry
        geometry_type = geometry["type"]
        if geometry_type == GeometryType.CYLINDER:
            char_length = geometry.get("diameter", 0.1)
        elif geometry_type == GeometryType.SPHERE:
            char_length = geometry.get("diameter", 0.1)
        elif geometry_type == GeometryType.CUBE:
            char_length = geometry.get("side_length", 0.1)
        elif geometry_type == GeometryType.AIRFOIL:
            char_length = geometry.get("chord_length", 0.1)
        elif geometry_type == GeometryType.PIPE:
            char_length = geometry.get("diameter", 0.1)
        elif geometry_type == GeometryType.CHANNEL:
            char_length = geometry.get("height", 0.1)
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
        logger.info(f"Calculated velocity {velocity:.3f} m/s from Reynolds number {reynolds_number}")
    
    # Default velocity if still None
    if velocity is None:
        velocity = 1.0
    
    speed_of_sound = 343.0  # m/s at 20°C
    mach_number = velocity / speed_of_sound if velocity else 0
    
    # Determine expected flow phenomena
    expects_vortex_shedding = check_vortex_shedding(
        geometry["type"], 
        reynolds_number
    )
    
    # Extract keywords from original prompt
    original_prompt = state.get("original_prompt", "")
    keywords = extract_keywords(original_prompt)
    
    return {
        "geometry_type": geometry["type"].value if hasattr(geometry["type"], 'value') else str(geometry["type"]),
        "reynolds_number": reynolds_number,
        "mach_number": mach_number,
        "flow_type": params.get("flow_type", FlowType.LAMINAR),
        "analysis_type": params.get("analysis_type", AnalysisType.UNSTEADY),
        "expects_vortex_shedding": expects_vortex_shedding,
        "has_heat_transfer": params.get("temperature") is not None,
        "is_compressible": mach_number > 0.3,
        "user_keywords": keywords,
        "time_scale_interest": infer_time_scale_interest(params, keywords)
    }


def check_vortex_shedding(geometry_type: GeometryType, reynolds_number: float) -> bool:
    """Check if vortex shedding is expected based on geometry and Re."""
    if reynolds_number <= 0:
        return False
    
    # Geometry-specific vortex shedding thresholds
    vortex_shedding_thresholds = {
        GeometryType.CYLINDER: 40,      # Vortex shedding starts around Re=40
        GeometryType.SPHERE: 200,        # Vortex shedding starts around Re=200
        GeometryType.CUBE: 50,           # Similar to cylinder
        GeometryType.AIRFOIL: 100000,    # Much higher for streamlined bodies
    }
    
    threshold = vortex_shedding_thresholds.get(geometry_type, 100)
    return reynolds_number > threshold


def extract_keywords(prompt: str) -> List[str]:
    """Extract relevant keywords from user prompt."""
    # Convert to lowercase for matching
    prompt_lower = prompt.lower()
    
    # Keywords that suggest specific solver needs
    steady_keywords = ["steady", "equilibrium", "final", "converged", "pressure drop", "drag coefficient"]
    transient_keywords = ["transient", "time", "unsteady", "vortex", "shedding", "oscillat", "frequency", 
                         "startup", "development", "periodic"]
    
    found_keywords = []
    
    for keyword in steady_keywords:
        if keyword in prompt_lower:
            found_keywords.append(f"steady:{keyword}")
    
    for keyword in transient_keywords:
        if keyword in prompt_lower:
            found_keywords.append(f"transient:{keyword}")
    
    return found_keywords


def infer_time_scale_interest(params: Dict[str, Any], keywords: List[str]) -> str:
    """Infer whether user is interested in transient or steady behavior."""
    # Check explicit analysis type
    if params.get("analysis_type") == AnalysisType.STEADY:
        return "steady"
    elif params.get("analysis_type") == AnalysisType.UNSTEADY:
        return "transient"
    
    # Check keywords
    steady_count = sum(1 for k in keywords if k.startswith("steady:"))
    transient_count = sum(1 for k in keywords if k.startswith("transient:"))
    
    if steady_count > transient_count:
        return "steady"
    elif transient_count > steady_count:
        return "transient"
    else:
        return "unknown"


def get_ai_solver_recommendation(
    features: Dict[str, Any], 
    solver_registry: Dict[SolverType, Dict]
) -> SolverType:
    """
    AI agent logic to select best solver based on problem features.
    This is where the intelligence lives.
    """
    
    # Log the decision process
    logger.info(f"AI Solver Selection - Problem features:")
    logger.info(f"  Geometry: {features['geometry_type']}")
    logger.info(f"  Reynolds Number: {features['reynolds_number']}")
    logger.info(f"  Analysis Type: {features['analysis_type']}")
    logger.info(f"  Expects Vortex Shedding: {features['expects_vortex_shedding']}")
    logger.info(f"  Time Scale Interest: {features['time_scale_interest']}")
    logger.info(f"  Keywords: {features['user_keywords']}")
    
    # Decision logic
    # Priority 1: Explicit steady-state request
    if features['analysis_type'] == AnalysisType.STEADY or features['time_scale_interest'] == "steady":
        logger.info("AI Decision: Explicit steady-state request → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Priority 2: Low Reynolds number without vortex shedding
    if not features['expects_vortex_shedding'] and features['reynolds_number'] < 100:
        logger.info(f"AI Decision: Low Re={features['reynolds_number']} without vortex shedding → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Priority 3: Keywords strongly suggesting steady state
    steady_keywords = ["pressure drop", "drag coefficient", "lift coefficient", "steady", "equilibrium"]
    if any(f"steady:{kw}" in features['user_keywords'] for kw in steady_keywords):
        logger.info("AI Decision: Steady-state keywords detected → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Priority 4: Vortex shedding or explicit transient request
    if features['expects_vortex_shedding'] or features['analysis_type'] == AnalysisType.UNSTEADY:
        logger.info("AI Decision: Vortex shedding expected or transient requested → pimpleFoam")
        return SolverType.PIMPLE_FOAM
    
    # Priority 5: Transient keywords
    transient_keywords = ["vortex", "shedding", "frequency", "oscillat", "time", "transient"]
    if any(f"transient:{kw}" in features['user_keywords'] for kw in transient_keywords):
        logger.info("AI Decision: Transient keywords detected → pimpleFoam")
        return SolverType.PIMPLE_FOAM
    
    # Default: For ambiguous cases, prefer efficiency
    if features['time_scale_interest'] == "unknown":
        logger.info("AI Decision: Ambiguous case, defaulting to efficient steady solver → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Final fallback
    logger.info("AI Decision: Default fallback → pimpleFoam")
    return SolverType.PIMPLE_FOAM


def build_solver_settings(
    solver_type: SolverType,
    parsed_params: Dict[str, Any],
    geometry_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Build complete solver settings based on selected solver type."""
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    reynolds_number = parsed_params.get("reynolds_number", 0)
    
    # Determine analysis type based on solver
    if solver_type == SolverType.SIMPLE_FOAM:
        analysis_type = AnalysisType.STEADY
    else:
        analysis_type = AnalysisType.UNSTEADY
    
    # Get solver info from registry
    solver_info = SOLVER_REGISTRY[solver_type]
    
    solver_settings = {
        "solver": solver_info["name"],
        "solver_type": solver_type,
        "flow_type": flow_type,
        "analysis_type": analysis_type,
        "reynolds_number": reynolds_number,
        "mach_number": parsed_params.get("mach_number", 0),
        "compressible": False  # Both solvers are incompressible
    }
    
    # Turbulence model selection
    if flow_type == FlowType.TURBULENT:
        if reynolds_number is not None and reynolds_number < 10000:
            solver_settings["turbulence_model"] = "kOmegaSST"
        elif reynolds_number is not None and reynolds_number >= 10000:
            solver_settings["turbulence_model"] = "kEpsilon"
        else:
            solver_settings["turbulence_model"] = "kOmegaSST"
    else:
        solver_settings["turbulence_model"] = "laminar"
    
    return solver_settings


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
    # Check if this is a transient solver
    if analysis_type == AnalysisType.UNSTEADY or "pimple" in solver.lower():
        # Calculate appropriate time step based on flow parameters
        velocity = parsed_params.get("velocity", None)
        
        # If velocity is not provided but Reynolds number is, calculate velocity
        if velocity is None and parsed_params.get("reynolds_number", 0) > 0:
            reynolds_number = parsed_params["reynolds_number"]
            density = parsed_params.get("density", 1.225)
            viscosity = parsed_params.get("viscosity", 1.81e-5)
            
            # Get characteristic length based on geometry
            if geometry_info["type"] == GeometryType.CYLINDER:
                char_length = geometry_info.get("diameter", 0.1)
            elif geometry_info["type"] == GeometryType.SPHERE:
                char_length = geometry_info.get("diameter", 0.1)
            elif geometry_info["type"] == GeometryType.CUBE:
                char_length = geometry_info.get("side_length", 0.1)
            elif geometry_info["type"] == GeometryType.AIRFOIL:
                char_length = geometry_info.get("chord_length", 0.1)
            elif geometry_info["type"] == GeometryType.PIPE:
                char_length = geometry_info.get("diameter", 0.1)
            elif geometry_info["type"] == GeometryType.CHANNEL:
                char_length = geometry_info.get("height", 0.1)
            else:
                char_length = 0.1  # Default
            
            # Calculate velocity from Re = ρ * V * L / μ
            velocity = reynolds_number * viscosity / (density * char_length)
            logger.info(f"Calculated velocity {velocity:.3f} m/s from Reynolds number {reynolds_number} for time step calculation")
        
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
        # Adjust SIMPLE settings based on Reynolds number
        reynolds_number = parsed_params.get("reynolds_number", 1000)
        
        # Low Re flows might need more correctors
        if reynolds_number < 100:
            n_corr = 1  # More corrections for stability
            p_tol = 1e-02
            u_tol = 1e-03
        else:
            n_corr = 0
            p_tol = 1e-02
            u_tol = 1e-03
        
        fv_solution["SIMPLE"] = {
            "nNonOrthogonalCorrectors": n_corr,
            "consistent": "true",
            "residualControl": {
                "p": p_tol,
                "U": u_tol
            }
        }
        
        if flow_type == FlowType.TURBULENT:
            fv_solution["SIMPLE"]["residualControl"].update({
                "k": 1e-03,
                "omega": 1e-03,
                "epsilon": 1e-03
            })
        
        # Relaxation factors - adjust based on Reynolds number for stability
        reynolds_number = parsed_params.get("reynolds_number", 1000)
        
        if reynolds_number < 100:  # Very low Re flows need more relaxation
            p_relax = 0.1
            u_relax = 0.3
            turb_relax = 0.3
            logger.info(f"Using conservative relaxation factors for low Re={reynolds_number}: p={p_relax}, U={u_relax}")
        elif reynolds_number < 1000:  # Moderate Re
            p_relax = 0.2
            u_relax = 0.5
            turb_relax = 0.5
        else:  # Higher Re
            p_relax = 0.3
            u_relax = 0.7
            turb_relax = 0.7
        
        fv_solution["relaxationFactors"] = {
            "fields": {"p": p_relax},
            "equations": {"U": u_relax}
        }
        
        if flow_type == FlowType.TURBULENT:
            fv_solution["relaxationFactors"]["equations"].update({
                "k": turb_relax,
                "omega": turb_relax,
                "epsilon": turb_relax
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
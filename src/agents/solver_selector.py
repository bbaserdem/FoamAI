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
    },
    SolverType.INTER_FOAM: {
        "name": "interFoam",
        "description": "Multiphase flow solver using Volume of Fluid (VOF) method",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["transient"],  # Always transient
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": False,
            "multiphase": True,
            "compressible": False
        },
        "recommended_for": [
            "Free surface flows",
            "Air-water interfaces",
            "Dam break simulations",
            "Wave propagation",
            "Filling/draining processes",
            "Sloshing tanks",
            "Marine/naval applications"
        ],
        "not_recommended_for": [
            "Single-phase flows",
            "Steady-state analysis",
            "Fully submerged flows",
            "Cases without clear phase interface"
        ],
        "typical_applications": [
            "Dam break flows",
            "Wave impact on structures",
            "Tank sloshing",
            "Ship hydrodynamics",
            "Droplet dynamics",
            "Bubble rise in liquids"
        ]
    },
    SolverType.RHO_PIMPLE_FOAM: {
        "name": "rhoPimpleFoam",
        "description": "Transient compressible flow solver for subsonic/transonic/supersonic flows",
        "capabilities": {
            "flow_type": ["compressible"],
            "time_dependency": ["transient", "steady"],  # Can do both
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": True,
            "multiphase": False,
            "compressible": True
        },
        "recommended_for": [
            "High-speed flows (Mach > 0.3)",
            "Shock wave propagation",
            "Compressible turbulence",
            "Gas dynamics",
            "Transonic/supersonic flows",
            "Temperature-dependent flows",
            "Pressure wave propagation"
        ],
        "not_recommended_for": [
            "Low-speed incompressible flows",
            "Flows with Mach < 0.3",
            "Liquid flows",
            "Free surface problems"
        ],
        "typical_applications": [
            "Shock tube problems",
            "Nozzle flows",
            "Jet flows",
            "Compressor/turbine passages",
            "High-speed aerodynamics",
            "Blast wave propagation"
        ]
    },
    SolverType.CHT_MULTI_REGION_FOAM: {
        "name": "chtMultiRegionFoam",
        "description": "Conjugate heat transfer solver for solid-fluid thermal coupling",
        "capabilities": {
            "flow_type": ["incompressible", "compressible"],
            "time_dependency": ["transient", "steady"],
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": True,
            "multiphase": False,
            "compressible": True,
            "multi_region": True
        },
        "recommended_for": [
            "Heat exchangers",
            "Electronic cooling",
            "Thermal management systems",
            "Solid-fluid heat transfer",
            "Conjugate heat transfer problems",
            "Multi-region thermal analysis",
            "Thermal boundary layer flows",
            "Natural convection with solid walls"
        ],
        "not_recommended_for": [
            "Isothermal flows",
            "Single-region problems",
            "Flows without heat transfer",
            "Pure fluid dynamics"
        ],
        "typical_applications": [
            "CPU/GPU cooling",
            "Heat sink design",
            "Building thermal analysis",
            "Pipe flow with wall conduction",
            "Nuclear reactor cooling",
            "Thermal insulation studies",
            "Industrial furnaces"
        ]
    },
    SolverType.REACTING_FOAM: {
        "name": "reactingFoam",
        "description": "Reactive flow solver for combustion and chemical reactions",
        "capabilities": {
            "flow_type": ["compressible"],
            "time_dependency": ["transient"],
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": True,
            "multiphase": False,
            "compressible": True,
            "chemical_reactions": True
        },
        "recommended_for": [
            "Combustion simulations",
            "Chemical reactors",
            "Flame propagation",
            "Detonation waves",
            "Species transport with reactions",
            "Premixed/non-premixed combustion",
            "Industrial burners",
            "Engine combustion"
        ],
        "not_recommended_for": [
            "Non-reactive flows",
            "Isothermal flows",
            "Incompressible flows",
            "Simple heat transfer"
        ],
        "typical_applications": [
            "Gas turbine combustors",
            "Internal combustion engines",
            "Industrial furnaces and burners",
            "Rocket engines",
            "Chemical process reactors",
            "Flame stability analysis",
            "Pollutant formation studies",
            "Fire safety simulations"
        ]
    }
}


# Default phase properties for multiphase simulations (water-air at 20°C)
DEFAULT_PHASE_PROPERTIES = {
    "water": {
        "density": 998.2,        # kg/m³
        "viscosity": 1.002e-3,   # Pa·s
        "surface_tension": 0.0728 # N/m (water-air interface)
    },
    "air": {
        "density": 1.204,        # kg/m³
        "viscosity": 1.825e-5    # Pa·s
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
        solver_config = generate_solver_config(solver_settings, parsed_params, geometry_info, state)
        
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
        import traceback
        logger.error(f"Solver Selector error: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
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
    if velocity is None and reynolds_number is not None and reynolds_number > 0:
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
    original_prompt = state.get("original_prompt", state.get("user_prompt", ""))
    keywords = extract_keywords(original_prompt)
    
    # Check for multiphase indicators
    is_multiphase = params.get("is_multiphase", False) or check_multiphase_indicators(original_prompt, params)
    phases = params.get("phases", [])
    free_surface = params.get("free_surface", False) or any("free surface" in kw.lower() for kw in keywords)
    
    # Check for compressibility
    is_compressible = params.get("compressible", False) or (mach_number is not None and mach_number > 0.3) or check_compressible_indicators(original_prompt)
    
    # Check for heat transfer
    has_heat_transfer = check_heat_transfer_indicators(original_prompt, params)
    
    # Check for reactive flows
    has_reactive_flow = check_reactive_flow_indicators(original_prompt, params)
    
    # Check for multi-region (solid-fluid coupling)
    multi_region_keywords = ["multi-region", "multiregion", "multi region", "solid-fluid", "solid fluid", 
                            "conjugate", "cht", "solid wall", "wall conduction", "coupling between"]
    is_multi_region = any(kw in original_prompt.lower() for kw in multi_region_keywords)
    
    return {
        "geometry_type": geometry["type"].value if hasattr(geometry["type"], 'value') else str(geometry["type"]),
        "reynolds_number": reynolds_number,
        "mach_number": mach_number,
        "flow_type": params.get("flow_type", FlowType.LAMINAR),
        "analysis_type": params.get("analysis_type", AnalysisType.UNSTEADY),
        "expects_vortex_shedding": expects_vortex_shedding,
        "has_heat_transfer": has_heat_transfer,
        "is_compressible": is_compressible,
        "is_multiphase": is_multiphase,
        "phases": phases,
        "free_surface": free_surface,
        "has_reactive_flow": has_reactive_flow,
        "is_multi_region": is_multi_region,
        "user_keywords": keywords,
        "time_scale_interest": infer_time_scale_interest(params, keywords)
    }


def check_vortex_shedding(geometry_type: GeometryType, reynolds_number: float) -> bool:
    """Check if vortex shedding is expected based on geometry and Re."""
    if reynolds_number is None or reynolds_number <= 0:
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


def check_multiphase_indicators(prompt: str, params: Dict[str, Any]) -> bool:
    """Check if the problem involves multiphase flow based on prompt and parameters."""
    import re
    prompt_lower = prompt.lower()
    
    # Multiphase keywords with word boundaries to avoid false positives
    multiphase_keywords = [
        r"\bwater\b", r"\bliquid\b", r"\bgas\b", r"\binterface\b",
        r"\bfree surface\b", r"\bvof\b", r"\bvolume of fluid\b", r"\bmultiphase\b",
        r"\bdam break\b", r"\bwave\b", r"\bdroplet\b", r"\bbubble\b", r"\bsplash\b",
        r"\bfilling\b", r"\bdraining\b", r"\bsloshing\b", r"\bmarine\b", r"\bnaval\b"
    ]
    
    # Special handling for "air" - only match as standalone word and check context
    air_pattern = r"\bair\b"
    if re.search(air_pattern, prompt_lower):
        # Check if it's in context of multiphase flow (with other fluids)
        # Use broader patterns to catch compound words like "underwater"
        other_fluids = [r"\bwater\b", r"water", r"\bliquid\b", r"liquid", r"\boil\b"]
        if any(re.search(fluid, prompt_lower) for fluid in other_fluids):
            return True
        # Check for explicit multiphase indicators with air
        multiphase_contexts = [
            r"\bair.*water\b", r"\bwater.*air\b", r"water.*air", r"air.*water",
            r"\btwo.*phase\b", r"\bfree surface\b", r"\bdam break\b", r"\bwave\b"
        ]
        if any(re.search(context, prompt_lower) for context in multiphase_contexts):
            return True
    
    # Check for other multiphase keywords
    for keyword in multiphase_keywords:
        if re.search(keyword, prompt_lower):
            return True
    
    # Check if multiple fluids are mentioned using word boundaries
    # Include both strict word boundaries and relaxed patterns for compound words
    fluids = [r"\bwater\b", r"water", r"\boil\b", r"\bair\b", r"\bgas\b", r"\bliquid\b", r"liquid"]
    unique_fluids = set()
    for fluid in fluids:
        if re.search(fluid, prompt_lower):
            # Normalize to base fluid name to avoid double counting
            base_fluid = fluid.replace(r"\b", "").replace(r"\\b", "")
            unique_fluids.add(base_fluid)
    
    if len(unique_fluids) >= 2:
        return True
    
    return False


def check_compressible_indicators(prompt: str) -> bool:
    """Check if the problem involves compressible flow based on prompt."""
    prompt_lower = prompt.lower()
    
    # Compressible flow keywords
    compressible_keywords = [
        "compressible", "shock", "supersonic", "transonic", "mach",
        "high-speed", "high speed", "sonic boom", "shock wave",
        "gas dynamics", "nozzle", "jet", "rocket", "blast"
    ]
    
    # Check for keyword presence
    for keyword in compressible_keywords:
        if keyword in prompt_lower:
            return True
    
    return False


def check_heat_transfer_indicators(prompt: str, params: Dict[str, Any]) -> bool:
    """Check if the problem involves heat transfer based on prompt and parameters."""
    prompt_lower = prompt.lower()
    
    # Heat transfer keywords
    heat_keywords = [
        "heat", "thermal", "temperature", "cooling", "heating",
        "heat transfer", "conjugate", "conduction", "convection",
        "radiation", "heat flux", "thermal boundary", "heat exchanger",
        "insulation", "heat sink", "thermal management", "cfd-cht",
        "multi-region", "solid-fluid", "wall temperature"
    ]
    
    # Check for keyword presence
    for keyword in heat_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check if temperature is specified in parameters
    if params.get("temperature") is not None:
        return True
    
    return False


def check_reactive_flow_indicators(prompt: str, params: Dict[str, Any]) -> bool:
    """Check if the problem involves reactive flows/combustion based on prompt."""
    prompt_lower = prompt.lower()
    
    # Reactive flow keywords
    reactive_keywords = [
        "combustion", "burning", "flame", "ignition", "reaction",
        "chemical", "species", "fuel", "oxidizer", "premixed",
        "non-premixed", "diffusion flame", "detonation", "deflagration",
        "burner", "combustor", "engine", "propulsion", "fire",
        "reacting", "reactive", "chemistry", "mixture fraction",
        "methane", "propane", "hydrogen", "ethane", "gasoline"
    ]
    
    # Check for keyword presence
    for keyword in reactive_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check if species or reactions are specified in parameters
    if params.get("chemical_species") or params.get("reactions"):
        return True
    
    return False


def extract_keywords(prompt: str) -> List[str]:
    """Extract relevant keywords from user prompt."""
    import re
    # Convert to lowercase for matching
    prompt_lower = prompt.lower()
    
    # Keywords that suggest specific solver needs - using word boundaries
    steady_keywords = [r"\bsteady\b", r"\bequilibrium\b", r"\bfinal\b", r"\bconverged\b", 
                      r"\bpressure drop\b", r"\bdrag coefficient\b"]
    transient_keywords = [r"\btransient\b", r"\btime\b", r"\bunsteady\b", r"\bvortex\b", 
                         r"\bshedding\b", r"\boscillat\w*\b", r"\bfrequency\b", 
                         r"\bstartup\b", r"\bdevelopment\b", r"\bperiodic\b"]
    multiphase_keywords = [r"\bwater\b", r"\binterface\b", r"\bfree surface\b", r"\bvof\b", 
                          r"\bmultiphase\b", r"\bdam break\b", r"\bwave\b", r"\bdroplet\b", 
                          r"\bbubble\b", r"\bsloshing\b"]
    compressible_keywords = [r"\bshock\b", r"\bsupersonic\b", r"\btransonic\b", r"\bmach\b", 
                            r"\bcompressible\b", r"\bhigh-speed\b", r"\bgas dynamics\b", 
                            r"\bnozzle\b", r"\bjet\b", r"\bblast\b"]
    heat_transfer_keywords = [r"\bheat\b", r"\bthermal\b", r"\btemperature\b", r"\bcooling\b", 
                             r"\bheating\b", r"\bconjugate\b", r"\bconduction\b", r"\bconvection\b", 
                             r"\bheat exchanger\b", r"\bheat sink\b", r"\binsulation\b", 
                             r"\bmulti-region\b", r"\bmulti region\b", r"\bwall conduction\b", 
                             r"\bsolid wall\b", r"\bcht\b", r"\bcoupling\b"]
    reactive_keywords = [r"\bcombustion\b", r"\bflame\b", r"\breaction\b", r"\bchemical\b", 
                        r"\bburning\b", r"\bfuel\b", r"\bignition\b", r"\bspecies\b", 
                        r"\bburner\b", r"\bengine\b", r"\breacting\b", r"\bmethane\b", 
                        r"\bpropane\b", r"\bhydrogen\b", r"\bethane\b", r"\bgasoline\b"]
    
    found_keywords = []
    
    for keyword in steady_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"steady:{keyword}")
    
    for keyword in transient_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"transient:{keyword}")
    
    # Special handling for "air" in multiphase context
    air_pattern = r"\bair\b"
    if re.search(air_pattern, prompt_lower):
        # Only include as multiphase if there's clear multiphase context
        # Include compound words like "underwater"
        other_fluids = [r"\bwater\b", r"water", r"\bliquid\b", r"liquid", r"\boil\b"]
        if any(re.search(fluid, prompt_lower) for fluid in other_fluids):
            found_keywords.append("multiphase:air")
    
    for keyword in multiphase_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"multiphase:{keyword}")
    
    for keyword in compressible_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"compressible:{keyword}")
    
    for keyword in heat_transfer_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"heat_transfer:{keyword}")
    
    for keyword in reactive_keywords:
        if re.search(keyword, prompt_lower):
            found_keywords.append(f"reactive:{keyword}")
    
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
    logger.info(f"  Mach Number: {features['mach_number']}")
    logger.info(f"  Analysis Type: {features['analysis_type']}")
    logger.info(f"  Expects Vortex Shedding: {features['expects_vortex_shedding']}")
    logger.info(f"  Is Multiphase: {features['is_multiphase']}")
    logger.info(f"  Is Compressible: {features['is_compressible']}")
    logger.info(f"  Has Heat Transfer: {features['has_heat_transfer']}")
    logger.info(f"  Has Reactive Flow: {features['has_reactive_flow']}")
    logger.info(f"  Is Multi-Region: {features['is_multi_region']}")
    logger.info(f"  Time Scale Interest: {features['time_scale_interest']}")
    logger.info(f"  Keywords: {features['user_keywords']}")
    
    # Decision logic with physics-based priority hierarchy
    
    # Priority 1: Most restrictive physics first - Reactive flows
    if features['has_reactive_flow']:
        logger.info("AI Decision: Reactive flow/combustion detected → reactingFoam")
        return SolverType.REACTING_FOAM
    
    # Priority 2: Multi-region heat transfer
    if features['is_multi_region'] and features['has_heat_transfer']:
        logger.info("AI Decision: Multi-region heat transfer detected → chtMultiRegionFoam")
        return SolverType.CHT_MULTI_REGION_FOAM
    
    # Priority 3: Multiphase
    if features['is_multiphase'] or features['free_surface']:
        # Check for incompatible requests
        if features['is_compressible'] and features.get('mach_number', 0) > 0.3:
            logger.warning("Compressible multiphase requested - this requires specialized solvers not currently supported")
            logger.info("AI Decision: Defaulting to interFoam for multiphase flow")
        else:
            logger.info("AI Decision: Multiphase flow detected → interFoam")
        return SolverType.INTER_FOAM
    
    # Priority 4: Compressible flow
    if features['is_compressible'] or (features.get('mach_number', 0) > 0.3):
        logger.info(f"AI Decision: Compressible flow (Mach={features.get('mach_number', 0):.2f}) → rhoPimpleFoam")
        return SolverType.RHO_PIMPLE_FOAM
    
    # Priority 3: Explicit steady-state request
    if features['analysis_type'] == AnalysisType.STEADY or features['time_scale_interest'] == "steady":
        # Validate that steady state is appropriate
        if features['expects_vortex_shedding']:
            logger.warning("Steady-state requested but vortex shedding expected - consider transient analysis")
        logger.info("AI Decision: Explicit steady-state request → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Priority 4: Low Reynolds number without vortex shedding
    if not features['expects_vortex_shedding'] and features.get('reynolds_number', 0) < 100:
        logger.info(f"AI Decision: Low Re={features.get('reynolds_number', 0)} without vortex shedding → simpleFoam")
        return SolverType.SIMPLE_FOAM
    
    # Priority 5: Keywords strongly suggesting steady state
    steady_keywords = ["pressure drop", "drag coefficient", "lift coefficient", "steady", "equilibrium"]
    if any(f"steady:{kw}" in features['user_keywords'] for kw in steady_keywords):
        if not features['expects_vortex_shedding']:
            logger.info("AI Decision: Steady-state keywords detected → simpleFoam")
            return SolverType.SIMPLE_FOAM
    
    # Priority 6: Vortex shedding or explicit transient request
    if features['expects_vortex_shedding'] or features['analysis_type'] == AnalysisType.UNSTEADY:
        logger.info("AI Decision: Vortex shedding expected or transient requested → pimpleFoam")
        return SolverType.PIMPLE_FOAM
    
    # Priority 7: Transient keywords
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
    reynolds_number = parsed_params.get("reynolds_number", None)
    
    # Determine analysis type based on solver
    if solver_type == SolverType.SIMPLE_FOAM:
        analysis_type = AnalysisType.STEADY
    else:
        # All other solvers are transient-capable, defaulting to UNSTEADY
        analysis_type = AnalysisType.UNSTEADY
    
    # Special case: interFoam is always transient
    if solver_type == SolverType.INTER_FOAM:
        analysis_type = AnalysisType.UNSTEADY
        if parsed_params.get("analysis_type") == AnalysisType.STEADY:
            logger.warning("interFoam does not support steady-state analysis, switching to transient")
    
    # Get solver info from registry
    solver_info = SOLVER_REGISTRY[solver_type]
    
    solver_settings = {
        "solver": solver_info["name"],
        "solver_type": solver_type,
        "flow_type": flow_type,
        "analysis_type": analysis_type,
        "reynolds_number": reynolds_number,
        "mach_number": parsed_params.get("mach_number", 0),
        "compressible": solver_info["capabilities"]["compressible"],
        "multiphase": solver_info["capabilities"]["multiphase"]
    }
    
    # Turbulence model selection
    if flow_type == FlowType.TURBULENT:
        # Special handling for compressible flows
        if solver_type == SolverType.RHO_PIMPLE_FOAM:
            mach_number = parsed_params.get("mach_number", 0)
            if mach_number > 1.0 or any("shock" in str(kw) for kw in parsed_params.get("keywords", [])):
                solver_settings["turbulence_model"] = "kOmegaSST"  # Better for shocks
            elif reynolds_number is not None and reynolds_number > 1e6:
                solver_settings["turbulence_model"] = "kEpsilon"
            else:
                solver_settings["turbulence_model"] = "kOmegaSST"
        else:
            # Standard turbulence model selection
            if reynolds_number is not None and reynolds_number < 10000:
                solver_settings["turbulence_model"] = "kOmegaSST"
            elif reynolds_number is not None and reynolds_number >= 10000:
                solver_settings["turbulence_model"] = "kEpsilon"
            else:
                solver_settings["turbulence_model"] = "kOmegaSST"
    else:
        solver_settings["turbulence_model"] = "laminar"
    
    # Add phase properties for multiphase solvers
    if solver_type == SolverType.INTER_FOAM:
        phases = parsed_params.get("phases", ["water", "air"])
        solver_settings["phases"] = phases
        solver_settings["phase_properties"] = {}
        for phase in phases:
            if phase in DEFAULT_PHASE_PROPERTIES:
                solver_settings["phase_properties"][phase] = DEFAULT_PHASE_PROPERTIES[phase].copy()
            else:
                # Use water properties as default for unknown fluids
                solver_settings["phase_properties"][phase] = DEFAULT_PHASE_PROPERTIES["water"].copy()
                logger.warning(f"Unknown phase '{phase}', using water properties as default")
        
        # Surface tension between phases
        if "water" in phases and "air" in phases:
            solver_settings["surface_tension"] = DEFAULT_PHASE_PROPERTIES["water"]["surface_tension"]
        else:
            solver_settings["surface_tension"] = 0.07  # Default surface tension
    
    # Add thermophysical properties for compressible solvers
    if solver_type == SolverType.RHO_PIMPLE_FOAM:
        solver_settings["thermophysical_model"] = "perfectGas"
        solver_settings["transport_model"] = "const"
        solver_settings["thermo_type"] = "hePsiThermo"
        solver_settings["mixture"] = "pureMixture"
        solver_settings["equation_of_state"] = "perfectGas"
        solver_settings["specie"] = "specie"
        solver_settings["energy"] = "sensibleInternalEnergy"
    
    # Add settings for chtMultiRegionFoam
    if solver_type == SolverType.CHT_MULTI_REGION_FOAM:
        solver_settings["multi_region"] = True
        solver_settings["regions"] = parsed_params.get("regions", ["fluid", "solid"])
        solver_settings["thermophysical_model"] = "perfectGas"
        solver_settings["transport_model"] = "const"
        solver_settings["thermo_type"] = "hePsiThermo"
        solver_settings["thermal_coupling"] = True
    
    # Add settings for reactingFoam
    if solver_type == SolverType.REACTING_FOAM:
        solver_settings["thermophysical_model"] = "psiReactionThermo"
        solver_settings["chemistry"] = True
        solver_settings["combustion_model"] = parsed_params.get("combustion_model", "PaSR")
        solver_settings["chemistry_solver"] = parsed_params.get("chemistry_solver", "ode")
        solver_settings["species"] = parsed_params.get("chemical_species", ["CH4", "O2", "CO2", "H2O", "N2"])
        solver_settings["reaction_mechanism"] = parsed_params.get("reaction_mechanism", "GRI-Mech3.0")
    
    return solver_settings


def select_solver(parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Select appropriate OpenFOAM solver based on flow conditions."""
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    # Default to transient (UNSTEADY) analysis unless explicitly specified as steady
    analysis_type = parsed_params.get("analysis_type", AnalysisType.UNSTEADY)
    compressible = parsed_params.get("compressible", False)
    heat_transfer = parsed_params.get("heat_transfer", False)
    reynolds_number = parsed_params.get("reynolds_number", None)
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


def generate_solver_config(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any], geometry_info: Dict[str, Any], state: Dict[str, Any] = None) -> Dict[str, Any]:
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
    
    # Add solver-specific configuration files
    if solver_settings.get("solver_type") == SolverType.INTER_FOAM:
        # Add multiphase-specific properties
        solver_config["g"] = {
            "dimensions": "[0 1 -2 0 0 0 0]",  # Acceleration dimensions
            "value": "(0 -9.81 0)"  # Gravity for free surface flows
        }
        solver_config["sigma"] = solver_settings.get("surface_tension", 0.07)
        solver_config["phases"] = solver_settings.get("phases", ["water", "air"])
        # Generate alpha.water boundary conditions based on U field
        u_field = state.get("boundary_conditions", {}).get("U", {}) if state else {}
        u_boundary_field = u_field.get("boundaryField", {})
        
        # Create alpha.water boundary conditions
        alpha_boundary_field = {}
        for patch_name, patch_config in u_boundary_field.items():
            if patch_name == "inlet":
                # For inlet, set alpha.water = 1 (pure water) or 0 (air only)
                # For water/air mixture, we'll start with air only and let water enter
                alpha_boundary_field[patch_name] = {
                    "type": "fixedValue",
                    "value": "uniform 0"  # Air only at inlet
                }
            elif patch_name == "outlet":
                alpha_boundary_field[patch_name] = {
                    "type": "zeroGradient"
                }
            elif patch_name == "walls":
                alpha_boundary_field[patch_name] = {
                    "type": "zeroGradient"
                }
            else:
                # Default for any other patches
                alpha_boundary_field[patch_name] = {
                    "type": "zeroGradient"
                }
        
        solver_config["alpha.water"] = {
            "dimensions": "[0 0 0 0 0 0 0]",  # Dimensionless volume fraction
            "internalField": "uniform 0",  # Start with air only
            "boundaryField": alpha_boundary_field
        }
        # Add p_rgh field for multiphase flows (instead of standard p)
        # Copy boundary conditions from standard p field if available
        p_field = state.get("boundary_conditions", {}).get("p", {}) if state else {}
        p_rgh_boundary_field = p_field.get("boundaryField", {})
        
        solver_config["p_rgh"] = {
            "dimensions": "[1 -1 -2 0 0 0 0]",  # Kinematic pressure for interFoam
            "internalField": "uniform 0",
            "boundaryField": p_rgh_boundary_field
        }
    
    if solver_settings.get("solver_type") == SolverType.RHO_PIMPLE_FOAM:
        # Add compressible flow properties
        solver_config["thermophysicalProperties"] = generate_thermophysical_properties(solver_settings, parsed_params)
        
        # Only generate temperature field if it doesn't already exist with proper boundary conditions
        if state and "boundary_conditions" in state and "T" in state["boundary_conditions"]:
            # Use existing temperature field from boundary condition agent (it has correct boundary conditions)
            existing_temp_field = state["boundary_conditions"]["T"]
            solver_config["T"] = {
                "dimensions": "[0 0 0 1 0 0 0]",  # Temperature in Kelvin
                "internalField": f"uniform {parsed_params.get('temperature', 293.15)}",  # Default 20°C
                "boundaryField": existing_temp_field["boundaryField"]
            }
        else:
            # Fallback - create basic temperature field (shouldn't happen with good boundary conditions)
            solver_config["T"] = {
                "dimensions": "[0 0 0 1 0 0 0]",  # Temperature in Kelvin
                "internalField": f"uniform {parsed_params.get('temperature', 293.15)}",  # Default 20°C
                "boundaryField": {}
            }
    
    if solver_settings.get("solver_type") == SolverType.CHT_MULTI_REGION_FOAM:
        # Add multi-region heat transfer properties
        regions = solver_settings.get("regions", ["fluid", "solid"])
        fluid_regions = [r for r in regions if "fluid" in r.lower()]
        solid_regions = [r for r in regions if "solid" in r.lower()]
        
        # Ensure we have at least one fluid and one solid region
        if not fluid_regions:
            fluid_regions = ["fluid"]
        if not solid_regions:
            solid_regions = ["solid"]
        
        solver_config["regionProperties"] = {
            "regions": fluid_regions + solid_regions,
            "fluidRegions": fluid_regions,
            "solidRegions": solid_regions
        }
        # Add thermophysical properties for each region
        solver_config["thermophysicalProperties"] = generate_thermophysical_properties(solver_settings, parsed_params)
        solver_config["fvOptions"] = {
            "energySource": {
                "type": "scalarSemiImplicitSource",
                "active": "true",
                "scalarSemiImplicitSourceCoeffs": {
                    "selectionMode": "all",
                    "volumeMode": "absolute",
                    "injectionRateSuSp": {
                        "h": (0, parsed_params.get("heat_source", 0))
                    }
                }
            }
        }
    
    if solver_settings.get("solver_type") == SolverType.REACTING_FOAM:
        # Add reactive flow properties
        solver_config["thermophysicalProperties"] = generate_reactive_thermophysical_properties(solver_settings, parsed_params)
        solver_config["chemistryProperties"] = {
            "chemistry": "on",
            "chemistryType": {
                "chemistrySolver": solver_settings.get("chemistry_solver", "ode"),
                "chemistryThermo": "psi"
            },
            "chemistryReader": "foamChemistryReader",
            "foamChemistryFile": f"constant/{solver_settings.get('reaction_mechanism', 'reactions')}"
        }
        solver_config["combustionProperties"] = {
            "combustionModel": solver_settings.get("combustion_model", "PaSR"),
            f"{solver_settings.get('combustion_model', 'PaSR')}Coeffs": {
                "Cmix": 0.1,
                "turbulentReaction": "on"
            }
        }
    
    return solver_config


def generate_control_dict(solver: str, analysis_type: AnalysisType, parsed_params: Dict[str, Any], geometry_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate controlDict configuration."""
    # Check if this is a transient solver
    if analysis_type == AnalysisType.UNSTEADY or "pimple" in solver.lower():
        # Calculate appropriate time step based on flow parameters
        velocity = parsed_params.get("velocity", None)
        
        # If velocity is not provided but Reynolds number is, calculate velocity
        if velocity is None and parsed_params.get("reynolds_number") is not None and parsed_params.get("reynolds_number") > 0:
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
        if "characteristic_length" in parsed_params and parsed_params["characteristic_length"] is not None and parsed_params["characteristic_length"] > 0:
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
            
            # Add interFoam-specific parameters
            if solver == "interFoam":
                control_dict["maxAlphaCo"] = 1.0  # Maximum alpha (VOF) Courant number
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
    solver_type = solver_settings.get("solver_type", SolverType.PIMPLE_FOAM)
    
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
        # interFoam only supports Euler and CrankNicolson schemes
        if solver_type == SolverType.INTER_FOAM:
            fv_schemes["ddtSchemes"]["default"] = "Euler"
        else:
            fv_schemes["ddtSchemes"]["default"] = "backward"
    
    # Solver-specific divergence schemes
    if solver_type == SolverType.INTER_FOAM:
        # interFoam specific schemes for VOF
        fv_schemes["divSchemes"].update({
            "div(rhoPhi,U)": "Gauss linearUpwind grad(U)",
            "div(phi,alpha)": "Gauss vanLeer",
            "div(phirb,alpha)": "Gauss interfaceCompression",
            "div(((rho*nuEff)*dev2(T(grad(U)))))": "Gauss linear"
        })
        # Add flux schemes for VOF
        fv_schemes["fluxRequired"] = {
            "default": "no",
            "p_rgh": "",
            "pcorr": "",
            "alpha.water": ""
        }
    elif solver_type == SolverType.RHO_PIMPLE_FOAM:
        # rhoPimpleFoam specific schemes for compressible flow
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "Gauss linearUpwindV grad(U)",
            "div(phi,K)": "Gauss upwind",
            "div(phi,h)": "Gauss upwind", 
            "div(phi,e)": "Gauss upwind",
            "div(phiv,p)": "Gauss upwind",
            "div(phi,k)": "Gauss upwind",
            "div(phi,omega)": "Gauss upwind",
            "div(phi,epsilon)": "Gauss upwind",
            "div(((rho*nuEff)*dev2(T(grad(U)))))": "Gauss linear"
        })
    elif solver_type == SolverType.CHT_MULTI_REGION_FOAM:
        # chtMultiRegionFoam specific schemes
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "Gauss linearUpwindV grad(U)",
            "div(phi,K)": "Gauss upwind",
            "div(phi,h)": "Gauss upwind",
            "div(phi,k)": "Gauss upwind",
            "div(phi,omega)": "Gauss upwind",
            "div(phi,epsilon)": "Gauss upwind",
            "div(((rho*nuEff)*dev2(T(grad(U)))))": "Gauss linear",
            "div(phid,p)": "Gauss upwind"
        })
    elif solver_type == SolverType.REACTING_FOAM:
        # reactingFoam specific schemes
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "Gauss linearUpwindV grad(U)",
            "div(phi,Yi_h)": "Gauss multivariateSelection { Yi limitedLinear01 1; h limitedLinear 1; }",
            "div(phi,K)": "Gauss upwind",
            "div(phi,k)": "Gauss upwind",
            "div(phi,omega)": "Gauss upwind",
            "div(phi,epsilon)": "Gauss upwind",
            "div(((rho*nuEff)*dev2(T(grad(U)))))": "Gauss linear",
            "div(phid,p)": "Gauss upwind"
        })
    else:
        # Standard incompressible schemes
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
    solver_type = solver_settings.get("solver_type", SolverType.PIMPLE_FOAM)
    
    # Base solution settings
    fv_solution = {
        "solvers": {},
        "SIMPLE": {},
        "PIMPLE": {},
        "relaxationFactors": {},
        "residualControl": {}
    }
    
    # Solver-specific pressure and velocity solvers
    if solver_type == SolverType.INTER_FOAM:
        # interFoam uses p_rgh (pressure minus hydrostatic component)
        fv_solution["solvers"]["p_rgh"] = {
            "solver": "PCG",
            "preconditioner": "DIC",
            "tolerance": 1e-08,
            "relTol": 0.01
        }
        fv_solution["solvers"]["p_rghFinal"] = {
            "solver": "PCG",
            "preconditioner": "DIC",
            "tolerance": 1e-08,
            "relTol": 0
        }
        # Add pressure correction solvers
        fv_solution["solvers"]["pcorr"] = {
            "solver": "PCG",
            "preconditioner": "DIC",
            "tolerance": 1e-08,
            "relTol": 0
        }
        fv_solution["solvers"]["pcorrFinal"] = {
            "solver": "PCG",
            "preconditioner": "DIC",
            "tolerance": 1e-08,
            "relTol": 0
        }
        # Add alpha.water solver
        fv_solution["solvers"]["alpha.water"] = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "nAlphaCorr": 2,
            "nAlphaSubCycles": 1,
            "cAlpha": 1.0,
            "tolerance": 1e-08,
            "relTol": 0
        }
    elif solver_type == SolverType.RHO_PIMPLE_FOAM:
        # rhoPimpleFoam pressure solver
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
        fv_solution["solvers"]["pFinal"] = fv_solution["solvers"]["p"].copy()
        fv_solution["solvers"]["pFinal"]["relTol"] = 0
        
        # Density solver for compressible flows
        fv_solution["solvers"]["rho"] = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0.1
        }
        fv_solution["solvers"]["rhoFinal"] = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0
        }
        
        # Energy equation solvers
        energy_solver = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0.1
        }
        fv_solution["solvers"]["e"] = energy_solver.copy()
        fv_solution["solvers"]["h"] = energy_solver.copy()
        fv_solution["solvers"]["eFinal"] = energy_solver.copy()
        fv_solution["solvers"]["eFinal"]["relTol"] = 0
        fv_solution["solvers"]["hFinal"] = energy_solver.copy()
        fv_solution["solvers"]["hFinal"]["relTol"] = 0
    elif solver_type == SolverType.CHT_MULTI_REGION_FOAM:
        # chtMultiRegionFoam pressure and energy solvers
        fv_solution["solvers"]["p_rgh"] = {
            "solver": "GAMG",
            "tolerance": 1e-06,
            "relTol": 0.01,
            "smoother": "GaussSeidel",
            "nPreSweeps": 0,
            "nPostSweeps": 2,
            "cacheAgglomeration": "true",
            "nCellsInCoarsestLevel": 10,
            "agglomerator": "faceAreaPair",
            "mergeLevels": 1
        }
        fv_solution["solvers"]["p_rghFinal"] = fv_solution["solvers"]["p_rgh"].copy()
        fv_solution["solvers"]["p_rghFinal"]["relTol"] = 0
        
        # Energy equation solvers for multi-region
        energy_solver = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0.1
        }
        fv_solution["solvers"]["h"] = energy_solver.copy()
        fv_solution["solvers"]["hFinal"] = energy_solver.copy()
        fv_solution["solvers"]["hFinal"]["relTol"] = 0
    elif solver_type == SolverType.REACTING_FOAM:
        # reactingFoam pressure solver
        fv_solution["solvers"]["p"] = {
            "solver": "PCG",
            "preconditioner": "DIC",
            "tolerance": 1e-06,
            "relTol": 0.01
        }
        fv_solution["solvers"]["pFinal"] = fv_solution["solvers"]["p"].copy()
        fv_solution["solvers"]["pFinal"]["relTol"] = 0
        
        # Species and energy solvers
        species_solver = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0
        }
        fv_solution["solvers"]["Yi"] = species_solver.copy()
        fv_solution["solvers"]["h"] = species_solver.copy()
        fv_solution["solvers"]["hs"] = species_solver.copy()
        
        # Chemistry solver settings
        fv_solution["chemistry"] = {
            "solver": "ode",
            "eps": 0.01,
            "scale": 1
        }
    else:
        # Standard pressure solver for incompressible flows
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
    
    # Velocity solver (common for all)
    fv_solution["solvers"]["U"] = {
        "solver": "smoothSolver",
        "smoother": "GaussSeidel",
        "tolerance": 1e-05,
        "relTol": 0.1
    }
    
    # For PIMPLE-based solvers, we need UFinal as well
    if analysis_type == AnalysisType.UNSTEADY or solver_type in [SolverType.PIMPLE_FOAM, SolverType.INTER_FOAM, SolverType.RHO_PIMPLE_FOAM]:
        fv_solution["solvers"]["UFinal"] = {
            "solver": "smoothSolver",
            "smoother": "GaussSeidel",
            "tolerance": 1e-06,
            "relTol": 0
        }
        if solver_type != SolverType.INTER_FOAM and "pFinal" not in fv_solution["solvers"]:
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
        if analysis_type == AnalysisType.UNSTEADY or solver_type in [SolverType.PIMPLE_FOAM, SolverType.INTER_FOAM, SolverType.RHO_PIMPLE_FOAM]:
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
    if analysis_type == AnalysisType.STEADY and solver_type == SolverType.SIMPLE_FOAM:
        # ... existing SIMPLE settings ...
        # Adjust SIMPLE settings based on Reynolds number
        reynolds_number = parsed_params.get("reynolds_number", 1000)
        
        # Low Re flows might need more correctors
        if reynolds_number is not None and reynolds_number < 100:
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
        reynolds_number = parsed_params.get("reynolds_number", None)
        
        if reynolds_number is not None and reynolds_number < 100:  # Very low Re flows need more relaxation
            p_relax = 0.1
            u_relax = 0.3
            turb_relax = 0.3
            logger.info(f"Using conservative relaxation factors for low Re={reynolds_number}: p={p_relax}, U={u_relax}")
        elif reynolds_number is not None and reynolds_number < 1000:  # Moderate Re
            p_relax = 0.2
            u_relax = 0.5
            turb_relax = 0.5
        else:  # Higher Re or unknown
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
        # Transient PIMPLE settings
        if solver_type == SolverType.INTER_FOAM:
            # interFoam specific settings
            fv_solution["PIMPLE"] = {
                "momentumPredictor": "no",
                "nOuterCorrectors": 1,
                "nCorrectors": 3,
                "nNonOrthogonalCorrectors": 0,
                "pRefCell": 0,
                "pRefValue": 0
            }
        elif solver_type == SolverType.RHO_PIMPLE_FOAM:
            # rhoPimpleFoam specific settings
            fv_solution["PIMPLE"] = {
                "nOuterCorrectors": 2,
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 1,
                "transonic": "yes" if (parsed_params.get("mach_number") or 0) > 0.8 else "no"
            }
        elif solver_type == SolverType.CHT_MULTI_REGION_FOAM:
            # chtMultiRegionFoam specific settings
            fv_solution["PIMPLE"] = {
                "nOuterCorrectors": 1,
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 1
            }
        elif solver_type == SolverType.REACTING_FOAM:
            # reactingFoam specific settings
            fv_solution["PIMPLE"] = {
                "nOuterCorrectors": 1,
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 1,
                "momentumPredictor": "yes"
            }
        else:
            # Standard PIMPLE settings
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
    solver_type = solver_settings.get("solver_type", SolverType.PIMPLE_FOAM)
    
    if solver_type == SolverType.INTER_FOAM:
        # Multiphase transport properties for interFoam
        phases = solver_settings.get("phases", ["water", "air"])
        phase_properties = solver_settings.get("phase_properties", {})
        
        transport_props = {
            "phases": phases,
            "sigma": solver_settings.get("surface_tension", 0.07)
        }
        
        # Add properties for each phase
        for phase in phases:
            if phase in phase_properties:
                props = phase_properties[phase]
                transport_props[phase] = {
                    "transportModel": "Newtonian",
                    "nu": props.get("viscosity", 1e-6) / props.get("density", 1000),
                    "rho": props.get("density", 1000)
                }
            else:
                # Default properties
                transport_props[phase] = {
                    "transportModel": "Newtonian",
                    "nu": 1e-6,  # Default kinematic viscosity
                    "rho": 1000  # Default density
                }
        
        return transport_props
    else:
        # Standard single-phase transport properties
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


def generate_thermophysical_properties(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate thermophysicalProperties file for compressible solvers."""
    # Default temperature and pressure if not specified
    temperature = parsed_params.get("temperature", 293.15)  # 20°C in Kelvin
    pressure = parsed_params.get("pressure", 101325)  # 1 atm in Pa
    
    # Gas properties (default to air)
    cp = parsed_params.get("specific_heat", 1005)  # J/(kg·K) for air
    cv = cp / 1.4  # Assuming gamma = 1.4 for air
    mol_weight = parsed_params.get("molecular_weight", 28.96)  # g/mol for air
    
    # Transport properties
    mu = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
    pr = parsed_params.get("prandtl_number", 0.72)  # Prandtl number for air
    
    return {
        "thermoType": {
            "type": solver_settings.get("thermo_type", "hePsiThermo"),
            "mixture": solver_settings.get("mixture", "pureMixture"),
            "transport": solver_settings.get("transport_model", "const"),
            "thermo": "hConst",
            "equationOfState": solver_settings.get("equation_of_state", "perfectGas"),
            "specie": solver_settings.get("specie", "specie"),
            "energy": solver_settings.get("energy", "sensibleInternalEnergy")
        },
        "mixture": {
            "specie": {
                "nMoles": 1,
                "molWeight": mol_weight
            },
            "thermodynamics": {
                "Cp": cp,
                "Hf": 0
            },
            "transport": {
                "mu": mu,
                "Pr": pr
            }
        }
    }


def generate_reactive_thermophysical_properties(solver_settings: Dict[str, Any], parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate thermophysicalProperties file for reactive flow solvers."""
    # Default temperature and pressure if not specified
    temperature = parsed_params.get("temperature", 300)  # 300K for combustion
    pressure = parsed_params.get("pressure", 101325)  # 1 atm in Pa
    
    # Get species list
    species = solver_settings.get("species", ["CH4", "O2", "CO2", "H2O", "N2"])
    
    return {
        "thermoType": {
            "type": "hePsiThermo",
            "mixture": "reactingMixture",
            "transport": "sutherland",
            "thermo": "janaf",
            "energy": "sensibleEnthalpy",
            "equationOfState": "perfectGas",
            "specie": "specie"
        },
        "chemistryReader": "foamChemistryReader",
        "inertSpecie": "N2",
        "fuel": solver_settings.get("fuel", "CH4"),
        "species": species,
        "defaultSpecie": {
            "specie": {
                "nMoles": 1,
                "molWeight": 28.96  # Average for air
            }
        },
        "reactions": {}  # Will be populated from reaction mechanism file
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
    elif solver not in ["simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam", "interFoam", 
                        "chtMultiRegionFoam", "reactingFoam"]:
        warnings.append(f"Unknown solver: {solver}")
    
    # Solver-specific validation
    if solver == "interFoam":
        # Check for required multiphase properties
        if "g" not in solver_config:
            warnings.append("Gravity vector 'g' not specified for interFoam")
        if "sigma" not in solver_config:
            warnings.append("Surface tension 'sigma' not specified for interFoam")
        if "phases" not in solver_config or len(solver_config.get("phases", [])) < 2:
            errors.append("interFoam requires at least 2 phases")
        # interFoam cannot be steady state
        if solver_config.get("analysis_type") == AnalysisType.STEADY:
            errors.append("interFoam does not support steady-state analysis")
    
    elif solver == "rhoPimpleFoam":
        # Check for required compressible properties
        if "thermophysicalProperties" not in solver_config:
            errors.append("Missing thermophysicalProperties for compressible solver")
        if "T" not in solver_config:
            warnings.append("Temperature field 'T' not initialized for rhoPimpleFoam")
        # Check Mach number
        mach_number = parsed_params.get("mach_number", 0)
        if mach_number is not None and isinstance(mach_number, (int, float)) and mach_number < 0.3:
            warnings.append(f"Low Mach number ({mach_number:.2f}) - consider using incompressible solver")
    
    elif solver == "chtMultiRegionFoam":
        # Check for required multi-region properties
        if "regionProperties" not in solver_config:
            errors.append("Missing regionProperties for chtMultiRegionFoam")
        else:
            regions = solver_config.get("regionProperties", {}).get("regions", [])
            if len(regions) < 2:
                errors.append("chtMultiRegionFoam requires at least 2 regions (fluid and solid)")
        if "thermophysicalProperties" not in solver_config:
            errors.append("Missing thermophysicalProperties for chtMultiRegionFoam")
    
    elif solver == "reactingFoam":
        # Check for required reactive flow properties
        if "thermophysicalProperties" not in solver_config:
            errors.append("Missing thermophysicalProperties for reactingFoam")
        if "chemistryProperties" not in solver_config:
            errors.append("Missing chemistryProperties for reactingFoam")
        if "combustionProperties" not in solver_config:
            warnings.append("Missing combustionProperties for reactingFoam - will use default combustion model")
        # reactingFoam is always transient
        if solver_config.get("analysis_type") == AnalysisType.STEADY:
            errors.append("reactingFoam does not support steady-state analysis")
    
    # Check time step for transient simulations
    if solver and ("pimple" in solver.lower() or solver in ["interFoam", "chtMultiRegionFoam", "reactingFoam"]):
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
        if reynolds_number is not None and reynolds_number < 10000:
            recommendations.append("k-omega SST model recommended for low Re turbulence")
        else:
            recommendations.append("k-epsilon model suitable for high Re turbulence")
    
    return recommendations 
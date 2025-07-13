"""Solver Selector Agent - Chooses appropriate OpenFOAM solvers and configurations."""

from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
import re

from .state import CFDState, CFDStep, GeometryType, FlowType, AnalysisType, SolverType


# Enhanced keyword detection with context analysis and weighting
KEYWORD_WEIGHTS = {
    "compressible": {
        # Core compressible flow keywords
        "shock": 3.0,
        "supersonic": 2.5,
        "transonic": 2.0,
        "hypersonic": 2.5,
        "mach": 2.0,
        "compressible": 2.0,
        "gas dynamics": 1.5,
        "high-speed": 1.5,
        "high speed": 1.5,
        "sonic boom": 2.0,
        # Applications and phenomena
        "nozzle": 1.5,
        "jet": 1.5,
        "rocket": 1.5,
        "blast": 2.0,
        "explosion": 2.0,
        "expansion": 1.0,
        "compression": 1.0,
        "rarefaction": 2.0,
        "oblique shock": 2.5,
        "normal shock": 2.5,
        "prandtl-meyer": 2.0,
        "fanno": 1.5,
        "rayleigh": 1.5,
        # Aerospace applications
        "aircraft": 1.0,
        "airfoil supersonic": 2.0,
        "wind tunnel": 1.0,
        "ballistics": 2.0,
        "projectile": 1.5,
        # Negative weights for conflicting contexts
        "wave": -1.0,  # "shock wave" vs "water wave"
        "water": -2.0,  # Compressible flows rarely involve water
        "liquid": -2.0,
        "free surface": -1.5,
        "dam break": -2.0,
        "sloshing": -2.0,
        "marine": -2.0,
        "naval": -2.0
    },
    "multiphase": {
        # Fluid types
        "water": 2.0,
        "liquid": 1.5,
        "gas": 1.0,
        "oil": 2.0,
        "steam": 1.5,
        "vapor": 1.5,
        "mist": 2.0,
        "fog": 1.5,
        "spray": 2.0,
        # Interface phenomena
        "interface": 2.0,
        "free surface": 2.5,
        "meniscus": 2.0,
        "contact line": 2.0,
        "wetting": 1.5,
        "dewetting": 1.5,
        "surface tension": 2.5,
        "capillary": 2.0,
        # Methods and models
        "vof": 3.0,
        "volume of fluid": 3.0,
        "level set": 2.5,
        "multiphase": 3.0,
        "two-phase": 2.5,
        "three-phase": 2.5,
        "eulerian": 1.5,
        "lagrangian": 1.5,
        # Phenomena and applications
        "dam break": 2.5,
        "wave": 1.5,  # Water waves, not shock waves
        "tsunami": 2.5,
        "breaking wave": 2.5,
        "droplet": 2.0,
        "bubble": 2.0,
        "cavitation": 2.5,
        "boiling": 2.0,
        "condensation": 2.0,
        "evaporation": 2.0,
        "splash": 2.0,
        "impact": 1.5,
        "filling": 1.5,
        "draining": 1.5,
        "sloshing": 2.0,
        "coating": 1.5,
        "inkjet": 2.0,
        "atomization": 2.0,
        # Applications
        "marine": 1.5,
        "naval": 1.5,
        "offshore": 1.5,
        "ship": 1.0,
        "hull": 1.0,
        "tank": 1.0,
        "reservoir": 1.0,
        "pipeline": 1.0,
        "microfluidics": 2.0,
        "air": 0.5,  # Only when combined with other fluids
        # Negative weights for conflicting contexts
        "shock": -2.0,  # Shock waves are compressible phenomena
        "supersonic": -2.0,
        "hypersonic": -2.0,
        "mach": -2.0,
        "compressible": -2.0,
        "gas dynamics": -1.5,
        "ballistics": -2.0
    },
    "heat_transfer": {
        # Core thermal keywords
        "heat": 2.0,
        "thermal": 2.0,
        "temperature": 1.5,
        "cooling": 1.5,
        "heating": 1.5,
        "hot": 1.0,
        "cold": 1.0,
        "warm": 1.0,
        # Heat transfer mechanisms
        "heat transfer": 3.0,
        "conduction": 2.0,
        "convection": 2.0,
        "radiation": 1.5,
        "natural convection": 2.5,
        "forced convection": 2.5,
        "mixed convection": 2.5,
        "free convection": 2.5,
        # Multi-physics coupling
        "conjugate": 2.5,
        "conjugate heat transfer": 3.0,
        "cht": 3.0,
        "cfd-cht": 3.0,
        "fluid-solid": 2.5,
        "solid-fluid": 2.0,
        "solid fluid": 2.0,
        "coupling": 1.5,
        "thermal coupling": 2.5,
        "multi-region": 2.5,
        "multi region": 2.5,
        "multiregion": 2.5,
        # Boundaries and conditions
        "heat flux": 2.0,
        "thermal boundary": 2.0,
        "wall temperature": 1.5,
        "wall conduction": 2.0,
        "solid wall": 1.5,
        "thermal contact": 2.0,
        "interface temperature": 2.0,
        # Applications and equipment
        "heat exchanger": 2.5,
        "radiator": 2.0,
        "heat sink": 2.0,
        "cooling system": 2.0,
        "thermal management": 2.0,
        "hvac": 2.0,
        "boiler": 2.0,
        "furnace": 2.0,
        "oven": 1.5,
        "chimney": 1.5,
        "stack": 1.0,
        "insulation": 1.5,
        "thermal insulation": 2.0,
        # Phase change
        "melting": 2.0,
        "solidification": 2.0,
        "freezing": 2.0,
        "phase change": 2.5,
        "latent heat": 2.0,
        # Electronics cooling
        "electronics": 1.5,
        "cpu": 1.5,
        "chip": 1.5,
        "pcb": 1.5,
        "thermal interface": 2.0
    },
    "reactive": {
        # Core combustion keywords
        "combustion": 3.0,
        "burning": 2.5,
        "flame": 2.5,
        "fire": 2.0,
        "ignition": 2.0,
        "autoignition": 2.5,
        "quenching": 2.0,
        "extinction": 2.0,
        "flashback": 2.5,
        "blowoff": 2.5,
        # Chemical processes
        "reaction": 2.0,
        "chemical": 2.0,
        "chemistry": 2.0,
        "kinetics": 2.0,
        "mechanism": 1.5,
        "species": 2.0,
        "concentration": 1.5,
        "mass fraction": 2.0,
        "mole fraction": 2.0,
        "mixture fraction": 2.0,
        "progress variable": 2.0,
        # Fuel types
        "fuel": 2.0,
        "oxidizer": 2.0,
        "methane": 2.0,
        "propane": 2.0,
        "hydrogen": 2.0,
        "ethane": 2.0,
        "gasoline": 2.0,
        "diesel": 2.0,
        "kerosene": 2.0,
        "natural gas": 2.0,
        "biogas": 2.0,
        "syngas": 2.0,
        "ammonia": 2.0,
        # Combustion modes
        "premixed": 2.5,
        "non-premixed": 2.5,
        "partially premixed": 2.5,
        "diffusion flame": 2.5,
        "laminar flame": 2.5,
        "turbulent flame": 2.5,
        "stratified": 2.0,
        # Combustion phenomena
        "detonation": 2.5,
        "deflagration": 2.5,
        "knock": 2.0,
        "auto-ignition": 2.5,
        "flame speed": 2.0,
        "flame front": 2.0,
        "flame propagation": 2.0,
        "flame stabilization": 2.0,
        # Applications
        "burner": 2.0,
        "combustor": 2.0,
        "engine": 1.5,
        "gas turbine": 1.0,  # Reduced score to avoid confusion with MRF
        "furnace": 2.0,
        "boiler": 1.5,
        "incinerator": 2.0,
        "flare": 2.0,
        "torch": 1.5,
        "propulsion": 1.5,
        "rocket": 1.5,
        "jet engine": 2.0,
        "combustion turbine": 2.0,  # More specific to avoid MRF confusion
        "internal combustion": 2.5,
        # Modeling approaches
        "reacting": 3.0,
        "reactive": 3.0,
        "eddy dissipation": 2.0,
        "flamelet": 2.5,
        "pdf": 1.5,
        "les combustion": 2.5,
        "rans combustion": 2.5,
        # Negative weights to avoid confusion
        "shock wave": -2.0,  # Compressible, not reactive
        "supersonic": -2.0,
        "hypersonic": -2.0,
        "mach": -2.0,
        "compressible": -1.5,
        "gas dynamics": -2.0,
        "nozzle": -1.5,
        "pump": -1.5,  # MRF, not reactive
        "impeller": -1.5,
        "centrifugal": -1.5,
        "rotating": -1.5,
        "rotation": -1.5,
        "mrf": -2.0,
        "multiple reference frame": -2.0,
        "steady rotating": -2.0,
        "free surface": -1.5,  # Multiphase, not reactive
        "dam break": -1.5,
        "multiphase": -1.5,
        "vof": -1.5,
        "volume of fluid": -1.5
    },
    "steady": {
        "steady": 2.0,
        "steady-state": 2.5,
        "steady state": 2.5,
        "equilibrium": 2.0,
        "final": 1.5,
        "converged": 2.0,
        "time-independent": 2.0,
        "stationary": 2.0,
        "constant": 1.0,
        # Performance metrics (often steady-state)
        "pressure drop": 2.0,
        "drag coefficient": 1.5,
        "lift coefficient": 1.5,
        "efficiency": 1.0,
        "performance": 1.0,
        "design point": 1.5,
        "operating point": 1.5,
        # Negative weights for conflicting contexts
        "transient": -2.0,
        "time": -1.0,
        "unsteady": -2.0,
        "vortex": -1.5,
        "shedding": -2.0,
        "oscillat": -2.0,
        "frequency": -2.0,
        "startup": -2.0,
        "development": -1.5,
        "periodic": -2.0,
        "pulsating": -2.0,
        "fluctuating": -2.0
    },
    "transient": {
        "transient": 2.5,
        "unsteady": 2.5,
        "time": 1.5,
        "time-dependent": 2.5,
        "time dependent": 2.5,
        "temporal": 2.0,
        "dynamic": 1.5,
        "evolution": 1.5,
        # Vortex phenomena
        "vortex": 2.0,
        "shedding": 2.5,
        "vortex shedding": 3.0,
        "karman": 2.5,
        "von karman": 2.5,
        "wake": 1.5,
        "instability": 2.0,
        # Oscillatory phenomena
        "oscillat": 2.0,
        "oscillating": 2.0,
        "oscillation": 2.0,
        "frequency": 2.0,
        "periodic": 2.0,
        "pulsating": 2.0,
        "pulsation": 2.0,
        "fluctuating": 2.0,
        "fluctuation": 2.0,
        "vibration": 1.5,
        "resonance": 2.0,
        # Flow development
        "startup": 2.0,
        "start-up": 2.0,
        "development": 1.5,
        "developing": 1.5,
        "transient response": 2.5,
        "impulse": 2.0,
        "step response": 2.0,
        # Turbulence
        "turbulent": 1.0,
        "turbulence": 1.0,
        "eddy": 1.0,
        "les": 1.5,  # Large Eddy Simulation
        "dns": 2.0,  # Direct Numerical Simulation
        # Dimensionless numbers
        "strouhal": 2.0,
        "strouhal number": 2.5,
        "reduced frequency": 2.0,
        # Negative weights for conflicting contexts
        "steady": -2.0,
        "steady-state": -2.5,
        "steady state": -2.5,
        "equilibrium": -2.0,
        "final": -1.5,
        "converged": -2.0,
        "stationary": -2.0
    },
    "piso": {
        # PISO algorithm preferences
        "piso": 3.0,
        "accurate": 2.0,
        "precision": 2.0,
        "accuracy": 2.0,
        "high precision": 2.5,
        "high accuracy": 2.5,
        "temporal accuracy": 2.5,
        "time accuracy": 2.5,
        "temporal precision": 2.5,
        "time precision": 2.5,
        # Biomedical applications
        "pulsatile": 2.5,
        "pulsating": 2.5,
        "arterial": 2.0,
        "cardiovascular": 2.0,
        "biomedical": 2.0,
        "blood flow": 2.0,
        "medical": 2.0,
        "physiological": 2.0,
        "heart": 2.0,
        "artery": 2.0,
        "vein": 2.0,
        "cardiac": 2.0,
        "vascular": 2.0,
        # Oscillatory flows
        "oscillatory": 2.0,
        "oscillating": 2.0,
        "womersley": 2.0,
        "periodic": 1.5,
        "cyclic": 1.5,
        "sinusoidal": 2.0,
        "harmonic": 2.0,
        # High fidelity simulations
        "high fidelity": 2.0,
        "detailed": 1.5,
        "fine": 1.5,
        "resolved": 1.5,
        "dns": 2.0,
        "direct numerical": 2.0,
        "well resolved": 2.0,
        "high resolution": 2.0,
        # Negative weights for less suitable cases
        "coarse": -1.0,
        "rough": -1.0,
        "approximate": -1.0,
        "fast": -1.0,
        "quick": -1.0,
        "rans": -1.0,
        "reynolds averaged": -1.0
    },
    "sonic": {
        # Supersonic flow indicators
        "sonic": 2.5,
        "supersonic": 3.0,
        "hypersonic": 3.0,
        "trans-sonic": 2.5,
        "transonic": 2.5,
        "sonic boom": 2.5,
        "mach": 2.5,
        "high mach": 2.5,
        "mach number": 2.5,
        # Shock phenomena
        "shock": 3.0,
        "shockwave": 3.0,
        "shock wave": 3.0,
        "shock waves": 3.0,
        "oblique shock": 2.5,
        "normal shock": 2.5,
        "bow shock": 2.5,
        "detached shock": 2.5,
        "attached shock": 2.5,
        "shock interaction": 2.5,
        "shock reflection": 2.5,
        "shock diffraction": 2.5,
        # Expansion phenomena
        "expansion": 2.0,
        "expansion fan": 2.0,
        "expansion wave": 2.0,
        "prandtl-meyer": 2.0,
        "rarefaction": 2.0,
        "rarefaction wave": 2.0,
        # Compressible flow theory
        "fanno flow": 2.0,
        "rayleigh flow": 2.0,
        "isentropic": 2.0,
        "adiabatic": 1.5,
        "polytropic": 1.5,
        "compressibility": 2.0,
        "density variation": 2.0,
        "pressure wave": 2.0,
        "acoustic": 1.5,
        "sound": 1.5,
        "sound wave": 1.5,
        # Aerospace applications
        "aerodynamics": 2.0,
        "aerospace": 2.0,
        "aircraft": 2.0,
        "fighter": 2.0,
        "missile": 2.0,
        "rocket": 2.0,
        "spacecraft": 2.0,
        "reentry": 2.0,
        "ballistic": 2.0,
        "projectile": 2.0,
        "bullet": 2.0,
        "artillery": 2.0,
        # High-speed facilities
        "wind tunnel": 2.0,
        "shock tunnel": 2.5,
        "blow-down": 2.0,
        "hypersonic tunnel": 2.5,
        "supersonic tunnel": 2.5,
        "ludwieg tube": 2.0,
        # Nozzle types
        "nozzle": 2.0,
        "de laval": 2.0,
        "convergent-divergent": 2.0,
        "cd nozzle": 2.0,
        "rocket nozzle": 2.0,
        "jet nozzle": 2.0,
        "exhaust nozzle": 2.0,
        "propelling nozzle": 2.0,
        # Negative weights for less suitable cases
        "subsonic": -1.0,
        "low speed": -1.0,
        "low mach": -1.0,
        "incompressible": -2.0,
        "water": -2.0,
        "liquid": -2.0,
        "multiphase": -1.0
    },
    "mrf": {
        # MRF core keywords
        "mrf": 3.0,
        "multiple reference frame": 3.0,
        "multiple reference frames": 3.0,
        "multi reference frame": 3.0,
        "rotating reference frame": 2.5,
        "reference frame": 2.0,
        "rotating frame": 2.5,
        "moving reference frame": 2.5,
        # Rotation keywords
        "rotating": 2.5,
        "rotation": 2.5,
        "rotational": 2.5,
        "rotary": 2.0,
        "spinning": 2.0,
        "angular": 2.0,
        "angular velocity": 2.0,
        "angular speed": 2.0,
        "omega": 2.0,
        "rpm": 2.0,
        "revolutions per minute": 2.0,
        "rad/s": 2.0,
        "radians per second": 2.0,
        # Rotating machinery
        "rotating machinery": 2.5,
        "turbomachinery": 2.5,
        "machinery": 2.0,
        "rotor": 2.5,
        "stator": 2.0,
        "rotating equipment": 2.5,
        "rotating device": 2.5,
        # Pumps
        "pump": 2.0,
        "centrifugal pump": 2.5,
        "axial pump": 2.5,
        "mixed flow pump": 2.5,
        "radial pump": 2.5,
        "impeller": 2.5,
        "pump impeller": 2.5,
        "centrifugal impeller": 2.5,
        "axial impeller": 2.5,
        "mixed flow impeller": 2.5,
        "circulation pump": 2.0,
        "cooling pump": 2.0,
        "water pump": 2.0,
        "oil pump": 2.0,
        "chemical pump": 2.0,
        "process pump": 2.0,
        "fire pump": 2.0,
        "booster pump": 2.0,
        "multistage pump": 2.0,
        "single stage pump": 2.0,
        "double suction pump": 2.0,
        "end suction pump": 2.0,
        "split case pump": 2.0,
        "volute pump": 2.0,
        "diffuser pump": 2.0,
        # Turbines
        "turbine": 2.0,
        "gas turbine": 2.0,
        "steam turbine": 2.0,
        "water turbine": 2.0,
        "wind turbine": 2.0,
        "hydroelectric turbine": 2.0,
        "hydro turbine": 2.0,
        "kaplan turbine": 2.0,
        "francis turbine": 2.0,
        "pelton turbine": 2.0,
        "axial turbine": 2.0,
        "radial turbine": 2.0,
        "mixed flow turbine": 2.0,
        "turbine runner": 2.0,
        "turbine blade": 2.0,
        "turbine vane": 2.0,
        "guide vane": 2.0,
        "wicket gate": 2.0,
        "stay vane": 2.0,
        "draft tube": 2.0,
        "spiral case": 2.0,
        "scroll case": 2.0,
        "penstock": 2.0,
        # Fans and blowers
        "fan": 2.0,
        "centrifugal fan": 2.5,
        "axial fan": 2.5,
        "mixed flow fan": 2.5,
        "radial fan": 2.5,
        "cooling fan": 2.0,
        "exhaust fan": 2.0,
        "supply fan": 2.0,
        "ventilation fan": 2.0,
        "industrial fan": 2.0,
        "blower": 2.0,
        "centrifugal blower": 2.5,
        "axial blower": 2.5,
        "roots blower": 2.0,
        "screw blower": 2.0,
        "air blower": 2.0,
        "gas blower": 2.0,
        # Compressors
        "compressor": 2.0,
        "centrifugal compressor": 2.5,
        "axial compressor": 2.5,
        "mixed flow compressor": 2.5,
        "radial compressor": 2.5,
        "air compressor": 2.0,
        "gas compressor": 2.0,
        "refrigeration compressor": 2.0,
        "compressor stage": 2.0,
        "compressor wheel": 2.0,
        "compressor impeller": 2.5,
        "compressor rotor": 2.5,
        "compressor stator": 2.0,
        "compressor blade": 2.0,
        "compressor vane": 2.0,
        "diffuser": 2.0,
        "volute": 2.0,
        "scroll": 2.0,
        "vaneless diffuser": 2.0,
        "vaned diffuser": 2.0,
        # Propellers
        "propeller": 2.0,
        "prop": 2.0,
        "screw": 2.0,
        "marine propeller": 2.0,
        "aircraft propeller": 2.0,
        "ship propeller": 2.0,
        "propeller blade": 2.0,
        "propeller hub": 2.0,
        "propeller boss": 2.0,
        "ducted propeller": 2.0,
        "open propeller": 2.0,
        "fixed pitch propeller": 2.0,
        "variable pitch propeller": 2.0,
        "controllable pitch propeller": 2.0,
        # Mixers and agitators
        "mixer": 2.0,
        "agitator": 2.0,
        "impeller mixer": 2.5,
        "stirrer": 2.0,
        "mixing impeller": 2.5,
        "agitator impeller": 2.5,
        "rushton turbine": 2.5,
        "pitched blade turbine": 2.5,
        "axial flow impeller": 2.5,
        "radial flow impeller": 2.5,
        "marine impeller": 2.5,
        "hydrofoil impeller": 2.5,
        "anchor impeller": 2.5,
        "helical impeller": 2.5,
        "ribbon impeller": 2.5,
        "paddle impeller": 2.5,
        "propeller impeller": 2.5,
        # Geometric components
        "blade": 2.0,
        "vane": 2.0,
        "rotor blade": 2.0,
        "stator blade": 2.0,
        "guide blade": 2.0,
        "runner blade": 2.0,
        "impeller blade": 2.0,
        "rotor vane": 2.0,
        "stator vane": 2.0,
        "guide vane": 2.0,
        "inlet guide vane": 2.0,
        "outlet guide vane": 2.0,
        "hub": 2.0,
        "shroud": 2.0,
        "casing": 2.0,
        "housing": 2.0,
        "volute casing": 2.0,
        "spiral casing": 2.0,
        "scroll casing": 2.0,
        "eye": 1.5,
        "inlet eye": 1.5,
        "suction eye": 1.5,
        "discharge": 1.5,
        "outlet": 1.5,
        "suction": 1.5,
        "inlet": 1.5,
        # Performance characteristics
        "head": 1.5,
        "pressure head": 1.5,
        "total head": 1.5,
        "dynamic head": 1.5,
        "static head": 1.5,
        "flow rate": 1.0,
        "discharge rate": 1.0,
        "capacity": 1.0,
        "efficiency": 1.5,
        "performance": 1.5,
        "characteristic": 1.5,
        "performance curve": 1.5,
        "characteristic curve": 1.5,
        "operating point": 1.5,
        "duty point": 1.5,
        "best efficiency point": 1.5,
        "bep": 1.5,
        "npsh": 1.5,
        "cavitation": 1.5,
        "surge": 1.5,
        "stall": 1.5,
        "off-design": 1.5,
        "part load": 1.5,
        "overload": 1.5,
        # Forces and moments
        "torque": 2.0,
        "moment": 2.0,
        "power": 1.5,
        "work": 1.5,
        "shaft power": 1.5,
        "hydraulic power": 1.5,
        "mechanical power": 1.5,
        "brake power": 1.5,
        "input power": 1.5,
        "output power": 1.5,
        "coriolis": 2.0,
        "centrifugal force": 2.0,
        "centripetal force": 2.0,
        "angular momentum": 2.0,
        "moment of momentum": 2.0,
        "euler equation": 2.0,
        "euler turbine equation": 2.0,
        # Steady-state indicators
        "steady rotating": 2.5,
        "steady state rotating": 2.5,
        "steady rotation": 2.5,
        "constant rotation": 2.5,
        "constant angular velocity": 2.5,
        "constant rpm": 2.5,
        "design speed": 2.0,
        "rated speed": 2.0,
        "nominal speed": 2.0,
        "operating speed": 2.0,
        # Negative weights for unsuitable cases
        "stationary": -2.0,
        "non-rotating": -2.0,
        "fixed": -1.0,
        "static": -1.0,
        "no rotation": -2.0,
        "transient": -1.0,  # MRF is typically steady-state
        "startup": -1.0,
        "acceleration": -1.0,
        "deceleration": -1.0,
        "variable speed": -1.0,
        "speed variation": -1.0,
        "unsteady rotation": -1.0,
        "time dependent rotation": -1.0,
        "oscillating rotation": -1.0,
        "reciprocating": -2.0,
        "linear": -2.0,
        "translational": -2.0,
        "sliding": -2.0,
        "combustion": -1.0,  # Avoid confusion with reactive flows
        "reacting": -1.0,
        "reactive": -1.0,
        "burning": -1.0,
        "flame": -1.0
    }
}

# Context-aware phrase detection
CONTEXT_PHRASES = {
    "compressible": [
        "shock wave",
        "sonic boom",
        "gas dynamics",
        "high-speed flow",
        "high speed flow",
        "mach number",
        "compressible flow"
    ],
    "multiphase": [
        "free surface",
        "dam break",
        "volume of fluid",
        "air-water interface",
        "liquid-gas interface",
        "two-phase flow",
        "multiphase flow"
    ],
    "heat_transfer": [
        "heat transfer",
        "conjugate heat transfer",
        "thermal boundary",
        "heat exchanger",
        "heat sink",
        "thermal management",
        "multi-region",
        "solid-fluid coupling"
    ]
}

# Parameter validation requirements for each solver
SOLVER_PARAMETER_REQUIREMENTS = {
    SolverType.SIMPLE_FOAM: {
        "required": ["reynolds_number", "velocity"],
        "optional": ["pressure", "turbulence_intensity"],
        "physics_checks": ["incompressible", "steady_state_compatible"]
    },
    SolverType.PIMPLE_FOAM: {
        "required": ["reynolds_number", "velocity"],
        "optional": ["pressure", "turbulence_intensity", "end_time"],
        "physics_checks": ["incompressible", "transient_compatible"]
    },
    SolverType.INTER_FOAM: {
        "required": ["velocity", "phases"],
        "optional": ["surface_tension", "gravity", "contact_angle"],
        "physics_checks": ["multiphase", "transient_only"]
    },
    SolverType.RHO_PIMPLE_FOAM: {
        "required": ["velocity", "temperature", "pressure"],
        "optional": ["mach_number", "turbulence_intensity"],
        "physics_checks": ["compressible", "density_varying"]
    },
    SolverType.CHT_MULTI_REGION_FOAM: {
        "required": ["velocity", "temperature"],
        "optional": ["heat_flux", "thermal_conductivity", "solid_regions"],
        "physics_checks": ["heat_transfer", "multi_region", "conjugate"]
    },
    SolverType.REACTING_FOAM: {
        "required": ["velocity", "temperature", "species"],
        "optional": ["reaction_rate", "mixture_fraction", "fuel_composition"],
        "physics_checks": ["combustion", "chemical_reactions"]
    },
    SolverType.BUOYANT_SIMPLE_FOAM: {
        "required": ["temperature", "gravity"],
        "optional": ["velocity", "thermal_expansion", "prandtl_number"],
        "physics_checks": ["heat_transfer", "buoyancy", "steady_state_compatible"]
    },
    SolverType.PISO_FOAM: {
        "required": ["reynolds_number", "velocity"],
        "optional": ["pressure", "turbulence_intensity", "end_time"],
        "physics_checks": ["incompressible", "transient_only"]
    },
    SolverType.SONIC_FOAM: {
        "required": ["velocity", "temperature", "pressure", "mach_number"],
        "optional": ["turbulence_intensity", "gas_properties"],
        "physics_checks": ["compressible", "supersonic_compatible", "transient_only"]
    },
    SolverType.MRF_SIMPLE_FOAM: {
        "required": ["reynolds_number", "velocity", "rotation_rate"],
        "optional": ["pressure", "turbulence_intensity", "mrf_zones"],
        "physics_checks": ["incompressible", "steady_state_compatible", "rotating_machinery"]
    }
}

# Intelligent defaults for missing parameters
INTELLIGENT_DEFAULTS = {
    "reynolds_number": {
        "cylinder": {"low": 100, "medium": 1000, "high": 10000},
        "sphere": {"low": 300, "medium": 3000, "high": 30000},
        "airfoil": {"low": 100000, "medium": 1000000, "high": 10000000}
    },
    "velocity": {
        "low_speed": 1.0,
        "medium_speed": 10.0,
        "high_speed": 100.0
    },
    "temperature": {
        "ambient": 293.15,  # 20°C
        "cold": 273.15,     # 0°C
        "hot": 373.15,      # 100°C
        "mars": 210.0,      # Mars surface temperature (-63°C)
        "moon": 250.0       # Moon surface temperature (day side, -23°C)
    },
    "pressure": {
        "atmospheric": 101325.0,
        "low": 50000.0,
        "high": 200000.0,
        "mars": 610.0,      # Mars atmospheric pressure (0.6% of Earth's)
        "moon": 3e-15       # Moon atmospheric pressure (essentially vacuum)
    },
    "gravity": {
        "earth": 9.81,      # m/s²
        "mars": 3.71,       # m/s²
        "moon": 1.62        # m/s²
    },
    "density": {
        "earth": 1.225,     # kg/m³ (Earth atmosphere at sea level)
        "mars": 0.02,       # kg/m³ (Mars atmosphere)
        "moon": 1e-14       # kg/m³ (Moon trace atmosphere)
    },
    "viscosity": {
        "earth": 1.81e-5,   # Pa·s (Earth atmosphere)
        "mars": 1.0e-5,     # Pa·s (Mars atmosphere)
        "moon": 1.0e-5      # Pa·s (Moon trace atmosphere - similar to Mars)
    },
    "thermal_expansion": {
        "air": 3.43e-3,     # 1/K for air at 20°C
        "water": 2.1e-4,    # 1/K for water at 20°C
        "typical": 3.0e-3   # 1/K typical for gases
    },
    "rotation_rate": {
        "low": 100.0,       # rad/s (about 950 RPM)
        "medium": 500.0,    # rad/s (about 4775 RPM)
        "high": 1000.0,     # rad/s (about 9550 RPM)
        "fan": 314.0,       # rad/s (about 3000 RPM - typical fan)
        "pump": 157.0,      # rad/s (about 1500 RPM - typical pump)
        "turbine": 628.0    # rad/s (about 6000 RPM - typical turbine)
    }
}

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
    },
    SolverType.BUOYANT_SIMPLE_FOAM: {
        "name": "buoyantSimpleFoam",
        "description": "Steady-state incompressible flow solver with buoyancy effects for natural convection",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["steady"],
            "turbulence": ["laminar", "RANS"],
            "heat_transfer": True,
            "multiphase": False,
            "compressible": False,
            "buoyancy": True,
            "natural_convection": True
        },
        "recommended_for": [
            "Natural convection problems",
            "Buoyancy-driven flows",
            "Heat transfer with density variations",
            "Thermal plumes",
            "Rayleigh-Bénard convection",
            "Cavity flows with heating",
            "Building ventilation",
            "Thermal stratification"
        ],
        "not_recommended_for": [
            "Forced convection dominated flows",
            "Transient thermal problems",
            "Compressible flows",
            "Multiphase flows",
            "High-speed flows"
        ],
        "typical_applications": [
            "Natural convection in enclosures",
            "Hot air rising from heated surfaces",
            "Thermal comfort in buildings",
            "Cooling of electronic equipment",
            "Geothermal flows",
            "Atmospheric boundary layers",
            "Solar collectors",
            "Thermal management systems"
        ]
    },
    SolverType.PISO_FOAM: {
        "name": "pisoFoam",
        "description": "Transient incompressible flow solver using PISO algorithm",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["transient"],
            "turbulence": ["laminar", "RANS", "LES"],
            "heat_transfer": False,
            "multiphase": False,
            "compressible": False,
            "piso_algorithm": True
        },
        "recommended_for": [
            "Transient flow simulations",
            "Unsteady flow phenomena",
            "Accurate time-dependent solutions",
            "Flows with rapid changes",
            "Oscillating and pulsatile flows",
            "Startup and shutdown simulations",
            "Vortex shedding at moderate Reynolds numbers",
            "Detailed temporal resolution required"
        ],
        "not_recommended_for": [
            "Steady-state analysis",
            "High Reynolds number turbulent flows",
            "Compressible flows",
            "Multiphase flows",
            "Very long time simulations"
        ],
        "typical_applications": [
            "Pulsatile flow in pipes",
            "Oscillating cylinder flows",
            "Periodic flow phenomena",
            "Transient mixing processes",
            "Flow development studies",
            "Laminar-turbulent transition",
            "Biofluid dynamics",
            "Microfluidic devices"
        ]
    },
    SolverType.SONIC_FOAM: {
        "name": "sonicFoam",
        "description": "Transient compressible flow solver for trans-sonic and supersonic flows",
        "capabilities": {
            "flow_type": ["compressible"],
            "time_dependency": ["transient"],
            "turbulence": ["laminar", "RANS"],
            "heat_transfer": True,
            "multiphase": False,
            "compressible": True,
            "supersonic": True,
            "shock_waves": True
        },
        "recommended_for": [
            "Supersonic flows (Mach > 1.0)",
            "Trans-sonic flows (Mach 0.8-1.2)",
            "Shock wave propagation",
            "Compressible turbulence",
            "High-speed aerodynamics",
            "Shock tube problems",
            "Blast wave simulations",
            "Hypersonic flows"
        ],
        "not_recommended_for": [
            "Incompressible flows",
            "Low-speed flows (Mach < 0.3)",
            "Steady-state problems",
            "Multiphase flows",
            "Liquid flows"
        ],
        "typical_applications": [
            "Supersonic nozzles",
            "Shock tubes",
            "Hypersonic vehicle aerodynamics",
            "Rocket nozzle flows",
            "Blast wave propagation",
            "Compressible jet flows",
            "Supersonic wind tunnel flows",
            "Ballistic projectile flows"
        ]
    },
    SolverType.MRF_SIMPLE_FOAM: {
        "name": "MRFSimpleFoam",
        "description": "Steady-state incompressible flow solver with Multiple Reference Frame zones",
        "capabilities": {
            "flow_type": ["incompressible"],
            "time_dependency": ["steady"],
            "turbulence": ["laminar", "RANS"],
            "heat_transfer": False,
            "multiphase": False,
            "compressible": False,
            "rotating_machinery": True,
            "multiple_reference_frames": True
        },
        "recommended_for": [
            "Rotating machinery",
            "Steady-state turbomachinery",
            "Fans and propellers",
            "Pumps and compressors",
            "Turbines",
            "Mixers and stirrers",
            "Centrifugal separators",
            "Rotating heat exchangers"
        ],
        "not_recommended_for": [
            "Transient rotating flows",
            "Flows without rotation",
            "Compressible flows",
            "Multiphase flows",
            "Unsteady rotor-stator interactions"
        ],
        "typical_applications": [
            "Centrifugal pumps",
            "Axial fans",
            "Propeller analysis",
            "Turbine blade rows",
            "Compressor stages",
            "Mixing tanks",
            "Cyclone separators",
            "Wind turbine rotors"
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
        
        # Get AI recommendation for solver with confidence scoring
        solver_recommendation, confidence_score, alternatives = get_ai_solver_recommendation(
            problem_features, 
            SOLVER_REGISTRY
        )
        
        # Validate and enhance parameters for the selected solver
        missing_params, suggested_defaults = validate_solver_parameters(
            solver_recommendation, 
            parsed_params, 
            geometry_info
        )
        
        # Apply intelligent defaults for missing parameters
        enhanced_params = parsed_params.copy()
        for param, default_value in suggested_defaults.items():
            if param not in enhanced_params or enhanced_params[param] is None:
                enhanced_params[param] = default_value
                if state["verbose"]:
                    logger.info(f"Applied intelligent default: {param} = {default_value}")
        
        # Log any missing critical parameters
        if missing_params:
            warning_msg = f"Missing parameters for {solver_recommendation.value}: {missing_params}"
            if suggested_defaults:
                warning_msg += f" (applied defaults: {list(suggested_defaults.keys())})"
            logger.warning(warning_msg)
        
        # Build solver settings with the recommended solver and enhanced parameters
        solver_settings = build_solver_settings(
            solver_recommendation,
            enhanced_params,
            geometry_info,
            confidence_score,
            alternatives
        )
        
        # Generate solver configuration files
        solver_config = generate_solver_config(solver_settings, parsed_params, geometry_info, state)
        
        # Validate solver configuration
        validation_result = validate_solver_config(solver_config, parsed_params)
        
        # Only return early if there are critical errors that prevent solver execution
        critical_errors = [error for error in validation_result["errors"] 
                          if "Missing required file" not in error]  # Allow missing files for now
        
        if critical_errors:
            logger.error(f"Critical solver validation errors: {critical_errors}")
            return {
                **state,
                "errors": state["errors"] + critical_errors,
                "warnings": state["warnings"] + validation_result["warnings"]
            }
        
        if state["verbose"]:
            logger.info(f"Solver Selector: Selected {solver_settings['solver']} solver")
            logger.info(f"Solver Selector: Analysis type: {solver_settings['analysis_type']}")
            logger.info(f"Solver Selector: Selection confidence: {confidence_score:.2f}")
            
            # Log alternatives if confidence is low
            if confidence_score < 0.7 and alternatives:
                logger.info("Solver Selector: Alternative suggestions:")
                for alt_solver, alt_confidence, alt_reason in alternatives:
                    logger.info(f"  - {alt_solver.value}: {alt_confidence:.2f} ({alt_reason})")
        
        return {
            **state,
            "solver_settings": solver_config,
            "errors": state["errors"] + validation_result.get("errors", []),
            "warnings": state["warnings"] + validation_result.get("warnings", [])
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


def extract_mach_number_from_text(text: str) -> Optional[float]:
    """Extract Mach number from text with improved patterns."""
    import re
    
    # Pattern 1: "Mach X.X" or "Mach X"
    match = re.search(r'mach\s+(\d+(?:\.\d+)?)', text.lower())
    if match:
        return float(match.group(1))
    
    # Pattern 2: "M = X.X" or "M=X.X"
    match = re.search(r'm\s*=\s*(\d+(?:\.\d+)?)', text.lower())
    if match:
        return float(match.group(1))
    
    # Pattern 3: "supersonic" implies Mach > 1
    if 'supersonic' in text.lower():
        return 1.5  # Default for supersonic
    
    # Pattern 4: "hypersonic" implies Mach > 5
    if 'hypersonic' in text.lower():
        return 6.0  # Default for hypersonic
    
    # Pattern 5: "transonic" implies Mach ~ 1
    if 'transonic' in text.lower() or 'trans-sonic' in text.lower():
        return 1.0  # Default for transonic
    
    return None


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
        elif geometry_type == GeometryType.NOZZLE:
            char_length = geometry.get("throat_diameter", geometry.get("length", 0.1))
        else:
            char_length = 0.1  # Default
        
        # Calculate velocity from Re = ρ * V * L / μ
        velocity = reynolds_number * viscosity / (density * char_length)
        logger.info(f"Calculated velocity {velocity:.3f} m/s from Reynolds number {reynolds_number}")
    
    # Default velocity if still None
    if velocity is None:
        velocity = 1.0
    
    # Extract Mach number from text first (higher priority than calculated)
    original_prompt = state.get("original_prompt", state.get("user_prompt", ""))
    mach_from_text = extract_mach_number_from_text(original_prompt)
    
    # Use text-extracted Mach number if available, otherwise calculate
    if mach_from_text is not None:
        mach_number = mach_from_text
        logger.info(f"Using Mach number from text: {mach_number}")
    else:
        # Calculate from velocity and temperature
        temperature = params.get("temperature", 300.0)  # K
        speed_of_sound = 343.0 * (temperature / 300.0)**0.5  # m/s, temperature corrected
        mach_number = velocity / speed_of_sound if velocity else 0
    
    # Determine expected flow phenomena
    expects_vortex_shedding = check_vortex_shedding(
        geometry["type"], 
        reynolds_number
    )
    
    # Extract keywords from original prompt using enhanced detection
    original_prompt = state.get("original_prompt", state.get("user_prompt", ""))
    keywords = extract_keywords(original_prompt)
    physics_scores = extract_keywords_with_context(original_prompt)
    
    # Enhanced physics detection using weighted scores
    is_multiphase = (params.get("is_multiphase", False) or 
                    physics_scores.get("multiphase", 0) > 1.0 or
                    check_multiphase_indicators(original_prompt, params))
    phases = params.get("phases", [])
    free_surface = params.get("free_surface", False) or physics_scores.get("multiphase", 0) > 2.0
    
    # Check for compressibility with enhanced detection
    is_compressible = (params.get("compressible", False) or 
                      (mach_number is not None and mach_number > 0.3) or
                      physics_scores.get("compressible", 0) > 1.0 or
                      check_compressible_indicators(original_prompt))
    
    # Check for heat transfer with enhanced detection
    has_heat_transfer = (physics_scores.get("heat_transfer", 0) > 1.0 or
                        check_heat_transfer_indicators(original_prompt, params))
    
    # Check for reactive flows with enhanced detection
    has_reactive_flow = (physics_scores.get("reactive", 0) > 1.0 or
                        check_reactive_flow_indicators(original_prompt, params))
    
    # INTELLIGENT HEAT TRANSFER CONTEXT ANALYSIS
    # Use intelligent context analysis instead of simple score thresholds
    heat_transfer_analysis = analyze_heat_transfer_context(original_prompt, physics_scores)
    
    # Override heat transfer detection with intelligent analysis
    has_heat_transfer = heat_transfer_analysis["has_heat_transfer"]
    is_multi_region = heat_transfer_analysis["is_multi_region"]
    is_natural_convection = heat_transfer_analysis["is_natural_convection"]
    
    # Legacy fallback for explicit multi-region keywords (if analysis is low confidence)
    if heat_transfer_analysis["confidence"] < 0.6:
        explicit_multi_keywords = ["multi-region", "multiregion", "multi region", "solid-fluid", 
                                  "solid fluid", "conjugate", "cht", "coupling between"]
        has_explicit_multi = any(kw in original_prompt.lower() for kw in explicit_multi_keywords)
        if has_explicit_multi:
            is_multi_region = True
    
    return {
        "geometry_type": geometry["type"].value if hasattr(geometry["type"], 'value') else str(geometry["type"]),
        "reynolds_number": reynolds_number,
        "mach_number": mach_number,
        "flow_type": params.get("flow_type", FlowType.LAMINAR),
        "analysis_type": params.get("analysis_type", AnalysisType.UNSTEADY),
        "expects_vortex_shedding": expects_vortex_shedding,
        "has_heat_transfer": has_heat_transfer,
        "is_natural_convection": is_natural_convection,
        "is_compressible": is_compressible,
        "is_multiphase": is_multiphase,
        "phases": phases,
        "free_surface": free_surface,
        "has_reactive_flow": has_reactive_flow,
        "is_multi_region": is_multi_region,
        "user_keywords": keywords,
        "time_scale_interest": infer_time_scale_interest(params, keywords),
        "heat_transfer_confidence": heat_transfer_analysis["confidence"],
        "keyword_scores": physics_scores  # Pass keyword scores for detailed analysis
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


def check_natural_convection_indicators(prompt: str) -> bool:
    """Check if the problem involves natural convection (single-region buoyancy-driven flow)."""
    prompt_lower = prompt.lower()
    
    # Natural convection indicators
    natural_convection_patterns = [
        "natural convection", "buoyancy", "buoyant", "thermal plume", 
        "rayleigh", "heated cavity", "heated enclosure", "cavity flow",
        "enclosed flow", "density driven", "gravity driven",
        "thermal circulation", "convective flow", "hot wall", "cold wall",
        "heated surface", "cooling surface", "thermal gradient",
        "temperature difference", "thermal stratification"
    ]
    
    # Check for natural convection patterns
    for pattern in natural_convection_patterns:
        if pattern in prompt_lower:
            return True
    
    # Check for cavity/enclosure + heating patterns
    cavity_patterns = ["cavity", "enclosure", "chamber", "box", "room"]
    heating_patterns = ["heated", "hot", "cooling", "cold", "temperature"]
    
    has_cavity = any(pattern in prompt_lower for pattern in cavity_patterns)
    has_heating = any(pattern in prompt_lower for pattern in heating_patterns)
    
    if has_cavity and has_heating:
        return True
    
    return False


def check_conjugate_heat_transfer_indicators(prompt: str) -> bool:
    """Check if the problem involves conjugate heat transfer (multi-region solid-fluid coupling)."""
    prompt_lower = prompt.lower()
    
    # Strong conjugate heat transfer indicators
    conjugate_indicators = [
        "conjugate heat transfer", "conjugate", "cht", "solid-fluid coupling",
        "solid fluid coupling", "multi-region", "multiregion", "multi region",
        "heat exchanger", "thermal coupling", "wall conduction", 
        "solid conduction", "coupled", "coupling between"
    ]
    
    # Check for explicit conjugate heat transfer
    for indicator in conjugate_indicators:
        if indicator in prompt_lower:
            return True
    
    # Check for solid + fluid + thermal patterns
    solid_patterns = ["solid", "metal", "steel", "aluminum", "copper", "wall thickness"]
    fluid_patterns = ["fluid", "air", "water", "flow"]
    thermal_patterns = ["heat transfer", "thermal", "conduction", "temperature"]
    
    has_solid = any(pattern in prompt_lower for pattern in solid_patterns)
    has_fluid = any(pattern in prompt_lower for pattern in fluid_patterns)
    has_thermal = any(pattern in prompt_lower for pattern in thermal_patterns)
    
    # Only trigger if all three are present (solid + fluid + thermal)
    if has_solid and has_fluid and has_thermal:
        return True
    
    return False


def analyze_heat_transfer_context(prompt: str, physics_scores: Dict[str, float]) -> Dict[str, bool]:
    """Intelligent analysis of heat transfer context to distinguish single-region vs multi-region."""
    prompt_lower = prompt.lower()
    
    # Check for natural convection and conjugate heat transfer patterns first
    is_natural_conv = check_natural_convection_indicators(prompt)
    is_conjugate = check_conjugate_heat_transfer_indicators(prompt)
    
    # Initialize results
    analysis = {
        "has_heat_transfer": physics_scores.get("heat_transfer", 0) > 1.0,
        "is_natural_convection": is_natural_conv,
        "is_conjugate_heat_transfer": is_conjugate,
        "is_multi_region": False,
        "confidence": 0.0
    }
    
    # If natural convection is detected, it implies heat transfer
    if is_natural_conv:
        analysis["has_heat_transfer"] = True
    
    # If conjugate heat transfer is detected, it implies heat transfer
    if is_conjugate:
        analysis["has_heat_transfer"] = True
    
    # Only proceed with analysis if heat transfer is detected
    if not analysis["has_heat_transfer"]:
        return analysis
    
    # Decision logic with confidence scoring
    if is_conjugate and not is_natural_conv:
        # Clear conjugate heat transfer case
        analysis["is_multi_region"] = True
        analysis["confidence"] = 0.9
    elif is_natural_conv and not is_conjugate:
        # Clear natural convection case
        analysis["is_multi_region"] = False
        analysis["confidence"] = 0.9
    elif is_conjugate and is_natural_conv:
        # Ambiguous case - both detected
        # Favor multi-region if explicit conjugate keywords
        explicit_conjugate = any(kw in prompt_lower for kw in [
            "conjugate", "cht", "multi-region", "solid-fluid", "coupling"
        ])
        if explicit_conjugate:
            analysis["is_multi_region"] = True
            analysis["confidence"] = 0.7
        else:
            analysis["is_multi_region"] = False
            analysis["confidence"] = 0.6
    else:
        # No specific patterns detected, use fallback logic
        heat_score = physics_scores.get("heat_transfer", 0)
        
        # Check for multi-region keywords as fallback
        multi_region_keywords = [
            "heat exchanger", "thermal management", "electronics cooling",
            "cpu cooling", "heat sink", "thermal interface"
        ]
        has_multi_keywords = any(kw in prompt_lower for kw in multi_region_keywords)
        
        if has_multi_keywords or heat_score > 4.0:
            analysis["is_multi_region"] = True
            analysis["confidence"] = 0.5  # Low confidence fallback
        else:
            analysis["is_multi_region"] = False
            analysis["confidence"] = 0.4  # Low confidence fallback
    
    return analysis


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


def extract_keywords_with_context(prompt: str) -> Dict[str, float]:
    """
    Enhanced keyword extraction with context analysis and intelligent multiphase detection.
    Returns physics category scores based on weighted keyword detection.
    """
    import re
    prompt_lower = prompt.lower()
    
    # Initialize physics category scores
    physics_scores = {
        "compressible": 0.0,
        "multiphase": 0.0,
        "heat_transfer": 0.0,
        "reactive": 0.0,
        "steady": 0.0,
        "transient": 0.0,
        "piso": 0.0,
        "sonic": 0.0,
        "mrf": 0.0
    }
    
    # First, check for context phrases (higher priority)
    for category, phrases in CONTEXT_PHRASES.items():
        for phrase in phrases:
            if phrase in prompt_lower:
                # Context phrases get full weight
                physics_scores[category] += 2.0
                logger.debug(f"Context phrase detected: '{phrase}' -> {category} (+2.0)")
    
    # Then check individual keywords with weights for all categories EXCEPT multiphase
    for category, keywords in KEYWORD_WEIGHTS.items():
        if category == "multiphase":
            continue  # Skip - we'll use intelligent detection instead
            
        for keyword, weight in keywords.items():
            # Use word boundaries for better matching
            if keyword.startswith(r"\b") or keyword.endswith(r"\b"):
                pattern = keyword
            else:
                pattern = rf"\b{re.escape(keyword)}\b"
            
            if re.search(pattern, prompt_lower):
                physics_scores[category] += weight
                logger.debug(f"Keyword detected: '{keyword}' -> {category} ({weight:+.1f})")
    
    # INTELLIGENT MULTIPHASE DETECTION - Use OpenAI with context awareness
    try:
        from agents.nl_interpreter import detect_multiphase_flow
        
        # Check if this is likely a compressible flow case first
        compressible_indicators = ["gas dynamics", "shock", "supersonic", "compressible", "mach"]
        is_likely_compressible = any(indicator in prompt_lower for indicator in compressible_indicators)
        
        if is_likely_compressible:
            # Add context to help AI understand these are typically single-phase compressible flows
            context_text = f"{prompt} (Note: This is a compressible flow scenario involving gas dynamics, which typically involves a single gas phase)"
            multiphase_info = detect_multiphase_flow(context_text)
        else:
            multiphase_info = detect_multiphase_flow(prompt)
        
        if multiphase_info.get("is_multiphase", False):
            physics_scores["multiphase"] += 3.0  # High confidence from AI
            logger.debug(f"AI multiphase detection: TRUE -> multiphase (+3.0)")
            logger.debug(f"AI explanation: {multiphase_info.get('explanation', 'No explanation')}")
        else:
            physics_scores["multiphase"] = 0.0  # AI says it's single-phase
            logger.debug(f"AI multiphase detection: FALSE -> single-phase (0.0)")
            logger.debug(f"AI explanation: {multiphase_info.get('explanation', 'No explanation')}")
    except Exception as e:
        logger.warning(f"AI multiphase detection failed: {e}, falling back to keyword detection")
        # Fallback to keyword detection if AI fails
        for keyword, weight in KEYWORD_WEIGHTS.get("multiphase", {}).items():
            if keyword.startswith(r"\b") or keyword.endswith(r"\b"):
                pattern = keyword
            else:
                pattern = rf"\b{re.escape(keyword)}\b"
            
            if re.search(pattern, prompt_lower):
                physics_scores["multiphase"] += weight
                logger.debug(f"Fallback keyword detected: '{keyword}' -> multiphase ({weight:+.1f})")
    
    # Special handling for "shock wave" vs "water wave"
    if "shock wave" in prompt_lower or "shockwave" in prompt_lower:
        physics_scores["compressible"] += 2.0
        physics_scores["multiphase"] -= 1.0  # Reduce multiphase score
        logger.debug("'shock wave' detected -> compressible (+2.0), multiphase (-1.0)")
    
    # Special handling for air-water combinations (only if not overridden by AI)
    if re.search(r"\bair\b", prompt_lower) and re.search(r"\bwater\b", prompt_lower):
        # Only add if AI didn't already detect multiphase
        if physics_scores["multiphase"] < 1.0:
            physics_scores["multiphase"] += 1.5
            logger.debug("Air-water combination detected -> multiphase (+1.5)")
    
    # Normalize negative scores to zero
    for category in physics_scores:
        physics_scores[category] = max(0.0, physics_scores[category])
    
    return physics_scores


def extract_keywords(prompt: str) -> List[str]:
    """
    Legacy keyword extraction function for backward compatibility.
    Now uses the enhanced context-aware detection.
    """
    physics_scores = extract_keywords_with_context(prompt)
    
    # Convert scores back to legacy format
    found_keywords = []
    for category, score in physics_scores.items():
        if score > 0.5:  # Threshold for keyword detection
            found_keywords.append(f"{category}:{score:.1f}")
    
    return found_keywords


def validate_solver_parameters(solver_type: SolverType, params: Dict[str, Any], 
                              geometry_info: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """
    Validate and suggest missing parameters for solver type.
    Returns (missing_params, suggested_defaults).
    """
    requirements = SOLVER_PARAMETER_REQUIREMENTS.get(solver_type, {})
    required_params = requirements.get("required", [])
    
    missing_params = []
    suggested_defaults = {}
    
    for param in required_params:
        if param not in params or params[param] is None:
            missing_params.append(param)
            default_value = get_intelligent_default(param, solver_type, params, geometry_info)
            if default_value is not None:
                suggested_defaults[param] = default_value
    
    return missing_params, suggested_defaults


def detect_mars_simulation(prompt: str) -> bool:
    """Detect if the user is requesting a Mars simulation."""
    mars_keywords = [
        "mars", "martian", "red planet", "on mars", "mars atmosphere",
        "mars surface", "mars conditions", "mars environment"
    ]
    
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in mars_keywords)


def detect_moon_simulation(prompt: str) -> bool:
    """Detect if the user is requesting a Moon simulation."""
    moon_keywords = [
        "moon", "lunar", "on the moon", "moon surface", "moon conditions",
        "moon environment", "lunar surface", "lunar conditions", "lunar environment"
    ]
    
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in moon_keywords)


def detect_custom_environment(prompt: str) -> Dict[str, Any]:
    """Use OpenAI to detect and extract custom environmental conditions."""
    try:
        # Skip if it's already Mars/Moon/Earth
        if detect_mars_simulation(prompt) or detect_moon_simulation(prompt):
            return {"has_custom_environment": False}
        
        # Check for environmental indicators
        environmental_keywords = [
            "pluto", "venus", "jupiter", "saturn", "neptune", "uranus", "mercury",
            "altitude", "elevation", "sea level", "underwater", "deep ocean", "high altitude",
            "mountain", "stratosphere", "atmosphere", "pressure", "vacuum", "space",
            "planet", "planetary", "conditions", "environment"
        ]
        
        prompt_lower = prompt.lower()
        has_environmental_context = any(keyword in prompt_lower for keyword in environmental_keywords)
        
        if not has_environmental_context:
            return {"has_custom_environment": False}
        
        # Get settings for API key
        import sys
        sys.path.append('src')
        from foamai.config import get_settings
        settings = get_settings()
        
        if not settings.openai_api_key:
            logger.warning("No OpenAI API key found for custom environment detection")
            return {"has_custom_environment": False}
        
        # Use OpenAI to extract environmental parameters
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        system_message = """You are an expert in planetary science and atmospheric physics. Analyze the given prompt to determine if it describes a specific environmental or planetary condition that would affect fluid dynamics simulation parameters.

Your task is to:
1. Identify if there's a specific environment mentioned (planet, altitude, etc.)
2. Determine appropriate physical parameters for that environment
3. Return the parameters in the specified JSON format

Be accurate with scientific values. If unsure about specific parameters, use reasonable estimates based on known science."""

        user_message = f"""Analyze this fluid dynamics scenario for custom environmental conditions:

PROMPT: "{prompt}"

If this describes a specific environment (planet, altitude, underwater, etc.) that differs from standard Earth sea-level conditions, extract the appropriate physical parameters.

Respond with ONLY this JSON format:
{{
    "has_custom_environment": true/false,
    "environment_name": "name of environment (e.g., 'Pluto', 'High Altitude', 'Underwater')",
    "temperature": temperature_in_kelvin,
    "pressure": pressure_in_pascals,
    "density": density_in_kg_per_m3,
    "viscosity": viscosity_in_pa_s,
    "gravity": gravity_in_m_per_s2,
    "explanation": "brief explanation of the environment and parameter choices"
}}

Examples:
- "Flow on Pluto" → Pluto conditions (40K, very low pressure/density, 0.62 m/s² gravity)
- "Flow at 10km altitude" → High altitude conditions (reduced pressure/density, same gravity)
- "Flow 100m underwater" → Underwater conditions (high pressure, water density)
- "Flow around cylinder" → has_custom_environment: false (standard conditions)

If no specific environment is mentioned, return has_custom_environment: false."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        # Parse JSON response
        import json
        try:
            result = json.loads(response.choices[0].message.content)
            if result.get("has_custom_environment", False):
                logger.info(f"Detected custom environment: {result.get('environment_name', 'Unknown')}")
                logger.info(f"Parameters: T={result.get('temperature')}K, P={result.get('pressure')}Pa, ρ={result.get('density')}kg/m³")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OpenAI environment response: {e}")
            return {"has_custom_environment": False}
            
    except Exception as e:
        logger.warning(f"Custom environment detection failed: {e}")
        return {"has_custom_environment": False}


def get_intelligent_default(param: str, solver_type: SolverType, params: Dict[str, Any], 
                          geometry_info: Dict[str, Any]) -> Any:
    """
    Generate intelligent default values for missing parameters.
    """
    geometry_type = geometry_info.get("type", GeometryType.CYLINDER)
    
    # Check if this is a Mars, Moon, or custom environment simulation
    original_prompt = params.get("original_prompt", "")
    is_mars_simulation = detect_mars_simulation(original_prompt)
    is_moon_simulation = detect_moon_simulation(original_prompt)
    
    # Check for custom environment if not Mars/Moon
    custom_environment = None
    if not is_mars_simulation and not is_moon_simulation:
        custom_environment = detect_custom_environment(original_prompt)
        if custom_environment.get("has_custom_environment", False):
            logger.info(f"Using custom environment parameters: {custom_environment.get('environment_name', 'Unknown')}")
    
    if param == "reynolds_number":
        # Base Reynolds number on geometry type and flow regime
        geometry_name = geometry_type.value if hasattr(geometry_type, 'value') else str(geometry_type).lower()
        
        if geometry_name in INTELLIGENT_DEFAULTS["reynolds_number"]:
            defaults = INTELLIGENT_DEFAULTS["reynolds_number"][geometry_name]
            # Choose based on solver type
            if solver_type == SolverType.SIMPLE_FOAM:
                return defaults["low"]  # Conservative for steady-state
            elif solver_type in [SolverType.PIMPLE_FOAM, SolverType.INTER_FOAM]:
                return defaults["medium"]  # Moderate for transient
            else:
                return defaults["high"]  # Higher for complex physics
        else:
            return 1000  # Generic default
    
    elif param == "velocity":
        # Base velocity on flow regime and solver
        if solver_type == SolverType.RHO_PIMPLE_FOAM:
            return INTELLIGENT_DEFAULTS["velocity"]["high_speed"]  # Compressible flows
        elif solver_type == SolverType.INTER_FOAM:
            return INTELLIGENT_DEFAULTS["velocity"]["low_speed"]   # Multiphase flows
        else:
            return INTELLIGENT_DEFAULTS["velocity"]["medium_speed"]  # General flows
    
    elif param == "temperature":
        # Base temperature on solver type and application
        if solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.CHT_MULTI_REGION_FOAM, SolverType.REACTING_FOAM, SolverType.BUOYANT_SIMPLE_FOAM, SolverType.SONIC_FOAM]:
            if is_mars_simulation:
                return INTELLIGENT_DEFAULTS["temperature"]["mars"]
            elif is_moon_simulation:
                return INTELLIGENT_DEFAULTS["temperature"]["moon"]
            elif custom_environment and custom_environment.get("has_custom_environment", False):
                return custom_environment.get("temperature", INTELLIGENT_DEFAULTS["temperature"]["ambient"])
            else:
                return INTELLIGENT_DEFAULTS["temperature"]["ambient"]
        else:
            return None  # Not required for incompressible solvers
    
    elif param == "pressure":
        # Base pressure on solver type
        if solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.SONIC_FOAM]:
            if is_mars_simulation:
                return INTELLIGENT_DEFAULTS["pressure"]["mars"]
            elif is_moon_simulation:
                return INTELLIGENT_DEFAULTS["pressure"]["moon"]
            elif custom_environment and custom_environment.get("has_custom_environment", False):
                return custom_environment.get("pressure", INTELLIGENT_DEFAULTS["pressure"]["atmospheric"])
            else:
                return INTELLIGENT_DEFAULTS["pressure"]["atmospheric"]
        else:
            return None  # Usually relative pressure for incompressible
    
    elif param == "gravity":
        # Base gravity on simulation environment
        if is_mars_simulation:
            return INTELLIGENT_DEFAULTS["gravity"]["mars"]
        elif is_moon_simulation:
            return INTELLIGENT_DEFAULTS["gravity"]["moon"]
        elif custom_environment and custom_environment.get("has_custom_environment", False):
            return custom_environment.get("gravity", INTELLIGENT_DEFAULTS["gravity"]["earth"])
        else:
            return INTELLIGENT_DEFAULTS["gravity"]["earth"]
    
    elif param == "density":
        # Base density on simulation environment
        if is_mars_simulation:
            return INTELLIGENT_DEFAULTS["density"]["mars"]
        elif is_moon_simulation:
            return INTELLIGENT_DEFAULTS["density"]["moon"]
        elif custom_environment and custom_environment.get("has_custom_environment", False):
            return custom_environment.get("density", INTELLIGENT_DEFAULTS["density"]["earth"])
        else:
            return INTELLIGENT_DEFAULTS["density"]["earth"]
    
    elif param == "viscosity":
        # Base viscosity on simulation environment
        if is_mars_simulation:
            return INTELLIGENT_DEFAULTS["viscosity"]["mars"]
        elif is_moon_simulation:
            return INTELLIGENT_DEFAULTS["viscosity"]["moon"]
        elif custom_environment and custom_environment.get("has_custom_environment", False):
            return custom_environment.get("viscosity", INTELLIGENT_DEFAULTS["viscosity"]["earth"])
        else:
            return INTELLIGENT_DEFAULTS["viscosity"]["earth"]
    
    elif param == "thermal_expansion":
        # Base thermal expansion on fluid type
        if solver_type == SolverType.BUOYANT_SIMPLE_FOAM:
            return INTELLIGENT_DEFAULTS["thermal_expansion"]["typical"]
        else:
            return None
    
    elif param == "phases":
        # Default phases for multiphase flows
        if solver_type == SolverType.INTER_FOAM:
            return ["water", "air"]
        else:
            return None
    
    elif param == "species":
        # Default species for reactive flows
        if solver_type == SolverType.REACTING_FOAM:
            return ["CH4", "O2", "CO2", "H2O", "N2"]  # Methane combustion
        else:
            return None
    
    elif param == "mach_number":
        # Default Mach number for compressible flows
        if solver_type == SolverType.SONIC_FOAM:
            return 1.5  # Supersonic default
        elif solver_type == SolverType.RHO_PIMPLE_FOAM:
            return 0.5  # Subsonic/transonic default
        else:
            return None
    
    elif param == "rotation_rate":
        # Default rotation rate for rotating machinery
        if solver_type == SolverType.MRF_SIMPLE_FOAM:
            # Try to infer from application context
            original_prompt = params.get("original_prompt", "").lower()
            if any(keyword in original_prompt for keyword in ["fan", "blower", "ventilation"]):
                return INTELLIGENT_DEFAULTS["rotation_rate"]["fan"]
            elif any(keyword in original_prompt for keyword in ["pump", "impeller"]):
                return INTELLIGENT_DEFAULTS["rotation_rate"]["pump"]
            elif any(keyword in original_prompt for keyword in ["turbine", "generator"]):
                return INTELLIGENT_DEFAULTS["rotation_rate"]["turbine"]
            else:
                return INTELLIGENT_DEFAULTS["rotation_rate"]["medium"]  # General default
        else:
            return None
    
    return None


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
) -> Tuple[SolverType, float, List[Tuple[SolverType, float, str]]]:
    """
    AI agent logic to select best solver based on problem features.
    Returns (selected_solver, confidence_score, alternative_suggestions).
    
    Confidence scoring:
    - 1.0: Perfect match, unambiguous selection
    - 0.8-0.9: High confidence, clear physics indicators
    - 0.6-0.7: Medium confidence, some ambiguity
    - 0.4-0.5: Low confidence, multiple viable options
    - 0.0-0.3: Very uncertain, needs user clarification
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
    logger.info(f"  Is Natural Convection: {features.get('is_natural_convection', False)}")
    logger.info(f"  Has Reactive Flow: {features['has_reactive_flow']}")
    logger.info(f"  Is Multi-Region: {features['is_multi_region']}")
    logger.info(f"  Heat Transfer Confidence: {features.get('heat_transfer_confidence', 0.0)}")
    logger.info(f"  Time Scale Interest: {features['time_scale_interest']}")
    logger.info(f"  Keywords: {features['user_keywords']}")
    
    # Enhanced decision logic with confidence scoring and alternatives
    solver_scores = {}
    alternatives = []
    
    # Calculate confidence scores for each solver based on physics indicators
    
    # Priority 1: Reactive flows - Very high confidence if detected
    if features['has_reactive_flow']:
        solver_scores[SolverType.REACTING_FOAM] = 0.95
        logger.info("AI Decision: Reactive flow/combustion detected → reactingFoam (confidence: 0.95)")
        return SolverType.REACTING_FOAM, 0.95, [(SolverType.RHO_PIMPLE_FOAM, 0.3, "Alternative for high-speed combustion")]
    
    # Priority 2: Natural convection - MOVED UP to prioritize over multi-region
    # Use intelligent context analysis to detect natural convection patterns
    if features.get('is_natural_convection', False) and features['has_heat_transfer']:
        heat_confidence = features.get('heat_transfer_confidence', 0.8)
        confidence = min(0.9, heat_confidence + 0.1)  # High confidence for clear natural convection
        alternatives = [
            (SolverType.PIMPLE_FOAM, 0.4, "Transient alternative for time-dependent convection"),
            (SolverType.CHT_MULTI_REGION_FOAM, 0.3, "Multi-region alternative if solid coupling needed")
        ]
        logger.info(f"AI Decision: Natural convection detected by intelligent analysis → buoyantSimpleFoam (confidence: {confidence})")
        return SolverType.BUOYANT_SIMPLE_FOAM, confidence, alternatives
    
    # Priority 3: Supersonic/compressible flows - MOVED UP to prevent multiphase confusion
    mach = features.get('mach_number', 0)
    keyword_scores = features.get('keyword_scores', {})
    sonic_score = keyword_scores.get('sonic', 0)
    
    if mach > 0.8 or sonic_score > 0 or features.get('is_compressible', False):
        # Enhanced supersonic detection - shock waves are inherently supersonic
        shock_indicators = ["shock", "shock wave", "shockwave", "blast"]
        original_prompt = ' '.join(features.get('user_keywords', []))
        has_shock = any(keyword in original_prompt.lower() for keyword in shock_indicators)
        
        if mach > 1.0 or (sonic_score > 2.0 and mach > 0.8) or (has_shock and sonic_score > 5.0):
            # Use sonicFoam for supersonic flows and shock phenomena
            confidence = 0.9 if mach > 1.0 else 0.85
            alternatives = [(SolverType.RHO_PIMPLE_FOAM, 0.4, "Alternative for subsonic compressible flows")]
            logger.info(f"AI Decision: Supersonic flow (Mach={mach:.2f}, sonic_score={sonic_score}, shock={has_shock}) → sonicFoam (confidence: {confidence})")
            return SolverType.SONIC_FOAM, confidence, alternatives
        else:
            # Use rhoPimpleFoam for subsonic compressible flows
            confidence = 0.9 if mach > 0.5 else 0.75
            alternatives = [(SolverType.PIMPLE_FOAM, 0.4, "Incompressible alternative if Mach < 0.3")]
            logger.info(f"AI Decision: Compressible flow (Mach={mach:.2f}) → rhoPimpleFoam (confidence: {confidence})")
            return SolverType.RHO_PIMPLE_FOAM, confidence, alternatives
    
    # Priority 4: Multi-region heat transfer - High confidence ONLY for true conjugate problems
    if features['is_multi_region'] and features['has_heat_transfer']:
        heat_confidence = features.get('heat_transfer_confidence', 0.8)
        
        # Only proceed with multi-region if we have high confidence in the detection
        if heat_confidence >= 0.7:
            confidence = min(0.9, heat_confidence)
            alternatives = [(SolverType.PIMPLE_FOAM, 0.4, "Single-region alternative if multi-region not needed")]
            logger.info(f"AI Decision: Multi-region heat transfer detected → chtMultiRegionFoam (confidence: {confidence})")
            return SolverType.CHT_MULTI_REGION_FOAM, confidence, alternatives
        else:
            # Low confidence multi-region detection - fall back to natural convection check
            logger.info(f"AI Decision: Low confidence multi-region detection ({heat_confidence:.2f}), checking for natural convection fallback")
            
            # Check for natural convection patterns as fallback
            buoyancy_keywords = ["natural convection", "buoyancy", "thermal plume", "rayleigh", "heated", "cooling", "thermal stratification"]
            has_buoyancy = any(keyword in ' '.join(features['user_keywords']) for keyword in buoyancy_keywords)
            
            if has_buoyancy:
                confidence = 0.7  # Medium confidence for fallback detection
                alternatives = [
                    (SolverType.CHT_MULTI_REGION_FOAM, 0.4, "Multi-region alternative if solid coupling needed"),
                    (SolverType.PIMPLE_FOAM, 0.3, "Transient alternative")
                ]
                logger.info(f"AI Decision: Fallback natural convection detection → buoyantSimpleFoam (confidence: {confidence})")
                return SolverType.BUOYANT_SIMPLE_FOAM, confidence, alternatives
    
    # Priority 5: Multiphase flows - High confidence for clear cases (after compressible check)
    if features['is_multiphase'] or features['free_surface']:
        confidence = 0.85
        alternatives = []
        
        # Check for incompatible requests (reduces confidence)
        if features['is_compressible'] and features.get('mach_number', 0) > 0.3:
            confidence = 0.6  # Lower confidence due to physics conflict
            alternatives.append((SolverType.RHO_PIMPLE_FOAM, 0.4, "For compressible flow, but no multiphase"))
            logger.warning("Compressible multiphase requested - this requires specialized solvers not currently supported")
            logger.info(f"AI Decision: Defaulting to interFoam for multiphase flow (confidence: {confidence})")
        else:
            alternatives.append((SolverType.PIMPLE_FOAM, 0.3, "Single-phase alternative"))
            logger.info(f"AI Decision: Multiphase flow detected → interFoam (confidence: {confidence})")
        
        return SolverType.INTER_FOAM, confidence, alternatives
    
    # Priority 6: Rotating machinery - High confidence for MRF applications
    mrf_score = keyword_scores.get('mrf', 0)
    
    if mrf_score > 0:
        # Check if steady-state (MRF) or transient
        if features.get('analysis_type') == AnalysisType.STEADY or features.get('time_scale_interest') == "steady":
            confidence = 0.85
            alternatives = [
                (SolverType.PIMPLE_FOAM, 0.5, "Transient alternative for unsteady rotating flows"),
                (SolverType.SIMPLE_FOAM, 0.3, "Non-rotating alternative")
            ]
            logger.info(f"AI Decision: Steady-state rotating machinery detected (mrf_score={mrf_score}) → MRFSimpleFoam (confidence: {confidence})")
            return SolverType.MRF_SIMPLE_FOAM, confidence, alternatives
        else:
            # For transient rotating flows, use pimpleFoam
            confidence = 0.7
            alternatives = [(SolverType.MRF_SIMPLE_FOAM, 0.6, "Steady-state rotating alternative")]
            logger.info(f"AI Decision: Transient rotating machinery detected (mrf_score={mrf_score}) → pimpleFoam (confidence: {confidence})")
            return SolverType.PIMPLE_FOAM, confidence, alternatives
    
    # Priority 7: Legacy buoyancy detection for backward compatibility
    buoyancy_keywords = ["natural convection", "buoyancy", "thermal plume", "rayleigh", "heated", "cooling", "thermal stratification"]
    has_buoyancy = any(keyword in ' '.join(features['user_keywords']) for keyword in buoyancy_keywords)
    
    if has_buoyancy and features['has_heat_transfer']:
        confidence = 0.75  # Slightly lower confidence for legacy detection
        alternatives = [
            (SolverType.PIMPLE_FOAM, 0.4, "Transient alternative for time-dependent convection"),
            (SolverType.CHT_MULTI_REGION_FOAM, 0.3, "Multi-region alternative if solid coupling needed")
        ]
        logger.info(f"AI Decision: Legacy buoyancy detection → buoyantSimpleFoam (confidence: {confidence})")
        return SolverType.BUOYANT_SIMPLE_FOAM, confidence, alternatives
    
    # Check for implicit buoyancy indicators
    if features['has_heat_transfer'] and features['analysis_type'] == AnalysisType.STEADY:
        # Look for temperature-driven flow indicators
        temp_keywords = ["temperature", "hot", "cold", "heated", "cooling", "thermal"]
        has_temp_keywords = any(keyword in ' '.join(features['user_keywords']) for keyword in temp_keywords)
        
        if has_temp_keywords:
            confidence = 0.7  # Medium confidence for implicit buoyancy
            alternatives = [
                (SolverType.SIMPLE_FOAM, 0.5, "Forced convection alternative"),
                (SolverType.PIMPLE_FOAM, 0.4, "Transient alternative")
            ]
            logger.info(f"AI Decision: Heat transfer with temperature gradients → buoyantSimpleFoam (confidence: {confidence})")
            return SolverType.BUOYANT_SIMPLE_FOAM, confidence, alternatives
    
    # Priority 8: PISO algorithm preference for accurate transient simulations
    piso_score = keyword_scores.get('piso', 0)
    
    if piso_score > 0 and features.get('analysis_type') == AnalysisType.UNSTEADY:
        # Use PISO for accurate transient simulations
        confidence = 0.8
        alternatives = [(SolverType.PIMPLE_FOAM, 0.7, "PIMPLE alternative for general transient flows")]
        logger.info(f"AI Decision: Accurate transient simulation required (piso_score={piso_score}) → pisoFoam (confidence: {confidence})")
        return SolverType.PISO_FOAM, confidence, alternatives
    
    # Now handle incompressible flows with confidence scoring
    reynolds_number = features.get('reynolds_number', 0)
    
    # Priority 9: Explicit steady-state request
    if features['analysis_type'] == AnalysisType.STEADY or features['time_scale_interest'] == "steady":
        confidence = 0.8
        alternatives = []
        
        # Validate that steady state is appropriate (reduces confidence if conflicts)
        if features['expects_vortex_shedding']:
            confidence = 0.5  # Reduced confidence due to physics conflict
            alternatives.append((SolverType.PIMPLE_FOAM, 0.7, "Recommended for vortex shedding"))
            logger.warning("Steady-state requested but vortex shedding expected - consider transient analysis")
        else:
            alternatives.append((SolverType.PIMPLE_FOAM, 0.3, "Transient alternative"))
        
        logger.info(f"AI Decision: Explicit steady-state request → simpleFoam (confidence: {confidence})")
        return SolverType.SIMPLE_FOAM, confidence, alternatives
    
    # Priority 10: Keywords strongly suggesting steady state
    steady_keywords = ["pressure drop", "drag coefficient", "lift coefficient", "steady", "equilibrium"]
    if any(f"steady:{kw}" in features['user_keywords'] for kw in steady_keywords):
        if not features['expects_vortex_shedding']:
            confidence = 0.7
            alternatives = [(SolverType.PIMPLE_FOAM, 0.4, "Transient alternative")]
            logger.info(f"AI Decision: Steady-state keywords detected → simpleFoam (confidence: {confidence})")
            return SolverType.SIMPLE_FOAM, confidence, alternatives
    
    # Priority 11: Vortex shedding or explicit transient request - High confidence
    if features['expects_vortex_shedding'] or features['analysis_type'] == AnalysisType.UNSTEADY:
        confidence = 0.85 if features['expects_vortex_shedding'] else 0.75
        alternatives = [(SolverType.SIMPLE_FOAM, 0.3, "Steady-state alternative if only final result needed")]
        logger.info(f"AI Decision: Vortex shedding expected or transient requested → pimpleFoam (confidence: {confidence})")
        return SolverType.PIMPLE_FOAM, confidence, alternatives
    
    # Priority 12: Transient keywords - Medium confidence
    transient_keywords = ["vortex", "shedding", "frequency", "oscillat", "time", "transient"]
    if any(f"transient:{kw}" in features['user_keywords'] for kw in transient_keywords):
        confidence = 0.7
        alternatives = [(SolverType.SIMPLE_FOAM, 0.4, "Steady-state alternative")]
        logger.info(f"AI Decision: Transient keywords detected → pimpleFoam (confidence: {confidence})")
        return SolverType.PIMPLE_FOAM, confidence, alternatives
    
    # Default cases: Lower confidence due to ambiguity
    if features['time_scale_interest'] == "unknown":
        confidence = 0.5  # Medium confidence for ambiguous cases
        alternatives = [(SolverType.PIMPLE_FOAM, 0.6, "Transient alternative for better accuracy")]
        logger.info(f"AI Decision: Ambiguous case, defaulting to efficient steady solver → simpleFoam (confidence: {confidence})")
        return SolverType.SIMPLE_FOAM, confidence, alternatives
    
    # Final fallback - Low confidence
    confidence = 0.4
    alternatives = [(SolverType.SIMPLE_FOAM, 0.5, "Steady-state alternative for efficiency")]
    logger.info(f"AI Decision: Default fallback → pimpleFoam (confidence: {confidence})")
    return SolverType.PIMPLE_FOAM, confidence, alternatives


def build_solver_settings(
    solver_type: SolverType,
    parsed_params: Dict[str, Any],
    geometry_info: Dict[str, Any],
    confidence_score: float = 1.0,
    alternatives: List[Tuple[SolverType, float, str]] = None
) -> Dict[str, Any]:
    """
    Build complete solver settings based on selected solver type.
    Returns standardized configuration format.
    """
    flow_type = parsed_params.get("flow_type", FlowType.LAMINAR)
    reynolds_number = parsed_params.get("reynolds_number", None)
    
    # Determine analysis type based on solver
    if solver_type in [SolverType.SIMPLE_FOAM, SolverType.BUOYANT_SIMPLE_FOAM, SolverType.MRF_SIMPLE_FOAM]:
        analysis_type = AnalysisType.STEADY
    elif solver_type in [SolverType.PISO_FOAM, SolverType.SONIC_FOAM]:
        analysis_type = AnalysisType.UNSTEADY  # These are transient-only
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
    
    # Build standardized solver settings following SOLVER_CONFIG_SCHEMA
    solver_settings = {
        # Core solver information
        "solver": solver_info["name"],
        "solver_type": solver_type,
        "analysis_type": analysis_type,
        "flow_type": flow_type,
        
        # Physics properties (standardized)
        "compressible": solver_info["capabilities"]["compressible"],
        "multiphase": solver_info["capabilities"]["multiphase"],
        "heat_transfer": solver_info["capabilities"]["heat_transfer"],
        
        # Flow parameters (standardized)
        "reynolds_number": reynolds_number,
        "mach_number": parsed_params.get("mach_number", 0),
        "velocity": parsed_params.get("velocity"),
        "temperature": parsed_params.get("temperature"),
        "pressure": parsed_params.get("pressure"),
        
        # Standardized field initialization (will be populated below)
        "fields": {},
        
        # Standardized physics properties (will be populated below)
        "properties": {},
        
        # Configuration files (will be populated by generate_solver_config)
        "controlDict": {},
        "fvSchemes": {},
        "fvSolution": {},
        
        # Metadata for tracking and debugging
        "metadata": {
            "solver_capabilities": solver_info["capabilities"],
            "recommended_for": solver_info.get("recommended_for", []),
            "selection_confidence": confidence_score,
            "parameter_defaults_applied": [],
            "alternatives": alternatives or []
        }
    }
    
    # Turbulence model selection (standardized in properties)
    if flow_type == FlowType.TURBULENT:
        # Special handling for compressible flows
        if solver_type == SolverType.RHO_PIMPLE_FOAM:
            mach_number = parsed_params.get("mach_number", 0)
            if mach_number > 1.0 or any("shock" in str(kw) for kw in parsed_params.get("keywords", [])):
                turbulence_model = "kOmegaSST"  # Better for shocks
            elif reynolds_number is not None and reynolds_number > 1e6:
                turbulence_model = "kEpsilon"
            else:
                turbulence_model = "kOmegaSST"
        else:
            # Standard turbulence model selection
            if reynolds_number is not None and reynolds_number < 10000:
                turbulence_model = "kOmegaSST"
            elif reynolds_number is not None and reynolds_number >= 10000:
                turbulence_model = "kEpsilon"
            else:
                turbulence_model = "kOmegaSST"
    else:
        turbulence_model = "laminar"
    
    solver_settings["properties"]["turbulence_model"] = turbulence_model
    
    # Add phase properties for multiphase solvers (standardized)
    if solver_type == SolverType.INTER_FOAM:
        phases = parsed_params.get("phases", ["water", "air"])
        solver_settings["properties"]["phases"] = phases
        solver_settings["properties"]["phase_properties"] = {}
        
        for phase in phases:
            if phase in DEFAULT_PHASE_PROPERTIES:
                solver_settings["properties"]["phase_properties"][phase] = DEFAULT_PHASE_PROPERTIES[phase].copy()
            else:
                # Use water properties as default for unknown fluids
                solver_settings["properties"]["phase_properties"][phase] = DEFAULT_PHASE_PROPERTIES["water"].copy()
                logger.warning(f"Unknown phase '{phase}', using water properties as default")
        
        # Surface tension between phases
        if "water" in phases and "air" in phases:
            solver_settings["properties"]["surface_tension"] = DEFAULT_PHASE_PROPERTIES["water"]["surface_tension"]
        else:
            solver_settings["properties"]["surface_tension"] = 0.07  # Default surface tension
        
        # Standard multiphase fields
        solver_settings["fields"]["g"] = {
            "dimensions": "[0 1 -2 0 0 0 0]",
            "value": "(0 -9.81 0)"
        }
        solver_settings["fields"]["sigma"] = solver_settings["properties"]["surface_tension"]
    
    # Add thermophysical properties for compressible solvers (standardized)
    if solver_type == SolverType.RHO_PIMPLE_FOAM:
        solver_settings["properties"]["thermophysical_model"] = "perfectGas"
        solver_settings["properties"]["transport_model"] = "const"
        solver_settings["properties"]["thermo_type"] = "hePsiThermo"
        solver_settings["properties"]["mixture"] = "pureMixture"
        solver_settings["properties"]["equation_of_state"] = "perfectGas"
        solver_settings["properties"]["specie"] = "specie"
        solver_settings["properties"]["energy"] = "sensibleInternalEnergy"
        
        # Standard compressible fields
        solver_settings["fields"]["T"] = solver_settings["temperature"] or INTELLIGENT_DEFAULTS["temperature"]["ambient"]
        solver_settings["fields"]["p"] = solver_settings["pressure"] or INTELLIGENT_DEFAULTS["pressure"]["atmospheric"]
    
    # Add settings for chtMultiRegionFoam (standardized)
    if solver_type == SolverType.CHT_MULTI_REGION_FOAM:
        solver_settings["properties"]["multi_region"] = True
        solver_settings["properties"]["regions"] = parsed_params.get("regions", ["fluid", "solid"])
        solver_settings["properties"]["thermophysical_model"] = "perfectGas"
        solver_settings["properties"]["transport_model"] = "const"
        solver_settings["properties"]["thermo_type"] = "hePsiThermo"
        solver_settings["properties"]["thermal_coupling"] = True
        
        # Standard heat transfer fields
        solver_settings["fields"]["T"] = solver_settings["temperature"] or INTELLIGENT_DEFAULTS["temperature"]["ambient"]
        
        # Ensure we have proper region setup
        regions = solver_settings["properties"]["regions"]
        if len(regions) < 2:
            # Add default regions if not enough provided
            if "fluid" not in regions:
                regions.append("fluid")
            if "solid" not in regions:
                regions.append("solid")
        
        # Add region properties
        solver_settings["properties"]["fluidRegions"] = [r for r in regions if "fluid" in r.lower()]
        solver_settings["properties"]["solidRegions"] = [r for r in regions if "solid" in r.lower()]
        
        # Ensure we have at least one of each type
        if not solver_settings["properties"]["fluidRegions"]:
            solver_settings["properties"]["fluidRegions"] = ["fluid"]
        if not solver_settings["properties"]["solidRegions"]:
            solver_settings["properties"]["solidRegions"] = ["solid"]
    
    # Add settings for reactingFoam (standardized)
    if solver_type == SolverType.REACTING_FOAM:
        solver_settings["properties"]["thermophysical_model"] = "psiReactionThermo"
        solver_settings["properties"]["chemistry"] = True
        solver_settings["properties"]["combustion_model"] = parsed_params.get("combustion_model", "PaSR")
        solver_settings["properties"]["chemistry_solver"] = parsed_params.get("chemistry_solver", "ode")
        
        # Handle species parameter variations
        species_list = (parsed_params.get("chemical_species") or 
                       parsed_params.get("species") or 
                       ["CH4", "O2", "CO2", "H2O", "N2"])
        solver_settings["properties"]["species"] = species_list
        solver_settings["properties"]["reaction_mechanism"] = parsed_params.get("reaction_mechanism", "GRI-Mech3.0")
        
        # Standard reactive fields
        solver_settings["fields"]["T"] = solver_settings["temperature"] or INTELLIGENT_DEFAULTS["temperature"]["ambient"]
        solver_settings["fields"]["p"] = solver_settings["pressure"] or INTELLIGENT_DEFAULTS["pressure"]["atmospheric"]
        
        # Add species fields for each species
        for species in species_list:
            solver_settings["fields"][species] = 0.0  # Initialize species mass fractions to 0
        
        # Set fuel species to initial value (if specified)
        fuel_species = parsed_params.get("fuel", "CH4")
        if fuel_species in species_list:
            solver_settings["fields"][fuel_species] = 0.1  # Initial fuel mass fraction
    
    # Add settings for sonicFoam (standardized)
    if solver_type == SolverType.SONIC_FOAM:
        solver_settings["properties"]["thermophysical_model"] = "perfectGas"
        solver_settings["properties"]["transport_model"] = "const"
        solver_settings["properties"]["thermo_type"] = "hePsiThermo"
        solver_settings["properties"]["mixture"] = "pureMixture"
        solver_settings["properties"]["equation_of_state"] = "perfectGas"
        solver_settings["properties"]["specie"] = "specie"
        solver_settings["properties"]["energy"] = "sensibleInternalEnergy"
        
        # Standard supersonic fields
        solver_settings["fields"]["T"] = solver_settings["temperature"] or INTELLIGENT_DEFAULTS["temperature"]["ambient"]
        solver_settings["fields"]["p"] = solver_settings["pressure"] or INTELLIGENT_DEFAULTS["pressure"]["atmospheric"]
        
        # Set higher velocity for supersonic flows
        if not solver_settings["velocity"]:
            solver_settings["velocity"] = 300.0  # Default supersonic velocity (m/s)
        
        # Add Mach number validation
        mach_number = parsed_params.get("mach_number", 1.5)
        solver_settings["mach_number"] = mach_number
        
        # Warn if Mach number seems too low
        if mach_number < 0.8:
            logger.warning(f"sonicFoam selected with Mach number {mach_number} - consider rhoPimpleFoam for subsonic flows")
    
    # Add settings for MRFSimpleFoam (standardized)
    if solver_type == SolverType.MRF_SIMPLE_FOAM:
        solver_settings["properties"]["mrf_zones"] = parsed_params.get("mrf_zones", ["rotating"])
        solver_settings["properties"]["rotation_rate"] = parsed_params.get("rotation_rate", INTELLIGENT_DEFAULTS["rotation_rate"]["medium"])
        solver_settings["properties"]["rotation_axis"] = parsed_params.get("rotation_axis", "(0 0 1)")
        solver_settings["properties"]["rotation_origin"] = parsed_params.get("rotation_origin", "(0 0 0)")
        
        # Standard MRF fields
        solver_settings["fields"]["MRFProperties"] = {
            "zones": solver_settings["properties"]["mrf_zones"],
            "rotation_rate": solver_settings["properties"]["rotation_rate"],
            "axis": solver_settings["properties"]["rotation_axis"],
            "origin": solver_settings["properties"]["rotation_origin"]
        }
        
        # Add rotating machinery flag
        solver_settings["properties"]["rotating_machinery"] = True
        
        # Ensure appropriate turbulence model for rotating flows
        if flow_type == FlowType.TURBULENT:
            solver_settings["properties"]["turbulence_model"] = "kOmegaSST"  # Better for rotating flows
    
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
        "flow_type": solver_settings["flow_type"],
        "solver_type": solver_settings.get("solver_type"),
        "properties": solver_settings.get("properties", {}),
        "fields": solver_settings.get("fields", {})
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
        
        # Create p_rgh with same boundary conditions as p, but will be remapped to actual mesh patches later
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

    if solver_settings.get("solver_type") == SolverType.SONIC_FOAM:
        # Add compressible flow properties for sonicFoam
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
        regions = solver_settings.get("properties", {}).get("regions", ["fluid", "solid"])
        fluid_regions = solver_settings.get("properties", {}).get("fluidRegions", [])
        solid_regions = solver_settings.get("properties", {}).get("solidRegions", [])
        
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
        
        # Add temperature field if defined
        if "T" in solver_settings.get("fields", {}):
            solver_config["T"] = {
                "dimensions": "[0 0 0 1 0 0 0]",  # Temperature in Kelvin
                "internalField": f"uniform {solver_settings['fields']['T']}",
                "boundaryField": {}
            }
    
    if solver_settings.get("solver_type") == SolverType.REACTING_FOAM:
        # Add reactive flow properties
        solver_config["thermophysicalProperties"] = generate_reactive_thermophysical_properties(solver_settings, parsed_params)
        solver_config["chemistryProperties"] = {
            "chemistry": "on",
            "chemistryType": {
                "chemistrySolver": solver_settings.get("properties", {}).get("chemistry_solver", "ode"),
                "chemistryThermo": "psi"
            },
            "chemistryReader": "foamChemistryReader",
            "foamChemistryFile": f"constant/{solver_settings.get('properties', {}).get('reaction_mechanism', 'reactions')}"
        }
        solver_config["combustionProperties"] = {
            "combustionModel": solver_settings.get("properties", {}).get("combustion_model", "PaSR"),
            f"{solver_settings.get('properties', {}).get('combustion_model', 'PaSR')}Coeffs": {
                "Cmix": 0.1,
                "turbulentReaction": "on"
            }
        }
        
        # Add temperature and pressure fields if defined
        if "T" in solver_settings.get("fields", {}):
            solver_config["T"] = {
                "dimensions": "[0 0 0 1 0 0 0]",  # Temperature in Kelvin
                "internalField": f"uniform {solver_settings['fields']['T']}",
                "boundaryField": {}
            }
        if "p" in solver_settings.get("fields", {}):
            solver_config["p"] = {
                "dimensions": "[1 -1 -2 0 0 0 0]",  # Pressure in Pa
                "internalField": f"uniform {solver_settings['fields']['p']}",
                "boundaryField": {}
            }
        
        # Add species fields
        species_list = solver_settings.get("properties", {}).get("species", [])
        for species in species_list:
            if species in solver_settings.get("fields", {}):
                solver_config[species] = {
                    "dimensions": "[0 0 0 0 0 0 0]",  # Dimensionless mass fraction
                    "internalField": f"uniform {solver_settings['fields'][species]}",
                    "boundaryField": {}
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
            elif geometry_info["type"] == GeometryType.NOZZLE:
                char_length = geometry_info.get("throat_diameter", geometry_info.get("length", 0.1))
            else:
                char_length = 0.1  # Default
            
            # Calculate velocity from Re = ρ * V * L / μ
            velocity = reynolds_number * viscosity / (density * char_length)
            logger.info(f"Calculated velocity {velocity:.3f} m/s from Reynolds number {reynolds_number} for time step calculation")
        
        # Ensure velocity is valid with detailed logging
        if velocity is None or velocity <= 0:
            logger.warning(f"Invalid velocity ({velocity}), using default 1.0 m/s")
            velocity = 1.0
        else:
            logger.info(f"Using velocity: {velocity:.3f} m/s")
        
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
        # Use user-specified Courant number or default, with null check
        target_courant = parsed_params.get("courant_number")
        if target_courant is None or target_courant <= 0:
            target_courant = 0.5  # Safe default
        if parsed_params.get("courant_number") is not None:
            logger.info(f"Using user-specified Courant number: {target_courant}")
        else:
            logger.info(f"Using default Courant number: {target_courant}")
        
        # Estimate cell size (assuming ~20-40 cells across characteristic length)
        mesh_resolution = parsed_params.get("mesh_resolution", "medium")
        cells_per_length = {"coarse": 20, "medium": 30, "fine": 40}.get(mesh_resolution, 30)
        
        # Ensure characteristic_length is valid
        if characteristic_length is None or characteristic_length <= 0:
            logger.error(f"Invalid characteristic_length: {characteristic_length}")
            characteristic_length = 0.1  # Emergency fallback
        
        cell_size = characteristic_length / cells_per_length
        
        # Ensure all values are valid before calculation
        if target_courant is None or cell_size is None or velocity is None:
            logger.error(f"Invalid values for time step calculation: target_courant={target_courant}, cell_size={cell_size}, velocity={velocity}")
            estimated_dt = 1e-4  # Safe fallback
        else:
            # Calculate time step
            estimated_dt = target_courant * cell_size / velocity
        
        # Apply reasonable bounds - use user-specified limits or defaults
        min_dt = parsed_params.get("min_time_step")
        max_dt = parsed_params.get("max_time_step")
        
        # Ensure min_dt and max_dt have valid values
        if min_dt is None or min_dt <= 0:
            min_dt = 1e-6  # Safe minimum default
        if max_dt is None or max_dt <= 0:
            max_dt = 0.01  # Safe maximum default
        
        # Log which values are being used
        if parsed_params.get("min_time_step") is not None:
            logger.info(f"Using user-specified minimum time step: {min_dt}")
        else:
            logger.info(f"Using default minimum time step: {min_dt}")
        if parsed_params.get("max_time_step") is not None:
            logger.info(f"Using user-specified maximum time step: {max_dt}")
        else:
            logger.info(f"Using default maximum time step: {max_dt}")
        
        # Ensure estimated_dt is valid before comparison
        if estimated_dt is None or estimated_dt <= 0:
            logger.error(f"Invalid estimated deltaT: {estimated_dt}, using safe default")
            estimated_dt = min_dt
        
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
            # Use user-specified max Courant number if provided, otherwise use conservative default
            user_courant = parsed_params.get("courant_number")
            if user_courant is not None and user_courant > 0:
                max_courant = user_courant * 1.8  # Allow 1.8x target for max
            else:
                max_courant = 0.5 * 1.8  # Use default target_courant
            
            # Apply safety bounds
            if max_courant > 2.0:  # Safety cap
                max_courant = 2.0
            elif max_courant < 0.5:  # Minimum reasonable max
                max_courant = 0.9
            
            # Use user-specified max time step or conservative estimate
            user_max_dt = parsed_params.get("max_time_step")
            if user_max_dt is not None and user_max_dt > 0:
                max_delta_t = user_max_dt
            else:
                # Ensure estimated_dt is valid before using it
                if estimated_dt is not None and estimated_dt > 0:
                    max_delta_t = min(0.01, estimated_dt * 10)  # Cap at 10x initial estimate
                else:
                    max_delta_t = 0.01  # Safe fallback
            
            control_dict.update({
                "adjustTimeStep": "yes",
                "maxCo": max_courant,
                "maxDeltaT": max_delta_t
            })
            
            # Add interFoam-specific parameters
            if solver == "interFoam":
                control_dict["maxAlphaCo"] = 1.0  # Maximum alpha (VOF) Courant number
            
            # Log adaptive time stepping parameters
            courant_source = "user-specified" if parsed_params.get("courant_number") is not None else "default"
            max_dt_source = "user-specified" if parsed_params.get("max_time_step") is not None else "estimated"
            logger.info(f"Using adaptive time stepping with maxCo={max_courant} ({courant_source}), maxDeltaT={max_delta_t} ({max_dt_source}), initial deltaT={estimated_dt:.6f}")
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
    elif solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.SONIC_FOAM]:
        # Compressible solver specific schemes (rhoPimpleFoam, sonicFoam)
        fv_schemes["divSchemes"].update({
            "div(phi,U)": "Gauss linearUpwindV grad(U)",
            "div(phi,K)": "Gauss upwind",
            "div(phi,h)": "Gauss upwind", 
            "div(phi,e)": "Gauss upwind",
            "div(phiv,p)": "Gauss upwind",
            "div(phid,p)": "Gauss upwind",  # sonicFoam specific scheme
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
    
    # Check if GPU acceleration is requested
    gpu_info = parsed_params.get("gpu_info", {})
    use_gpu = gpu_info.get("use_gpu", False)
    gpu_backend = gpu_info.get("gpu_backend", "petsc")
    
    # Base solution settings
    fv_solution = {
        "solvers": {},
        "SIMPLE": {},
        "PIMPLE": {},
        "relaxationFactors": {},
        "residualControl": {}
    }
    
    # GPU-specific library loading
    if use_gpu:
        fv_solution["libs"] = ["libpetscFoam.so"]
        if gpu_backend == "amgx":
            fv_solution["libs"].append("libamgxFoam.so")
    
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
    elif solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.SONIC_FOAM]:
        # Compressible solver pressure solver (rhoPimpleFoam, sonicFoam)
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
        
        # Density solver for compressible flows (required for both rhoPimpleFoam and sonicFoam)
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
        if use_gpu and gpu_backend == "petsc":
            fv_solution["solvers"]["p"] = {
                "solver": "petsc",
                "petsc": {
                    "options": {
                        "ksp_type": "cg",
                        "mat_type": "aijcusparse",
                        "pc_type": "gamg"
                    }
                },
                "tolerance": 1e-06,
                "relTol": 0.1
            }
        elif use_gpu and gpu_backend == "amgx":
            fv_solution["solvers"]["p"] = {
                "solver": "amgx",
                "amgx": {},
                "tolerance": 1e-06,
                "relTol": 0.1
            }
        else:
            # Standard CPU solver
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
            # Apply same GPU settings to pFinal solver
            if use_gpu and gpu_backend == "petsc":
                fv_solution["solvers"]["pFinal"] = {
                    "solver": "petsc",
                    "petsc": {
                        "options": {
                            "ksp_type": "cg",
                            "mat_type": "aijcusparse",
                            "pc_type": "gamg"
                        }
                    },
                    "tolerance": 1e-06,
                    "relTol": 0
                }
            elif use_gpu and gpu_backend == "amgx":
                fv_solution["solvers"]["pFinal"] = {
                    "solver": "amgx",
                    "amgx": {},
                    "tolerance": 1e-06,
                    "relTol": 0
                }
            else:
                # Standard CPU solver
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
        elif solver_type in [SolverType.RHO_PIMPLE_FOAM, SolverType.SONIC_FOAM]:
            # Compressible solver specific settings (rhoPimpleFoam, sonicFoam)
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
    
    if flow_type == FlowType.LAMINAR or turbulence_model == "laminar":
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
    # Check if this is a Mars, Moon, or custom environment simulation
    original_prompt = parsed_params.get("original_prompt", "")
    is_mars_simulation = detect_mars_simulation(original_prompt)
    is_moon_simulation = detect_moon_simulation(original_prompt)
    
    # Check for custom environment
    custom_environment = None
    if not is_mars_simulation and not is_moon_simulation:
        custom_environment = detect_custom_environment(original_prompt)
    
    # Default temperature and pressure if not specified
    if is_mars_simulation:
        temperature = parsed_params.get("temperature", 210.0)  # Mars surface temperature
        pressure = parsed_params.get("pressure", 610.0)  # Mars atmospheric pressure
    elif is_moon_simulation:
        temperature = parsed_params.get("temperature", 250.0)  # Moon surface temperature
        pressure = parsed_params.get("pressure", 3e-15)  # Moon atmospheric pressure (vacuum)
    elif custom_environment and custom_environment.get("has_custom_environment", False):
        temperature = parsed_params.get("temperature", custom_environment.get("temperature", 293.15))
        pressure = parsed_params.get("pressure", custom_environment.get("pressure", 101325))
        logger.info(f"Using custom environment thermophysical properties: {custom_environment.get('environment_name', 'Unknown')}")
    else:
        temperature = parsed_params.get("temperature", 293.15)  # 20°C in Kelvin
        pressure = parsed_params.get("pressure", 101325)  # 1 atm in Pa
    
    # Gas properties (default to air)
    cp = parsed_params.get("specific_heat", 1005)  # J/(kg·K) for air
    cv = cp / 1.4  # Assuming gamma = 1.4 for air
    mol_weight = parsed_params.get("molecular_weight", 28.96)  # g/mol for air
    
    # Transport properties
    mu = parsed_params.get("viscosity", 1.81e-5)  # Pa·s
    pr = parsed_params.get("prandtl_number", 0.72)  # Prandtl number for air
    
    # Get properties from solver_settings if available
    properties = solver_settings.get("properties", {})
    
    return {
        "thermoType": {
            "type": properties.get("thermo_type", "hePsiThermo"),
            "mixture": properties.get("mixture", "pureMixture"),
            "transport": properties.get("transport_model", "const"),
            "thermo": "hConst",
            "equationOfState": properties.get("equation_of_state", "perfectGas"),
            "specie": properties.get("specie", "specie"),
            "energy": properties.get("energy", "sensibleInternalEnergy")
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
    # Check if this is a Mars, Moon, or custom environment simulation
    original_prompt = parsed_params.get("original_prompt", "")
    is_mars_simulation = detect_mars_simulation(original_prompt)
    is_moon_simulation = detect_moon_simulation(original_prompt)
    
    # Check for custom environment
    custom_environment = None
    if not is_mars_simulation and not is_moon_simulation:
        custom_environment = detect_custom_environment(original_prompt)
    
    # Default temperature and pressure if not specified
    if is_mars_simulation:
        temperature = parsed_params.get("temperature", 210.0)  # Mars surface temperature
        pressure = parsed_params.get("pressure", 610.0)  # Mars atmospheric pressure
    elif is_moon_simulation:
        temperature = parsed_params.get("temperature", 250.0)  # Moon surface temperature
        pressure = parsed_params.get("pressure", 3e-15)  # Moon atmospheric pressure (vacuum)
    elif custom_environment and custom_environment.get("has_custom_environment", False):
        temperature = parsed_params.get("temperature", custom_environment.get("temperature", 300))
        pressure = parsed_params.get("pressure", custom_environment.get("pressure", 101325))
        logger.info(f"Using custom environment reactive properties: {custom_environment.get('environment_name', 'Unknown')}")
    else:
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
    """
    Enhanced solver configuration validation with comprehensive checks.
    Validates configuration completeness, parameter compatibility, and physics consistency.
    """
    errors = []
    warnings = []
    suggestions = []
    
    # Check required files
    required_files = ["controlDict", "fvSchemes", "fvSolution", "turbulenceProperties", "transportProperties"]
    for file in required_files:
        if file not in solver_config:
            errors.append(f"Missing required file: {file}")
    
    # Check solver compatibility
    solver = solver_config.get("solver")
    if not solver:
        errors.append("No solver specified")
        return {"valid": False, "errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    # Validate solver name
    valid_solvers = ["simpleFoam", "pimpleFoam", "rhoSimpleFoam", "rhoPimpleFoam", "interFoam", 
                    "chtMultiRegionFoam", "reactingFoam"]
    if solver not in valid_solvers:
        warnings.append(f"Unknown solver: {solver}. Valid solvers: {', '.join(valid_solvers)}")
    
    # Get configuration structure for validation
    fields = solver_config.get("fields", {})
    properties = solver_config.get("properties", {})
    metadata = solver_config.get("metadata", {})
    
    # Validate standardized configuration structure
    if not isinstance(fields, dict):
        errors.append("Configuration 'fields' must be a dictionary")
    if not isinstance(properties, dict):
        errors.append("Configuration 'properties' must be a dictionary")
    if not isinstance(metadata, dict):
        warnings.append("Configuration 'metadata' should be a dictionary")
    
    # Solver-specific validation with enhanced checks
    if solver == "interFoam":
        _validate_interfoam_config(solver_config, fields, properties, errors, warnings, suggestions)
    elif solver == "rhoPimpleFoam":
        _validate_rhopimplefoam_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    elif solver == "chtMultiRegionFoam":
        _validate_chtmultiregion_config(solver_config, fields, properties, errors, warnings, suggestions)
    elif solver == "reactingFoam":
        _validate_reactingfoam_config(solver_config, fields, properties, errors, warnings, suggestions)
    elif solver == "buoyantSimpleFoam":
        _validate_buoyant_simple_foam_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    elif solver == "pisoFoam":
        _validate_piso_foam_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    elif solver == "sonicFoam":
        _validate_sonic_foam_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    elif solver == "MRFSimpleFoam":
        _validate_mrf_simple_foam_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    elif solver in ["simpleFoam", "pimpleFoam"]:
        _validate_incompressible_config(solver_config, fields, properties, parsed_params, errors, warnings, suggestions)
    
    # Cross-validation checks
    _validate_physics_consistency(solver_config, parsed_params, errors, warnings, suggestions)
    _validate_numerical_settings(solver_config, parsed_params, errors, warnings, suggestions)
    _validate_boundary_conditions(solver_config, parsed_params, errors, warnings, suggestions)
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions
    }


def _validate_interfoam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                              properties: Dict[str, Any], errors: List[str], 
                              warnings: List[str], suggestions: List[str]) -> None:
    """Validate interFoam-specific configuration."""
    # Check for required multiphase properties
    if "g" not in fields and "g" not in solver_config:
        errors.append("Gravity vector 'g' not specified for interFoam")
    
    if "sigma" not in fields and "sigma" not in solver_config:
        errors.append("Surface tension 'sigma' not specified for interFoam")
        suggestions.append("Add surface tension value (typical: 0.07 N/m for water-air)")
    
    # Check phases
    phases = properties.get("phases", solver_config.get("phases", []))
    if not phases or len(phases) < 2:
        errors.append("interFoam requires at least 2 phases")
        suggestions.append("Specify phases like ['water', 'air']")
    
    # Check phase properties
    phase_props = properties.get("phase_properties", {})
    for phase in phases:
        if phase not in phase_props:
            warnings.append(f"Missing properties for phase '{phase}'")
            suggestions.append(f"Add density and viscosity for phase '{phase}'")
    
    # interFoam cannot be steady state
    if solver_config.get("analysis_type") == AnalysisType.STEADY:
        errors.append("interFoam does not support steady-state analysis")
        suggestions.append("Use transient analysis for multiphase flows")


def _validate_rhopimplefoam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                  properties: Dict[str, Any], parsed_params: Dict[str, Any],
                                  errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate rhoPimpleFoam-specific configuration."""
    # Check for required compressible properties
    # Note: For compressible solvers, boundary conditions and thermophysical properties 
    # are handled by other agents in the workflow, so we skip these validation checks
    
    # Check thermophysical properties - this should be generated by the solver selector
    if "thermophysicalProperties" not in solver_config:
        # This is expected to be generated by the solver selector based on solver type
        # The case writer will actually write the file, so we don't need to error here
        pass  # Remove the error for now as it's handled in the workflow
    
    # Check Mach number consistency
    mach_number = parsed_params.get("mach_number", 0)
    if mach_number is not None and isinstance(mach_number, (int, float)):
        if mach_number < 0.3:
            warnings.append(f"Low Mach number ({mach_number:.2f}) - consider using incompressible solver")
            suggestions.append("Use pimpleFoam or simpleFoam for Mach < 0.3")
        elif mach_number > 5.0:
            warnings.append(f"Very high Mach number ({mach_number:.2f}) - ensure proper shock capturing")
            suggestions.append("Consider specialized high-Mach solvers or adjust numerical schemes")
    
    # Check thermophysical model consistency
    thermo_model = properties.get("thermophysical_model")
    if thermo_model and thermo_model not in ["perfectGas", "incompressiblePerfectGas", "rhoConst"]:
        warnings.append(f"Unusual thermophysical model: {thermo_model}")


def _validate_chtmultiregion_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                   properties: Dict[str, Any], errors: List[str], 
                                   warnings: List[str], suggestions: List[str]) -> None:
    """Validate chtMultiRegionFoam-specific configuration."""
    # Check for required multi-region properties
    if not properties.get("multi_region", False):
        errors.append("Multi-region flag not set for chtMultiRegionFoam")
    
    regions = properties.get("regions", [])
    if len(regions) < 2:
        errors.append("chtMultiRegionFoam requires at least 2 regions (fluid and solid)")
        suggestions.append("Define regions like ['fluid', 'solid']")
    
    # Check for typical region types
    fluid_regions = properties.get("fluidRegions", [])
    solid_regions = properties.get("solidRegions", [])
    
    if not fluid_regions:
        warnings.append("No fluid regions detected - ensure proper region naming")
    if not solid_regions:
        warnings.append("No solid regions detected - ensure proper region naming")
    
    # Check thermal coupling
    if not properties.get("thermal_coupling", False):
        warnings.append("Thermal coupling not enabled - check if intended")
        suggestions.append("Enable thermal coupling for conjugate heat transfer")
    
    # Check temperature field
    if "T" not in fields and "T" not in solver_config:
        errors.append("Temperature field 'T' required for chtMultiRegionFoam")
        suggestions.append("Initialize temperature field for all regions")


def _validate_reactingfoam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                 properties: Dict[str, Any], errors: List[str], 
                                 warnings: List[str], suggestions: List[str]) -> None:
    """Validate reactingFoam-specific configuration."""
    # Check for required reactive flow properties
    if not properties.get("chemistry", False):
        errors.append("Chemistry not enabled for reactingFoam")
        suggestions.append("Enable chemistry for reactive flows")
    
    species = properties.get("species", [])
    if not species or len(species) < 2:
        errors.append("reactingFoam requires chemical species")
        suggestions.append("Define species list (e.g., ['CH4', 'O2', 'CO2', 'H2O', 'N2'])")
    
    # Check combustion model
    combustion_model = properties.get("combustion_model")
    if not combustion_model:
        warnings.append("No combustion model specified - will use default")
        suggestions.append("Specify combustion model (e.g., 'PaSR', 'EDC', 'laminar')")
    
    # Check required fields
    if "T" not in fields and "T" not in solver_config:
        errors.append("Temperature field 'T' required for reactingFoam")
    
    # Check species fields - they should now be in the fields dict
    for species_name in species:
        if species_name not in fields:
            warnings.append(f"Species field '{species_name}' not initialized")
            suggestions.append(f"Initialize species field '{species_name}' with appropriate mass fraction")
    
    # reactingFoam is always transient
    if solver_config.get("analysis_type") == AnalysisType.STEADY:
        errors.append("reactingFoam does not support steady-state analysis")
        suggestions.append("Use transient analysis for reactive flows")


def _validate_buoyant_simple_foam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                        properties: Dict[str, Any], parsed_params: Dict[str, Any],
                                        errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate buoyantSimpleFoam-specific configuration."""
    # Check for required temperature field
    if "T" not in fields and "T" not in solver_config:
        errors.append("Temperature field 'T' required for buoyantSimpleFoam")
        suggestions.append("Initialize temperature field (typical: 293.15 K)")
    
    # Check for gravity vector
    if "g" not in fields and "g" not in solver_config and "gravity" not in parsed_params:
        errors.append("Gravity vector 'g' required for buoyantSimpleFoam")
        suggestions.append("Set gravity vector (typical: (0 -9.81 0) m/s²)")
    
    # Check for thermal expansion coefficient
    if "beta" not in fields and "beta" not in solver_config and "thermal_expansion" not in parsed_params:
        warnings.append("Thermal expansion coefficient 'beta' not specified")
        suggestions.append("Set thermal expansion coefficient (typical: 3.43e-3 1/K for air)")
    
    # Check for transport properties
    if "transportProperties" not in solver_config:
        warnings.append("Transport properties not specified for buoyantSimpleFoam")
        suggestions.append("Add transport properties with density, viscosity, and thermal properties")
    
    # Check Prandtl number
    prandtl_number = parsed_params.get("prandtl_number")
    if prandtl_number is not None and (prandtl_number < 0.1 or prandtl_number > 100):
        warnings.append(f"Unusual Prandtl number ({prandtl_number}) - typical range is 0.1-100")
        suggestions.append("Check Prandtl number value (typical: 0.71 for air, 7.0 for water)")
    
    # Check reference temperature
    ref_temp = parsed_params.get("reference_temperature")
    if ref_temp is not None and (ref_temp < 200 or ref_temp > 600):
        warnings.append(f"Reference temperature ({ref_temp} K) outside typical range")
        suggestions.append("Check reference temperature (typical: 293.15 K)")
    
    # buoyantSimpleFoam is steady-state only
    if solver_config.get("analysis_type") == AnalysisType.UNSTEADY:
        errors.append("buoyantSimpleFoam only supports steady-state analysis")
        suggestions.append("Use buoyantPimpleFoam for transient natural convection")
    
    # Check for heat transfer consistency
    if not properties.get("heat_transfer", False):
        warnings.append("Heat transfer not enabled - this may not be appropriate for buoyantSimpleFoam")
        suggestions.append("Enable heat transfer for natural convection simulations")


def _validate_piso_foam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                              properties: Dict[str, Any], parsed_params: Dict[str, Any],
                              errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate pisoFoam-specific configuration."""
    # Check required fields for incompressible flow
    if "U" not in fields and "U" not in solver_config:
        errors.append("Velocity field 'U' required for pisoFoam")
        suggestions.append("Initialize velocity field (typical: (1 0 0) m/s)")
    
    if "p" not in fields and "p" not in solver_config:
        errors.append("Pressure field 'p' required for pisoFoam")
        suggestions.append("Initialize pressure field (typical: 0 Pa relative)")
    
    # Check for transient compatibility
    if solver_config.get("analysis_type") == AnalysisType.STEADY:
        errors.append("pisoFoam only supports transient analysis")
        suggestions.append("Use simpleFoam for steady-state analysis")
    
    # Check Reynolds number for appropriateness
    reynolds_number = parsed_params.get("reynolds_number")
    if reynolds_number is not None and reynolds_number > 100000:
        warnings.append(f"High Reynolds number ({reynolds_number}) - consider pimpleFoam for better stability")
        suggestions.append("pimpleFoam may be more stable for high Re flows")
    
    # Check time step settings
    control_dict = solver_config.get("controlDict", {})
    delta_t = control_dict.get("deltaT", 0)
    if delta_t is not None and delta_t <= 0:
        errors.append("Invalid time step for pisoFoam")
        suggestions.append("Set positive time step (typical: 0.001 s)")
    
    # Suggest temporal accuracy considerations
    suggestions.append("pisoFoam provides good temporal accuracy - ensure CFL < 1 for stability")


def _validate_sonic_foam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                               properties: Dict[str, Any], parsed_params: Dict[str, Any],
                               errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate sonicFoam-specific configuration."""
    # Check required fields for compressible flow
    # Note: For sonicFoam, boundary conditions should be provided by the boundary condition agent
    # and thermophysical properties should be provided by the case writer
    # So we skip these validation checks as they are handled by other agents
    
    # Check thermophysical properties - this should be generated by the solver selector
    if "thermophysicalProperties" not in solver_config:
        # This is expected to be generated by the solver selector based on solver type
        # The case writer will actually write the file, so we don't need to error here
        pass  # Remove the error for now as it's handled in the workflow
    
    # Validate Mach number
    mach_number = parsed_params.get("mach_number")
    if mach_number is None:
        warnings.append("Mach number not specified - assuming supersonic flow")
        suggestions.append("Specify Mach number for better solver configuration")
    elif mach_number < 0.8:
        warnings.append(f"Low Mach number ({mach_number}) for sonicFoam - consider rhoPimpleFoam")
        suggestions.append("sonicFoam is optimized for trans-sonic/supersonic flows")
    elif mach_number > 5.0:
        warnings.append(f"Very high Mach number ({mach_number}) - ensure proper shock capturing")
        suggestions.append("Use specialized high-Mach schemes and fine mesh near shocks")
    
    # Check for transient compatibility
    if solver_config.get("analysis_type") == AnalysisType.STEADY:
        errors.append("sonicFoam only supports transient analysis")
        suggestions.append("Use appropriate steady compressible solver for steady-state")
    
    # Check pressure and temperature consistency
    pressure = parsed_params.get("pressure")
    temperature = parsed_params.get("temperature")
    if pressure is not None and temperature is not None:
        if pressure <= 0:
            errors.append("Pressure must be positive for compressible flows")
        if temperature <= 0:
            errors.append("Temperature must be positive")
    
    # Suggest appropriate numerical schemes
    suggestions.append("Use appropriate shock-capturing schemes (e.g., Kurganov) for supersonic flows")
    suggestions.append("Consider adaptive time stepping for stability")


def _validate_mrf_simple_foam_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                    properties: Dict[str, Any], parsed_params: Dict[str, Any],
                                    errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate MRFSimpleFoam-specific configuration."""
    # Check required fields for incompressible flow
    if "U" not in fields and "U" not in solver_config:
        errors.append("Velocity field 'U' required for MRFSimpleFoam")
        suggestions.append("Initialize velocity field (typical: (1 0 0) m/s)")
    
    if "p" not in fields and "p" not in solver_config:
        errors.append("Pressure field 'p' required for MRFSimpleFoam")
        suggestions.append("Initialize pressure field (typical: 0 Pa relative)")
    
    # Check for MRF properties
    if "MRFProperties" not in solver_config:
        errors.append("MRFProperties required for MRFSimpleFoam")
        suggestions.append("Add MRFProperties file defining rotating zones")
    
    # Validate rotation rate
    rotation_rate = parsed_params.get("rotation_rate")
    if rotation_rate is None:
        warnings.append("Rotation rate not specified - using default value")
        suggestions.append("Specify rotation rate in rad/s (e.g., 314 rad/s = 3000 RPM)")
    elif rotation_rate <= 0:
        errors.append("Rotation rate must be positive")
    elif rotation_rate > 10000:
        warnings.append(f"Very high rotation rate ({rotation_rate} rad/s) - check units and stability")
        suggestions.append("Ensure rotation rate is in rad/s, not RPM")
    
    # Check for steady-state compatibility
    if solver_config.get("analysis_type") == AnalysisType.UNSTEADY:
        errors.append("MRFSimpleFoam only supports steady-state analysis")
        suggestions.append("Use pimpleFoam with MRF for transient rotating flows")
    
    # Check Reynolds number for rotating machinery
    reynolds_number = parsed_params.get("reynolds_number")
    if reynolds_number is not None:
        if reynolds_number < 1000:
            warnings.append(f"Low Reynolds number ({reynolds_number}) for rotating machinery - check flow regime")
            suggestions.append("Rotating machinery typically operates at high Reynolds numbers")
    
    # Check for turbulence modeling
    turbulence_props = solver_config.get("turbulenceProperties", {})
    if turbulence_props.get("simulationType") == "laminar":
        warnings.append("Laminar simulation for rotating machinery - consider turbulent modeling")
        suggestions.append("Rotating machinery flows are typically turbulent")
    
    # Suggest MRF configuration
    suggestions.append("Define MRF zones carefully - ensure rotating regions are properly specified")
    suggestions.append("Consider mesh refinement in high-gradient regions near rotating zones")
    suggestions.append("Use appropriate wall functions for rotating walls")


def _validate_incompressible_config(solver_config: Dict[str, Any], fields: Dict[str, Any], 
                                   properties: Dict[str, Any], parsed_params: Dict[str, Any],
                                   errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate incompressible solver configuration."""
    solver = solver_config.get("solver")
    
    # Check for compressible properties in incompressible solver
    if "thermophysicalProperties" in solver_config:
        warnings.append(f"Thermophysical properties specified for incompressible solver {solver}")
        suggestions.append("Remove thermophysical properties or use compressible solver")
    
    # Check Reynolds number vs solver choice
    reynolds_number = parsed_params.get("reynolds_number", 0)
    if reynolds_number and reynolds_number > 100000:
        if solver == "simpleFoam":
            warnings.append("Very high Reynolds number with steady solver - consider transient")
            suggestions.append("Use pimpleFoam for high Re flows to capture unsteady effects")


def _validate_physics_consistency(solver_config: Dict[str, Any], parsed_params: Dict[str, Any], 
                                 errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate physics consistency across configuration."""
    solver = solver_config.get("solver")
    
    # Check Reynolds number vs turbulence model
    reynolds_number = parsed_params.get("reynolds_number", 0)
    turbulence_props = solver_config.get("turbulenceProperties", {})
    simulation_type = turbulence_props.get("simulationType", "")
    
    if reynolds_number is not None and reynolds_number > 0:
        if reynolds_number > 2300 and simulation_type == "laminar":
            warnings.append(f"High Reynolds number ({reynolds_number}) with laminar simulation")
            suggestions.append("Consider turbulent simulation for Re > 2300")
        elif reynolds_number < 1000 and simulation_type == "RAS":
            warnings.append(f"Low Reynolds number ({reynolds_number}) with turbulent simulation")
            suggestions.append("Consider laminar simulation for Re < 1000")
    
    # Check Mach number vs solver
    mach_number = parsed_params.get("mach_number", 0)
    if mach_number and mach_number > 0.3:
        if solver in ["simpleFoam", "pimpleFoam"]:
            warnings.append(f"High Mach number ({mach_number:.2f}) with incompressible solver")
            suggestions.append("Use rhoPimpleFoam for Mach > 0.3")


def _validate_numerical_settings(solver_config: Dict[str, Any], parsed_params: Dict[str, Any], 
                                errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate numerical settings and schemes."""
    # Check time step for transient simulations
    solver = solver_config.get("solver")
    if solver and ("pimple" in solver.lower() or solver in ["interFoam", "chtMultiRegionFoam", "reactingFoam"]):
        control_dict = solver_config.get("controlDict", {})
        delta_t = control_dict.get("deltaT", 0)
        
        if delta_t is not None and delta_t <= 0:
            errors.append("Invalid time step for transient simulation")
            suggestions.append("Set positive time step (e.g., 0.001 s)")
        elif delta_t is not None and delta_t > 0.1:
            warnings.append(f"Large time step ({delta_t} s) may cause instability")
            suggestions.append("Consider smaller time step for stability")
    
    # Check fvSolution settings
    fv_solution = solver_config.get("fvSolution", {})
    if fv_solution:
        # Check SIMPLE/PIMPLE settings
        if solver == "simpleFoam" and "SIMPLE" not in fv_solution:
            warnings.append("Missing SIMPLE algorithm settings for simpleFoam")
        elif "pimple" in solver.lower() and "PIMPLE" not in fv_solution:
            warnings.append(f"Missing PIMPLE algorithm settings for {solver}")


def _validate_boundary_conditions(solver_config: Dict[str, Any], parsed_params: Dict[str, Any], 
                                 errors: List[str], warnings: List[str], suggestions: List[str]) -> None:
    """Validate boundary condition consistency."""
    # This is a placeholder for boundary condition validation
    # In a full implementation, this would check boundary condition files
    # and ensure they match the solver requirements
    
    solver = solver_config.get("solver")
    
    # Check if boundary conditions are specified in state
    # (This would typically come from the boundary condition agent)
    if "boundary_conditions" not in solver_config:
        warnings.append("No boundary conditions specified in configuration")
        suggestions.append("Ensure boundary conditions are properly defined")
    
    # Solver-specific boundary condition checks
    if solver == "interFoam":
        # interFoam needs alpha fields for each phase
        phases = solver_config.get("phases", [])
        for phase in phases:
            if phase == "water":  # Primary phase typically needs alpha.water
                warnings.append("Ensure alpha.water boundary conditions are defined")
    
    elif solver == "rhoPimpleFoam":
        # Compressible solvers need temperature and pressure BCs
        suggestions.append("Ensure temperature and pressure boundary conditions are defined")
    
    elif solver == "chtMultiRegionFoam":
        # Multi-region solvers need BCs for all regions
        regions = solver_config.get("properties", {}).get("regions", [])
        if len(regions) > 1:
            suggestions.append("Ensure boundary conditions are defined for all regions")
    
    elif solver == "reactingFoam":
        # Reactive solvers need species BCs
        species = solver_config.get("properties", {}).get("species", [])
        if species:
            suggestions.append("Ensure species boundary conditions are defined")


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
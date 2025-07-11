# FoamAI Solver Selection Guide

This document describes the available OpenFOAM solvers in FoamAI, the types of problems they solve, and example prompts that trigger their selection.

## Available Solvers

### 1. simpleFoam
**Type**: Steady-state incompressible flow solver using SIMPLE algorithm

**Best For:**
- Low Reynolds number flows (Re < 40-50 for cylinders)
- Steady aerodynamics and drag calculations
- Pressure drop calculations in pipes/channels
- Flows that reach a steady equilibrium
- Efficiency when time history is not important

**Physical Phenomena:**
- No vortex shedding expected
- No transient effects of interest
- Flow reaches steady state naturally

**Example Prompts:**
- "Calculate drag coefficient for flow around cylinder at Reynolds number 20"
- "Steady-state flow around a 0.1m diameter cylinder at 2 m/s"
- "Find pressure drop in a pipe with diameter 0.05m at Re=100"
- "Simulate steady flow over a sphere at low velocity"
- "Calculate lift and drag on an airfoil at 5 degrees angle of attack in steady flow"

**Solver Settings:**
- Uses relaxation factors tuned by Reynolds number
- Lower Re flows use more conservative relaxation (p=0.1, U=0.3)
- Higher Re flows use standard relaxation (p=0.3, U=0.7)

---

### 2. pimpleFoam
**Type**: Transient incompressible flow solver using PIMPLE algorithm (merged PISO-SIMPLE)

**Best For:**
- Vortex shedding phenomena (Re > 40-50 for cylinders)
- Time-dependent flow analysis
- Startup and shutdown transients
- Unsteady aerodynamics
- Flow instabilities and oscillations

**Physical Phenomena:**
- Vortex shedding expected
- Time-varying forces and pressures
- Flow separation and reattachment
- Turbulent fluctuations of interest

**Example Prompts:**
- "Simulate vortex shedding behind a 0.05m cylinder at Reynolds number 150"
- "Transient flow analysis around a cube for 2 seconds"
- "Study flow instabilities behind a sphere at Re=300"
- "Analyze startup flow around an airfoil from rest to 30 m/s"
- "Time-dependent simulation of flow past a bluff body"
- "Calculate Strouhal number for cylinder at Re=200"

**Solver Settings:**
- Adaptive time stepping with CFL control (maxCo=0.9)
- Time step automatically calculated based on mesh and velocity
- Captures transient phenomena accurately

---

### 3. pisoFoam
**Type**: Transient incompressible flow solver using PISO algorithm

**Best For:**
- Transient incompressible flows requiring high temporal accuracy
- Large time step transient simulations
- Flows where PISO algorithm is specifically requested
- Less computationally intensive than PIMPLE for some cases

**Physical Phenomena:**
- Time-dependent incompressible flows
- Unsteady phenomena with emphasis on temporal accuracy
- Flows requiring explicit time stepping characteristics

**Example Prompts:**
- "Use PISO algorithm for transient flow around cylinder"
- "Simulate unsteady flow with PISO method"
- "Time-dependent analysis using pisoFoam"

**Solver Settings:**
- Pure PISO algorithm (no outer corrector loops)
- Optimized for temporal accuracy
- Suitable for moderate time steps

---

### 4. interFoam
**Type**: Multiphase flow solver using Volume of Fluid (VOF) method

**Best For:**
- Free surface flows with air-water interfaces
- Breaking waves and wave impact
- Dam break and sloshing simulations
- Droplet dynamics and spray formation
- Two-phase immiscible fluid flows

**Physical Phenomena:**
- Interface tracking between immiscible fluids
- Surface tension effects
- Wave breaking and air entrainment
- Droplet formation and coalescence

**Example Prompts:**
- "Dam break simulation with water and air"
- "Wave breaking over a seawall"
- "Droplet impact on a surface"
- "Sloshing in a tank"
- "Water flow with free surface"

**Solver Settings:**
- VOF method for interface tracking
- MULES algorithm for sharp interface preservation
- Adaptive time stepping for interface stability

---

### 5. rhoPimpleFoam
**Type**: Compressible transient flow solver

**Best For:**
- Compressible flows with density variations
- Subsonic to low supersonic flows (Mach < 1.2)
- Flows with significant temperature variations
- Pressure-driven flows with compressibility effects

**Physical Phenomena:**
- Density variations due to pressure/temperature changes
- Compressible flow effects without strong shocks
- Thermodynamic property variations
- Moderate Mach number flows

**Example Prompts:**
- "Compressible flow in a nozzle at Mach 0.8"
- "Flow with significant density variations"
- "Subsonic compressible flow around airfoil"
- "Pressure-driven flow with compressibility"

**Solver Settings:**
- Density-based formulation
- Thermodynamic coupling
- Pressure-velocity coupling for compressible flows

---

### 6. sonicFoam
**Type**: Transient compressible flow solver for trans-sonic/supersonic flows

**Best For:**
- High-speed compressible flows (Mach > 1.2)
- Supersonic and hypersonic flows
- Shock wave phenomena
- Gas dynamics with strong density variations

**Physical Phenomena:**
- Shock wave formation and propagation
- Expansion fans and compression waves
- High Mach number effects
- Strong density gradients

**Example Prompts:**
- "Supersonic flow at Mach 2.5"
- "Shock wave propagation"
- "Hypersonic flow around blunt body"
- "Gas dynamics with strong shocks"
- "Ballistic projectile at high speed"

**Solver Settings:**
- Shock-capturing schemes
- High-resolution flux limiters
- Specialized for high Mach number flows

---

### 7. chtMultiRegionFoam
**Type**: Conjugate heat transfer solver for multi-region problems

**Best For:**
- Heat transfer problems with solid-fluid coupling
- Electronics cooling with heat sinks
- Heat exchangers and thermal management
- Problems requiring solid conduction coupling

**Physical Phenomena:**
- Conjugate heat transfer between solid and fluid
- Multi-region temperature coupling
- Thermal conduction in solids
- Convective heat transfer in fluids

**Example Prompts:**
- "Heat transfer in electronics with heat sink"
- "Heat exchanger with solid walls"
- "Thermal management system"
- "Conjugate heat transfer analysis"

**Solver Settings:**
- Multi-region mesh handling
- Solid-fluid thermal coupling
- Temperature continuity at interfaces

---

### 8. reactingFoam
**Type**: Reactive flow solver for combustion and chemical reactions

**Best For:**
- Combustion processes and flame propagation
- Chemical reaction systems
- Mixing and reaction in turbulent flows
- Pollutant formation and destruction

**Physical Phenomena:**
- Chemical reactions and species transport
- Combustion heat release
- Flame propagation and extinction
- Turbulence-chemistry interaction

**Example Prompts:**
- "Combustion in a gas turbine"
- "Chemical mixing and reaction"
- "Flame propagation in premixed gas"
- "Turbulent combustion simulation"

**Solver Settings:**
- Species transport equations
- Chemical reaction mechanisms
- Combustion models (EDC, PaSR, etc.)

---

### 9. buoyantSimpleFoam
**Type**: Steady-state heat transfer solver with buoyancy effects

**Best For:**
- Natural convection problems
- Heat transfer with buoyancy-driven flows
- Thermal plumes and convection cells
- Steady-state thermal analysis

**Physical Phenomena:**
- Buoyancy-driven flows
- Natural convection heat transfer
- Thermal stratification
- Gravity-driven circulation

**Example Prompts:**
- "Natural convection in a heated cavity"
- "Thermal plume from heated surface"
- "Buoyancy-driven flow in enclosure"
- "Steady-state thermal convection"

**Solver Settings:**
- Boussinesq approximation for buoyancy
- Temperature-dependent density
- Steady-state energy equation

---

### 10. MRFSimpleFoam
**Type**: Steady-state incompressible flow solver with Multiple Reference Frame (MRF)

**Best For:**
- Rotating machinery analysis
- Pumps, fans, and turbines
- Steady-state flows with rotation
- Propeller and rotor simulations

**Physical Phenomena:**
- Rotating reference frames
- Coriolis and centrifugal effects
- Steady-state rotating flows
- Impeller and blade interactions

**Example Prompts:**
- "Flow through a centrifugal pump"
- "Propeller in steady rotation"
- "Fan performance analysis"
- "Rotating machinery simulation"

**Solver Settings:**
- Multiple reference frame handling
- Rotating coordinate transformations
- Steady-state with rotation effects

---

## AI Solver Selection Logic

The AI makes intelligent decisions based on:

### 1. **Reynolds Number Analysis**
- Checks if vortex shedding is expected based on geometry and Re
- Cylinder: Vortex shedding starts at Re ≈ 40-50
- Sphere: Vortex shedding starts at Re ≈ 300
- Square cylinder: Vortex shedding starts at Re ≈ 50-60

### 2. **Keyword Detection**
- **simpleFoam triggers**: "steady-state", "steady", "equilibrium", "drag coefficient" (at low Re)
- **pimpleFoam triggers**: "transient", "time-dependent", "vortex shedding", "unsteady", "startup", "Strouhal"
- **pisoFoam triggers**: "PISO", "PISO algorithm", "explicit time stepping", "temporal accuracy"
- **interFoam triggers**: "multiphase", "free surface", "VOF", "water", "dam break", "wave", "droplet", "interface"
- **rhoPimpleFoam triggers**: "compressible", "density variations", "subsonic", "Mach" (< 1.2), "pressure-driven"
- **sonicFoam triggers**: "supersonic", "hypersonic", "shock", "high-speed", "Mach" (> 1.2), "gas dynamics"
- **chtMultiRegionFoam triggers**: "conjugate heat transfer", "multi-region", "solid-fluid", "heat exchanger", "thermal coupling"
- **reactingFoam triggers**: "combustion", "chemical reaction", "flame", "species transport", "mixing"
- **buoyantSimpleFoam triggers**: "natural convection", "buoyancy", "thermal plume", "gravity-driven", "heated cavity"
- **MRFSimpleFoam triggers**: "rotating machinery", "MRF", "propeller", "fan", "pump", "turbine", "rotation"

### 3. **Physical Reasoning**
- If Re is below vortex shedding threshold → simpleFoam (more efficient)
- If Re is above vortex shedding threshold → pimpleFoam (captures physics)
- If time history is requested → pimpleFoam or pisoFoam
- If only final forces needed at low Re → simpleFoam
- If multiphase flow detected → interFoam
- If compressible flow with Mach > 1.2 → sonicFoam
- If compressible flow with Mach < 1.2 → rhoPimpleFoam
- If heat transfer with solid coupling → chtMultiRegionFoam
- If chemical reactions present → reactingFoam
- If buoyancy-driven flow → buoyantSimpleFoam
- If rotating machinery → MRFSimpleFoam

### 4. **Default Behavior**
- When in doubt, the system favors accuracy over efficiency
- Unknown flows default to transient analysis if Re is moderate to high
- AI analyzes multiple physical phenomena simultaneously
- Solver selection based on confidence scoring system with alternatives provided

---

## Usage Tips

1. **Be specific about time dependency** - Use keywords like "steady-state" or "transient" when you have a preference

2. **Provide Reynolds number** - This helps the AI make better decisions about expected flow phenomena

3. **Mention physical phenomena** - Keywords like "vortex shedding" or "drag coefficient" help guide solver selection

4. **Trust the AI** - The system uses physical reasoning to select the most appropriate solver

5. **Coarse mesh for testing** - Add "coarse mesh" to prompts for faster initial testing

---

*Last Updated: 2025-01-21*
*Version: 2.0 - Complete solver suite with 10 OpenFOAM solvers* 
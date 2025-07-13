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

### 3. **Physical Reasoning**
- If Re is below vortex shedding threshold → simpleFoam (more efficient)
- If Re is above vortex shedding threshold → pimpleFoam (captures physics)
- If time history is requested → pimpleFoam
- If only final forces needed at low Re → simpleFoam

### 4. **Default Behavior**
- When in doubt, the system favors accuracy over efficiency
- Unknown flows default to transient analysis if Re is moderate to high

---

## Future Solver Additions (Planned)

### rhoSimpleFoam / rhoPimpleFoam
- Compressible flow solvers
- For high Mach number flows (Ma > 0.3)
- Density variations important

### interFoam
- Multiphase flow solver
- Free surface flows
- Volume of Fluid (VOF) method

### buoyantSimpleFoam / buoyantPimpleFoam
- Heat transfer with buoyancy
- Natural convection problems
- Thermal plumes

### SRFSimpleFoam / SRFPimpleFoam
- Single rotating reference frame
- Rotating machinery (simplified)
- Stirred tanks, mixers

---

## Usage Tips

1. **Be specific about time dependency** - Use keywords like "steady-state" or "transient" when you have a preference

2. **Provide Reynolds number** - This helps the AI make better decisions about expected flow phenomena

3. **Mention physical phenomena** - Keywords like "vortex shedding" or "drag coefficient" help guide solver selection

4. **Trust the AI** - The system uses physical reasoning to select the most appropriate solver

5. **Coarse mesh for testing** - Add "coarse mesh" to prompts for faster initial testing

---

*Last Updated: 2025-07-08*
*Version: 1.0* 
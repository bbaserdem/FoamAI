# FoamAI Vortex Shedding Visualization Guide

## Overview

FoamAI now includes comprehensive vortex shedding visualization capabilities designed to properly capture and display the complex flow phenomena associated with vortex shedding behind bluff bodies. This guide explains the enhanced features and how to use them effectively.

## What's New for Vortex Shedding Visualization

### 🌪️ **Enhanced Visualization Features**

1. **Vorticity Field Visualization**
   - Calculates and displays vorticity magnitude using `curl(U)`
   - Uses the 'Plasma' color map for optimal vortex contrast
   - Essential for seeing actual vortex structures in the flow

2. **Q-Criterion Isosurfaces**
   - Advanced vortex identification using the Q-criterion
   - Shows 3D vortex cores as isosurfaces
   - Automatically selects appropriate contour levels (10% of maximum Q)

3. **Enhanced Streamlines**
   - Smart seeding specifically designed for vortex shedding
   - Multiple seed points in the wake region
   - Captures both upstream flow and downstream vortex formation

4. **Time-Averaged Flow Visualization**
   - Computes time-averaged velocity fields
   - Shows mean flow patterns behind the obstruction
   - Helps understand the overall flow structure

5. **Animation Support**
   - Saves ParaView state files for interactive viewing
   - Provides detailed animation instructions
   - Includes estimated Strouhal number for cylinders

### 🎯 **Automatic Detection**

The system automatically detects when vortex shedding is expected based on:
- **Geometry type**: Cylinder, sphere, cube, or custom STL
- **Reynolds number**: Compares against known vortex shedding thresholds
  - Cylinder: Re > 40
  - Sphere: Re > 200
  - Cube: Re > 50
  - Custom: Re > 50 (conservative)

When vortex shedding is detected, the system automatically:
- Generates specialized visualizations
- Uses appropriate time steps (80% of simulation time)
- Creates enhanced streamline patterns
- Saves animation-ready state files

## Generated Visualization Files

For vortex shedding cases, the following files are created in the `visualization/` directory:

```
visualization/
├── pressure_field.png          # Pressure contours
├── velocity_field.png          # Velocity magnitude
├── vorticity_field.png         # Vorticity magnitude (NEW)
├── q_criterion.png             # Q-criterion isosurfaces (NEW)
├── streamlines.png             # Enhanced streamlines (IMPROVED)
├── surface_pressure.png        # Surface pressure distribution
├── time_averaged_flow.png      # Time-averaged velocity (NEW)
├── vortex_shedding_animation.pvsm    # ParaView state file (NEW)
└── animation_instructions.txt  # Animation guide (NEW)
```

## How to Use the Enhanced Visualizations

### 1. **Basic Usage**
Run FoamAI with vortex shedding conditions:
```bash
uv run python src/foamai/cli.py solve "Flow around a cylinder at Re=150" --verbose --export-images
```

### 2. **Opening in ParaView**
The system will automatically open ParaView with the enhanced visualizations. You can also run:
```bash
python open_in_paraview.py work/your_case_directory
```

### 3. **Interactive Animation**
For time-dependent vortex shedding visualization:
1. Open ParaView
2. Load the state file: `File > Load State > vortex_shedding_animation.pvsm`
3. Use the animation controls to play through time steps
4. Color by 'Vorticity_Magnitude' for best results

### 4. **Advanced Visualization Tips**

#### **For Vorticity Visualization:**
- Use the 'Plasma' or 'Viridis' color maps
- Adjust the color scale to highlight vortex structures
- Consider using logarithmic scaling for better contrast

#### **For Q-Criterion:**
- Look for tube-like structures representing vortex cores
- Adjust opacity (default: 0.7) for better visualization
- Color by velocity magnitude to show flow speed in vortices

#### **For Time Animation:**
- Play at 10-20% speed for better observation
- Enable time annotation to see temporal evolution
- Save animations as MP4 or AVI files

## Understanding Vortex Shedding Results

### **Key Phenomena to Look For:**

1. **Von Kármán Vortex Street**
   - Alternating vortices in the wake
   - Regular shedding frequency
   - Symmetric vortex formation

2. **Vortex Formation Process**
   - Boundary layer separation
   - Shear layer roll-up
   - Vortex detachment and convection

3. **Wake Characteristics**
   - Recirculation zone behind the object
   - Vortex street formation distance
   - Wake spreading angle

### **Quantitative Analysis:**

The system provides estimated Strouhal numbers for cylinders:
- **Strouhal Number (St)**: `St = f * D / U`
  - Where f = shedding frequency, D = diameter, U = velocity
- **Typical values**: St ≈ 0.2 for cylinders at Re = 100-300

## Troubleshooting

### **Common Issues:**

1. **No Vorticity Field Generated**
   - Check if the solver is transient (pimpleFoam)
   - Ensure sufficient time steps are available
   - Verify Reynolds number is above threshold

2. **Poor Animation Quality**
   - Increase output frequency in solver settings
   - Use more time steps (recommend > 20 for good animation)
   - Check that transient simulation ran to completion

3. **Streamlines Not Showing Wake**
   - Verify enhanced seeding is activated
   - Check domain size (wake should be captured)
   - Ensure velocity field is available

### **Performance Tips:**

- Use `--export-images` flag for faster batch processing
- For large cases, consider reducing image resolution
- Time-averaged visualizations require > 20 time steps

## Technical Details

### **Vorticity Calculation:**
```python
# ParaView Calculator function
vorticity = curl(U)
vorticity_magnitude = mag(curl(U))
```

### **Q-Criterion Calculation:**
```python
# Simplified Q-criterion approximation
Q = 0.5 * (mag(curl(U))^2 - 0.5 * (mag(grad(U)) + mag(grad(U))_T)^2)
```

### **Enhanced Streamline Seeding:**
- **Upstream seeding**: 10 points across flow inlet
- **Wake seeding**: 15×5 grid downstream of object
- **Adaptive spacing**: Based on object characteristic length

## Integration with FoamAI Workflow

The enhanced visualization system integrates seamlessly with the FoamAI workflow:

1. **NL Interpreter**: Detects vortex shedding keywords
2. **Solver Selector**: Chooses transient solvers (pimpleFoam) when needed
3. **Mesh Generator**: Creates appropriate wake refinement
4. **Simulation Executor**: Runs with suitable time stepping
5. **Visualization Agent**: Generates enhanced vortex shedding visualizations

## Examples

### **Sample Commands:**
```bash
# Classic cylinder vortex shedding
uv run python src/foamai/cli.py solve "Vortex shedding behind a 0.1m cylinder at 2 m/s" --verbose --export-images

# High Reynolds number case
uv run python src/foamai/cli.py solve "Turbulent flow around sphere at Re=1000" --verbose --export-images

# Custom geometry
uv run python src/foamai/cli.py solve "Flow around custom geometry with vortex shedding" --stl-file geometry.stl --verbose --export-images
```

### **Expected Results:**
- Vorticity magnitude images showing clear vortex structures
- Q-criterion isosurfaces revealing vortex cores
- Streamlines illustrating the von Kármán vortex street
- Time-averaged flow showing mean wake characteristics

## Future Enhancements

Planned improvements for vortex shedding visualization:
- **Strouhal number calculation** from force coefficients
- **Proper Orthogonal Decomposition (POD)** analysis
- **Dynamic Mode Decomposition (DMD)** for modal analysis
- **Automated vortex tracking** and statistics
- **3D vortex identification** using λ2 criterion

---

*This enhanced visualization system ensures that FoamAI users can properly analyze and understand vortex shedding phenomena, providing both quantitative data and intuitive visualizations of these complex flow behaviors.* 
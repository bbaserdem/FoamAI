# Mesh Convergence from Natural Language Prompts

The FoamAI system now supports mesh convergence studies directly from natural language prompts! You can request mesh convergence analysis without using command-line flags.

## How It Works

The natural language interpreter automatically detects when you're asking for:
- Mesh convergence studies
- Grid independence tests  
- Mesh sensitivity analysis
- Convergence validation

## Example Prompts

### Basic Mesh Convergence
```bash
uv run python src/foamai/cli.py solve "Flow around a cylinder with mesh convergence study" --verbose
```

### Specific Number of Levels
```bash
uv run python src/foamai/cli.py solve "Simulate flow around F1 car with 5 mesh levels for convergence analysis" --stl-file stl/F1.stl --verbose
```

### Custom Convergence Threshold
```bash
uv run python src/foamai/cli.py solve "Grid independence test with 0.5% convergence threshold for flow around airfoil" --verbose
```

### Target Specific Parameters
```bash
uv run python src/foamai/cli.py solve "Check drag convergence with mesh refinement study for flow around sphere" --verbose
```

### Complex Example
```bash
uv run python src/foamai/cli.py solve "Perform mesh convergence study with 6 levels, analyze drag and pressure convergence within 0.8% accuracy for high-speed flow around F1 car at 200 km/h" --stl-file stl/F1.stl --verbose
```

### Alternative Keywords
```bash
uv run python src/foamai/cli.py solve "Grid sensitivity analysis for turbulent flow around cylinder" --verbose
```

```bash
uv run python src/foamai/cli.py solve "Ensure mesh independence by testing different mesh resolutions" --verbose
```

```bash
uv run python src/foamai/cli.py solve "Validate mesh quality with convergence test for nozzle flow" --verbose
```

## Detected Keywords

The system recognizes these patterns:
- **Mesh convergence**: "mesh convergence", "mesh independence", "mesh study"
- **Grid convergence**: "grid convergence", "grid independence", "grid study"  
- **General convergence**: "convergence study", "convergence test", "convergence analysis"
- **Refinement studies**: "mesh refinement study", "grid refinement study"
- **Sensitivity analysis**: "mesh sensitivity", "grid sensitivity", "sensitivity analysis"
- **Quality checks**: "validate mesh", "verify mesh", "mesh quality check"
- **Resolution studies**: "mesh resolution study", "test mesh convergence"

## Parameter Extraction

The system can extract:

### Number of Mesh Levels
- "with 5 mesh levels"
- "using 6 refinement levels"
- "4 different meshes"
- "6-level mesh study"

### Convergence Threshold
- "0.5% convergence threshold"
- "within 0.8% accuracy"
- "tolerance of 1.0%"
- "error less than 0.5%"

### Target Parameters
- **Drag**: "drag convergence", "check drag", "analyze drag"
- **Pressure**: "pressure convergence", "pressure drop"
- **Velocity**: "velocity convergence", "max velocity"
- **Lift**: "lift convergence", "lift coefficient"
- **Forces**: "force convergence"

## What Happens Behind the Scenes

When mesh convergence is detected from your prompt:

1. **Detection**: The natural language interpreter identifies convergence keywords
2. **Parameter Extraction**: Extracts levels, threshold, and target parameters
3. **State Update**: Updates the CFD state with mesh convergence settings
4. **Workflow Modification**: The orchestrator automatically routes to mesh convergence
5. **Multiple Simulations**: Runs simulations on systematically refined meshes
6. **Convergence Analysis**: Calculates Grid Convergence Index (GCI) and Richardson extrapolation
7. **Optimal Mesh Selection**: Recommends the coarsest mesh that meets convergence criteria
8. **Results Copy**: Copies the optimal mesh results to the main case for visualization

## Benefits

- **No Command-Line Flags**: Natural language is more intuitive
- **Automatic Parameter Detection**: Extracts settings from your description
- **Flexible Requests**: Multiple ways to ask for the same thing
- **Comprehensive Analysis**: Full GCI-based convergence assessment
- **Optimal Mesh Selection**: Automatically chooses the best mesh
- **Seamless Integration**: Works with all existing features (STL files, verbose output, etc.)

## Example Output

When you run a mesh convergence study, you'll see:

```
🔍 Mesh Convergence Study Results:
✅ Completed 4 mesh levels successfully
📊 Recommended Level: 2 (Fine mesh)
💡 Mesh Convergence Recommendations:
  ✅ drag_coefficient: CONVERGED (0.8% change)
  ✅ pressure_drop: CONVERGED (0.6% change)
```

## Combining with Other Features

You can combine mesh convergence with other features:

```bash
# With STL files
uv run python src/foamai/cli.py solve "Mesh convergence study for F1 car aerodynamics at 200 km/h, analyze drag and downforce" --stl-file stl/F1.stl --verbose

# With custom parameters
uv run python src/foamai/cli.py solve "Grid independence test with 5 levels and 0.5% threshold for high Reynolds number flow around cylinder with velocity 50 m/s" --verbose

# With advanced physics
uv run python src/foamai/cli.py solve "Mesh sensitivity analysis for turbulent flow with heat transfer around heated cylinder" --verbose
```

This natural language approach makes mesh convergence studies much more accessible and intuitive to use! 
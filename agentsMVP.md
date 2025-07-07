# AI-Powered CFD Application MVP Implementation Plan

Based on the mermaid diagram and existing codebase structure, this document outlines a comprehensive step-by-step plan for implementing the MVP command-line version of the AI-powered fluid dynamics application.

## Step-by-Step Implementation Plan for MVP

### Phase 1: Foundation Setup (Days 1-3)

**1. Core Dependencies & Environment**
- Add LangChain, LangGraph, and OpenAI dependencies to your `pyproject.toml`
- Install OpenFOAM (suggest using the Foundation version 2312 as per your tech stack docs)
- Set up ParaView server installation
- Configure your development environment with proper Python path handling

**2. Project Structure Enhancement**
```
FoamAI/
├── src/foamai/
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── agents/             # LangGraph agents
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── nl_interpreter.py
│   │   ├── mesh_generator.py
│   │   ├── boundary_condition.py
│   │   ├── solver_selector.py
│   │   ├── case_writer.py
│   │   ├── simulation_executor.py
│   │   └── visualization.py
│   ├── templates/          # OpenFOAM case templates
│   ├── utils/             # Helper functions
│   └── config/            # Configuration management
```

**3. Configuration Management**
- Create a configuration system for OpenFOAM paths, ParaView server settings, and LLM credentials
- Set up environment variable handling for OpenAI API key
- Configure logging for the entire application

### Phase 2: Core Agent Implementation (Days 4-10)

**4. LangGraph State Schema**
```python
# Define the state structure that will be passed between agents
class CFDState(TypedDict):
    user_prompt: str
    parsed_parameters: Dict[str, Any]
    geometry_info: Dict[str, Any]
    mesh_config: Dict[str, Any]
    boundary_conditions: Dict[str, Any]
    solver_settings: Dict[str, Any]
    case_directory: str
    simulation_results: Dict[str, Any]
    visualization_path: str
    errors: List[str]
```

**5. Natural Language Interpreter Agent**
- Use OpenAI GPT-4 to parse user prompts like "Turbulent flow around a cylinder"
- Extract geometry type, flow conditions, analysis type, and specific parameters
- Return structured data for downstream agents

**6. Mesh Generator Agent**
- Create templates for common geometries (cylinder, airfoil, pipe, etc.)
- Generate `blockMeshDict` files based on geometry parameters
- Handle different mesh refinement levels

**7. Boundary Condition Agent**
- Create templates for common boundary conditions (inlet, outlet, walls, symmetry)
- Generate `0/` directory files (U, p, turbulence properties)
- Handle different flow regimes (laminar, turbulent, compressible)

**8. Solver Selector Agent**
- Rule-based selection of OpenFOAM solvers (simpleFoam, pimpleFoam, etc.)
- Generate appropriate `fvSchemes` and `fvSolution` files
- Configure solver parameters based on flow conditions

**9. Case Writer Agent**
- Assemble complete OpenFOAM case directory structure
- Copy template files and populate with agent-generated content
- Validate case completeness before simulation

### Phase 3: Execution & Visualization (Days 11-15)

**10. Simulation Executor Agent**
- Execute OpenFOAM preprocessing (blockMesh, checkMesh)
- Run the selected solver with progress monitoring
- Parse residuals and convergence information
- Handle common simulation errors and failures

**11. Visualization Agent**
- Use ParaView Python scripting to create standard visualizations
- Generate pressure, velocity, and streamline plots
- Export images or 3D visualization files
- Handle different visualization types based on the simulation

**12. System Orchestrator**
- Implement the LangGraph workflow to coordinate all agents
- Handle error recovery and agent retry logic
- Manage the overall state flow from user input to final output

### Phase 4: CLI Interface & Integration (Days 16-20)

**13. Command-Line Interface**
```bash
# Target usage
foamai solve "Turbulent flow around a cylinder at Re=1000"
foamai solve "Laminar flow in a pipe with pressure drop"
foamai solve "Flow over an airfoil at 10 degrees angle of attack"
```

**14. Template Library**
- Create pre-configured OpenFOAM case templates for common scenarios
- Include mesh generation scripts and boundary condition setups
- Provide template validation and customization capabilities

**15. Output Management**
- Organize simulation results in timestamped directories
- Provide options for different output formats (images, ParaView files, data files)
- Implement cleanup options for temporary files

### Phase 5: Testing & Validation (Days 21-25)

**16. Test Cases**
- Create automated tests for each agent
- Implement end-to-end tests with known validation cases
- Test error handling and recovery mechanisms

**17. Performance Optimization**
- Optimize LLM prompt engineering for better parameter extraction
- Implement caching for common case templates
- Add progress indicators for long-running simulations

## Key Implementation Considerations

### 1. **OpenFOAM Integration**
- Ensure proper OpenFOAM environment sourcing before running commands
- Handle different OpenFOAM versions and installation paths
- Implement robust error parsing from OpenFOAM outputs

### 2. **LLM Prompt Engineering**
- Create structured prompts that reliably extract CFD parameters
- Implement validation of LLM outputs before passing to downstream agents
- Use few-shot examples for better parameter extraction accuracy

### 3. **Error Handling**
- Implement comprehensive error handling at each agent level
- Create recovery strategies for common OpenFOAM failures
- Provide meaningful error messages to users

### 4. **Resource Management**
- Monitor simulation resource usage (CPU, memory, disk space)
- Implement timeout mechanisms for long-running simulations
- Handle cleanup of temporary files and directories

### 5. **Extensibility**
- Design the system to easily add new geometry types
- Allow for custom boundary condition templates
- Support adding new solver configurations

### 6. **Validation**
- Implement case validation before simulation execution
- Check mesh quality and provide warnings
- Validate boundary condition compatibility

## Technology Stack Alignment

Your current setup aligns well with the planned implementation:
- **Nix environment**: Perfect for reproducible OpenFOAM installations
- **Python ecosystem**: Enables easy integration with LangChain/LangGraph
- **Documented architecture**: Provides clear guidance for agent interactions

## Next Steps

1. Start with Phase 1 to establish the foundation
2. Implement a simple "hello world" case that can parse "flow around cylinder" and generate a basic OpenFOAM case
3. Gradually add complexity and more sophisticated natural language understanding
4. Test with increasingly complex scenarios

This approach will give you a working MVP that demonstrates the core concept while providing a solid foundation for the full application architecture you've designed.

## Target CLI Usage Examples

```bash
# Basic usage
foamai solve "Turbulent flow around a cylinder at Re=1000"

# With specific parameters
foamai solve "Laminar flow in a pipe with pressure drop of 100 Pa"

# Complex geometries
foamai solve "Flow over an airfoil at 10 degrees angle of attack"

# With output specifications
foamai solve "Turbulent flow around a cylinder" --output-format paraview --export-images
```

## Expected Output Structure

```
results/
├── 2024-01-XX_HH-MM-SS_cylinder_flow/
│   ├── case/                    # OpenFOAM case files
│   ├── simulation.log           # Simulation logs
│   ├── visualization/           # Generated images/ParaView files
│   │   ├── pressure_field.png
│   │   ├── velocity_field.png
│   │   └── streamlines.png
│   └── summary.json            # Simulation summary and results
``` 
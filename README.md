# FoamAI 🌊

**AI-Powered CFD Analysis with OpenFOAM and ParaView**

FoamAI is an intelligent CFD (Computational Fluid Dynamics) application that converts natural language descriptions into complete OpenFOAM simulations. Simply describe your flow problem in plain English, and FoamAI will automatically generate the mesh, boundary conditions, solver settings, run the simulation, and create visualizations.

## 🚀 Key Features

### 🎯 **Natural Language Processing**
- **Intelligent Prompt Parsing**: Converts natural language descriptions into CFD parameters
- **Dimension Extraction**: Automatically extracts geometry dimensions with unit conversion (mm, cm, inches → meters)
- **Parameter Validation**: Validates physical parameters and provides warnings for out-of-range values
- **Advanced Parameter Detection**: Recognizes domain size multipliers, Courant numbers, time step limits, and mesh resolution preferences

### 🏗️ **Geometry Support**
- **Built-in Geometries**: Cylinder, sphere, cube, airfoil, pipe, channel
- **Custom STL Geometries**: Full support for complex 3D geometries via STL files
- **Automatic Geometry Analysis**: STL bounding box analysis, unit detection, and scaling
- **Geometry Rotation**: Support for rotating geometries with natural language commands
- **Intelligent Defaults**: Automatic geometry sizing based on Reynolds number and flow type

### 🔧 **Solver Selection & Configuration**
- **Multiple OpenFOAM Solvers**:
  - `simpleFoam`: Steady-state incompressible flows
  - `pimpleFoam`: Transient incompressible flows with vortex shedding
  - `interFoam`: Multiphase flows (VOF method)
  - `rhoPimpleFoam`: Compressible transient flows
  - `chtMultiRegionFoam`: Conjugate heat transfer
  - `reactingFoam`: Combustion and chemical reactions
- **Intelligent Solver Selection**: AI-powered solver recommendation based on problem features
- **Adaptive Time Stepping**: Automatic time step calculation based on velocity and geometry
- **Turbulence Models**: Laminar, RANS (k-epsilon, k-omega), and LES support

### 🕸️ **Advanced Mesh Generation**
- **Structured Meshes**: BlockMesh for simple geometries
- **Unstructured Meshes**: SnappyHexMesh for complex geometries
- **Adaptive Mesh Parameters**: Automatic cell count and refinement level calculation
- **Mesh Quality Control**: Built-in mesh quality assessment and recommendations
- **O-Grid Generation**: Specialized meshes for cylindrical geometries
- **Surface Layer Insertion**: Boundary layer mesh generation for wall-bounded flows
- **Mesh Convergence Studies**: Systematic mesh refinement with Grid Convergence Index (GCI) analysis

### 🌊 **Boundary Conditions**
- **Intelligent Mapping**: Automatic boundary condition mapping to mesh patches
- **Comprehensive Field Support**: Velocity (U), pressure (p), temperature (T), turbulence fields
- **Geometry-Specific Conditions**: Optimized boundary conditions for each geometry type
- **AI-Enhanced Generation**: OpenAI-powered boundary condition optimization
- **Heat Transfer**: Automatic temperature field generation for high-speed flows

### 📊 **Visualization & Analysis**
- **Automatic Visualization**: Generates pressure, velocity, and streamline plots
- **Vortex Shedding Analysis**: 
  - Vorticity magnitude visualization
  - Q-criterion isosurfaces for vortex core identification
  - Time-averaged flow fields
  - Enhanced streamline seeding for wake capture
- **Surface Analysis**: Surface pressure distribution on geometry
- **ParaView Integration**: Automatic ParaView launching with .foam files
- **Animation Support**: ParaView state files for time-dependent visualization
- **Multiple Export Formats**: PNG images, ParaView files, VTK data

### 🔄 **Workflow Management**
- **Multi-Agent Architecture**: Specialized agents for each workflow step
- **Error Recovery**: Automatic retry with parameter adjustment
- **User Approval System**: Interactive configuration review before simulation
- **Progress Tracking**: Real-time progress indicators and detailed logging
- **Iterative Workflow**: Support for multiple simulation iterations
- **Mesh Independence Validation**: Automated mesh convergence studies with uncertainty quantification

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- OpenFOAM (ESI or Foundation version)
- ParaView 5.6+
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/foamai.git
   cd foamai
   ```

2. **Install dependencies**
   ```bash
   uv sync  # or pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Create .env file with your settings
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   echo "OPENFOAM_PATH=/path/to/openfoam" >> .env
   echo "PARAVIEW_PATH=/path/to/paraview" >> .env
   ```

## 🎮 Usage

### Basic Usage

```bash
# Solve a CFD problem from natural language
uv run python src/foamai/cli.py solve "Flow around a cylinder at 10 m/s"

# Use custom STL geometry
uv run python src/foamai/cli.py solve "Turbulent flow around car at 60 m/s" --stl-file path/to/car.stl

# Skip user approval for automated runs
uv run python src/foamai/cli.py solve "Flow in pipe with 0.1m diameter" --no-user-approval

# Enable verbose output for debugging
uv run python src/foamai/cli.py solve "Flow over airfoil" --verbose

# Run mesh convergence study
uv run python src/foamai/cli.py solve "Flow around cylinder at 10 m/s" --mesh-study --mesh-levels 4
```

### CLI Commands

- `solve`: Main command for CFD problem solving
- `list-examples`: Show example problems and commands
- `status`: Check installation and configuration
- `visualize`: Generate visualizations from existing cases (planned)

### CLI Options

- `--stl-file`: Path to STL file for custom geometry
- `--verbose, -v`: Enable verbose logging
- `--no-user-approval`: Skip interactive approval step
- `--no-export-images`: Disable automatic image export
- `--output-format`: Output format (images, paraview, data)
- `--max-retries`: Maximum retry attempts (default: 3)
- `--force-validation`: Override parameter validation warnings

#### Mesh Convergence Options
- `--mesh-study`: Enable mesh convergence study
- `--mesh-levels`: Number of mesh refinement levels (default: 4)
- `--mesh-target-params`: Parameters to monitor (e.g., drag_coefficient,pressure_drop)
- `--mesh-convergence-threshold`: Convergence threshold percentage (default: 1.0%)

## 📝 Example Problems

### External Aerodynamics
```bash
# Cylinder vortex shedding
uv run python src/foamai/cli.py solve "Turbulent flow around 0.1m diameter cylinder at Reynolds number 1000"

# Airfoil analysis
uv run python src/foamai/cli.py solve "Flow over NACA 0012 airfoil at 10 degrees angle of attack"

# Sphere wake analysis
uv run python src/foamai/cli.py solve "Flow around sphere at 50 m/s with fine mesh"
```

### Internal Flows
```bash
# Pipe flow
uv run python src/foamai/cli.py solve "Laminar flow in pipe with 0.05m diameter and 2 m/s velocity"

# Channel flow
uv run python src/foamai/cli.py solve "Turbulent channel flow with heated walls"
```

### Custom Geometries
```bash
# Vehicle aerodynamics
uv run python src/foamai/cli.py solve "Flow around car at highway speed" --stl-file car.stl

# Rotated geometry
uv run python src/foamai/cli.py solve "Flow around aircraft rotated 15 degrees" --stl-file plane.stl
```

### Advanced Parameters
```bash
# Domain size control
uv run python src/foamai/cli.py solve "Flow around cylinder with 50x domain size"

# Time stepping control
uv run python src/foamai/cli.py solve "Unsteady flow with Courant number 0.8 and max time step 0.001"

# Mesh resolution
uv run python src/foamai/cli.py solve "Flow around sphere with coarse mesh for 5 seconds"
```

### Mesh Convergence Studies
```bash
# Basic mesh convergence study
uv run python src/foamai/cli.py solve "Flow around cylinder at 10 m/s" --mesh-study

# Advanced mesh convergence with custom parameters
uv run python src/foamai/cli.py solve "Flow around airfoil at 20 m/s" --mesh-study --mesh-levels 5 --mesh-target-params drag_coefficient,lift_coefficient

# Mesh convergence with specific threshold
uv run python src/foamai/cli.py solve "Pipe flow at 2 m/s" --mesh-study --mesh-convergence-threshold 0.5

# Automated mesh convergence (no user approval)
uv run python src/foamai/cli.py solve "Flow around sphere" --mesh-study --mesh-levels 3 --no-user-approval
```

## 🏗️ Architecture

### Agent-Based Workflow
FoamAI uses a multi-agent architecture with specialized agents:

1. **Orchestrator Agent**: Manages workflow progression and error recovery
2. **Natural Language Interpreter**: Parses user prompts into CFD parameters
3. **Mesh Generator**: Creates appropriate mesh configurations
4. **Boundary Condition Agent**: Generates field boundary conditions
5. **Solver Selector**: Chooses optimal solver and settings
6. **Case Writer**: Assembles OpenFOAM case files
7. **User Approval Agent**: Handles interactive configuration review
8. **Simulation Executor**: Runs OpenFOAM simulations
9. **Mesh Convergence Agent**: Performs systematic mesh refinement studies
10. **Visualization Agent**: Creates ParaView visualizations
11. **Results Review Agent**: Analyzes simulation results
12. **Error Handler**: Manages error recovery and retry logic

### Supported Geometries
- **Cylinder**: External flow with O-grid or snappyHexMesh
- **Sphere**: External flow with specialized mesh topology
- **Cube**: External flow around sharp-edged geometry
- **Airfoil**: Aerodynamic analysis with boundary layer meshes
- **Pipe**: Internal flow with structured mesh
- **Channel**: Bounded flow with wall treatment
- **Custom**: STL-based complex geometries

### Flow Types & Analysis
- **Laminar**: Low Reynolds number flows (Re < 2300 for pipes)
- **Turbulent**: High Reynolds number flows with RANS models
- **Transitional**: Flows in transition regime
- **Steady**: Time-independent analysis
- **Unsteady**: Time-dependent with vortex shedding

## 🔧 Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your_openai_api_key

# OpenFOAM Configuration
OPENFOAM_PATH=/path/to/openfoam/installation
OPENFOAM_VERSION=2312
OPENFOAM_VARIANT=ESI  # or Foundation

# ParaView Configuration
PARAVIEW_PATH=/path/to/paraview/installation
PARAVIEW_SERVER_PORT=11111

# Application Settings
LOG_LEVEL=INFO
MAX_SIMULATION_TIME=3600
WORK_DIR=./work
RESULTS_DIR=./results
```

### Configuration File
Settings can also be configured via Python:
```python
from foamai.config import get_settings

settings = get_settings()
settings.openfoam_path = "/path/to/openfoam"
settings.paraview_path = "/path/to/paraview"
settings.max_simulation_time = 7200  # 2 hours

# Mesh convergence settings
settings.mesh_convergence_levels = 4
settings.mesh_convergence_threshold = 1.0  # 1% convergence threshold
settings.mesh_convergence_scale_factor = 2.0  # 2x refinement between levels
```

## 📊 Output Files

### Generated Case Structure
```
work/
├── YYYY-MM-DD_HH-MM-SS_case_name/
│   ├── system/
│   │   ├── blockMeshDict          # Mesh definition
│   │   ├── snappyHexMeshDict      # Complex mesh settings
│   │   ├── controlDict            # Solver control
│   │   ├── fvSchemes              # Numerical schemes
│   │   └── fvSolution             # Solver settings
│   ├── constant/
│   │   ├── polyMesh/              # Generated mesh (from recommended level)
│   │   ├── turbulenceProperties   # Turbulence model
│   │   ├── transportProperties    # Fluid properties
│   │   └── triSurface/           # STL geometries
│   ├── 0/
│   │   ├── U                     # Velocity field
│   │   ├── p                     # Pressure field
│   │   ├── T                     # Temperature field
│   │   └── turbulence_fields     # k, omega, epsilon, nut
│   ├── time_directories/         # Solution data
│   ├── visualization/
│   │   ├── pressure_field.png
│   │   ├── velocity_field.png
│   │   ├── streamlines.png
│   │   ├── vorticity_field.png
│   │   └── surface_pressure.png
│   ├── case_name.foam           # ParaView file
│   └── mesh_convergence/        # Mesh convergence study results
│       ├── convergence_report.txt
│       ├── convergence_data.json
│       ├── case_name_mesh_level_0/  # Coarse mesh case
│       ├── case_name_mesh_level_1/  # Medium mesh case
│       ├── case_name_mesh_level_2/  # Fine mesh case
│       └── case_name_mesh_level_3/  # Extra fine mesh case
```

### Visualization Types
- **Pressure Field**: Contour plots of pressure distribution
- **Velocity Field**: Vector plots and magnitude contours
- **Streamlines**: Flow path visualization with enhanced seeding
- **Vorticity**: Vortex identification and wake analysis
- **Q-Criterion**: Advanced vortex core identification
- **Surface Pressure**: Pressure distribution on geometry surfaces
- **Time-Averaged Fields**: Mean flow analysis for unsteady cases

## 🚨 Error Handling

### Automatic Recovery
- **Parameter Validation**: Checks for physical validity
- **Mesh Quality**: Assesses and improves mesh quality
- **Convergence Issues**: Adjusts solver settings automatically
- **Retry Logic**: Attempts alternative approaches on failure
- **User Guidance**: Provides helpful error messages and suggestions

### Common Issues & Solutions
- **STL File Problems**: Automatic format detection and scaling
- **Mesh Generation Failures**: Adaptive parameter adjustment
- **Solver Divergence**: Automatic relaxation factor tuning
- **Boundary Condition Mapping**: Intelligent patch matching

## 🔍 Advanced Features

### 🧮 **Mesh Convergence Studies**
FoamAI includes a comprehensive mesh convergence analysis system that provides publication-ready results with uncertainty quantification:

#### **Systematic Mesh Refinement**
- **Automatic Mesh Generation**: Creates multiple mesh levels with systematic refinement (2x scaling factor)
- **Intelligent Scaling**: Adjusts both cell count and refinement levels progressively
- **Quality Control**: Maintains mesh quality across all refinement levels
- **Geometry-Aware**: Adapts refinement strategy based on geometry complexity

#### **Grid Convergence Index (GCI) Analysis**
- **Richardson Extrapolation**: Calculates theoretical exact solution
- **Uncertainty Quantification**: Provides error bounds for simulation results
- **Convergence Assessment**: Determines if results are mesh-independent
- **Safety Factors**: Uses established GCI safety factors (1.25 for 3+ grids)

#### **Parameter Monitoring**
- **Drag Coefficient**: For external flow geometries (cylinder, sphere, airfoil)
- **Pressure Drop**: For internal flows (pipes, channels)
- **Maximum Velocity**: Universal parameter for all flow types
- **Strouhal Number**: For vortex shedding analysis
- **Friction Factor**: For pipe flow analysis
- **Custom Parameters**: Support for user-defined monitoring parameters

#### **Automated Convergence Assessment**
- **Threshold-Based**: Configurable convergence criteria (default: 1% change)
- **Trend Analysis**: Monitors convergence trends across mesh levels
- **Optimal Mesh Selection**: Recommends best mesh level balancing accuracy and cost
- **Uncertainty Bounds**: Provides confidence intervals for results

#### **Professional Reporting**
- **Detailed Analysis**: Comprehensive convergence report with statistics
- **Visualization**: Convergence plots and trend analysis
- **Publication Ready**: Results formatted for academic/industrial use
- **Recommendation Engine**: Suggests optimal mesh configuration

### STL File Processing
- **Format Detection**: Automatic ASCII/binary STL detection
- **Unit Recognition**: Intelligent unit detection and scaling
- **Geometry Validation**: Bounding box analysis and error checking
- **Rotation Support**: Natural language geometry rotation
- **Multi-Scale Handling**: Automatic scaling for CFD-appropriate sizes

### Mesh Quality Assessment
- **Aspect Ratio**: Cell shape quality analysis
- **Skewness**: Mesh orthogonality checking
- **Cell Count**: Automatic refinement level selection
- **Y+ Estimation**: Boundary layer mesh assessment
- **Recommendations**: Automatic mesh improvement suggestions
- **Convergence Validation**: Grid Convergence Index (GCI) analysis for mesh independence
- **Richardson Extrapolation**: Theoretical exact solution estimation with uncertainty bounds

### Vortex Shedding Analysis
- **Reynolds Number Thresholds**: Automatic detection based on geometry
- **Enhanced Seeding**: Optimized streamline seed placement
- **Wake Capture**: Specialized visualization for wake regions
- **Time-Dependent Analysis**: Unsteady flow visualization
- **Strouhal Number**: Automatic frequency analysis

### Boundary Layer Treatment
- **Wall Functions**: Automatic wall treatment selection
- **Layer Insertion**: Boundary layer mesh generation
- **Y+ Control**: Near-wall mesh sizing
- **Heat Transfer**: Temperature boundary conditions
- **Turbulence Fields**: Automatic turbulence field initialization

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:
- Code style and standards
- Testing requirements
- Pull request process
- Development setup

## 📚 Documentation

- **User Guide**: Comprehensive usage examples
- **API Reference**: Agent and function documentation
- **Developer Guide**: Architecture and extension guide
- **Troubleshooting**: Common issues and solutions

## 🎯 Roadmap

### Planned Features
- **More Solvers**: Support for additional OpenFOAM solvers
- **Heat Transfer**: Enhanced thermal analysis capabilities
- **Multiphase Flows**: Advanced VOF and Eulerian methods
- **Chemical Reactions**: Combustion and reaction modeling
- **Optimization**: Automated design optimization
- **Cloud Integration**: Remote simulation capabilities
- **Advanced Mesh Convergence**: Adaptive mesh refinement and error estimation
- **Parallel Mesh Studies**: Distributed mesh convergence analysis

### Current Limitations
- Limited to incompressible flows (compressible support planned)
- Single-phase flows (multiphase support in development)
- English language only (multilingual support planned)
- Requires OpenFOAM and ParaView installation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenFOAM community for the excellent CFD toolkit
- ParaView team for visualization capabilities
- OpenAI for natural language processing
- Contributors and beta testers

---

**Made with ❤️ by the FoamAI team**

*Transform your CFD workflow with the power of AI*

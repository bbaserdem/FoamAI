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
  - `simpleFoam`: Steady-state incompressible flows with SIMPLE algorithm
  - `pimpleFoam`: Transient incompressible flows with PIMPLE algorithm and vortex shedding
  - `pisoFoam`: Transient incompressible flows using PISO algorithm for highly unsteady cases
  - `interFoam`: Multiphase flows using VOF method with interface compression
  - `rhoPimpleFoam`: Compressible transient flows with thermophysical properties
  - `sonicFoam`: Transonic/supersonic compressible flows with flux limiters
  - `chtMultiRegionFoam`: Conjugate heat transfer with multiple regions
  - `reactingFoam`: Combustion and chemical reactions with finite rate chemistry
  - `buoyantSimpleFoam`: Heat transfer with buoyancy effects in steady flows
  - `MRFSimpleFoam`: Steady incompressible flows with rotating machinery (MRF)
- **Intelligent Solver Selection**: 
  - AI-powered solver recommendation with confidence scoring
  - Context-aware decision making based on geometry, Reynolds number, and flow conditions
  - Alternative solver suggestions with detailed explanations
- **Solver-Specific Optimizations**:
  - **simpleFoam**: SIMPLE algorithm with relaxation factor tuning
  - **pimpleFoam**: PIMPLE algorithm with automatic time stepping
  - **pisoFoam**: PISO algorithm for highly unsteady flows
  - **interFoam**: VOF method with interface compression
  - **rhoPimpleFoam**: Compressible flow with thermophysical properties
  - **sonicFoam**: Transonic/supersonic flow with flux limiters
  - **chtMultiRegionFoam**: Conjugate heat transfer with multiple regions
- **Adaptive Time Stepping**: 
  - Automatic time step calculation based on Courant number
  - Dynamic adjustment during simulation based on stability
  - Stability monitoring with automatic reduction
- **Turbulence Models**: 
  - **RANS**: k-epsilon, k-omega SST, Spalart-Allmaras
  - **LES**: Smagorinsky, Dynamic Smagorinsky, WALE
  - **DNS**: Direct numerical simulation for low Reynolds numbers
  - **Transition Models**: Automatic transition model selection
- **Numerical Schemes**: 
  - **Gradient Schemes**: Gauss linear, cellLimited, faceLimited
  - **Divergence Schemes**: Gauss upwind, linearUpwind, QUICK, limitedLinear
  - **Laplacian Schemes**: Gauss linear corrected, uncorrected
  - **Interpolation Schemes**: Linear, upwind, weighted
- **Linear Solver Configuration**: 
  - **GAMG**: Geometric algebraic multigrid for pressure
  - **PBiCGStab**: Preconditioned BiCGStab for velocity
  - **smoothSolver**: Smooth solver for turbulence fields
  - **Preconditioners**: DIC, DILU, GAMG
  - **Convergence Criteria**: Residual-based with automatic adjustment

### 🕸️ **Advanced Mesh Generation**
- **Multiple Mesh Topologies**:
  - **BlockMesh**: Structured hexahedral meshes for simple geometries
  - **SnappyHexMesh**: Unstructured meshes with automatic surface wrapping
  - **O-Grid**: Specialized cylindrical mesh topology for perfect cylinder flows
  - **Structured Internal**: Optimized structured meshes for pipes and channels
- **Adaptive Mesh Parameters**: 
  - Automatic cell count calculation based on geometry size
  - Dynamic domain sizing with configurable multipliers
  - STL-aware mesh adaptation with unit detection and scaling
- **Mesh Quality Control**: 
  - Built-in skewness and aspect ratio assessment
  - Automatic mesh improvement suggestions
  - Y+ estimation for boundary layer meshes
- **Geometry-Specific Optimizations**:
  - **Cylinder**: O-grid topology with proper wake refinement
  - **Sphere**: 3D spherical mesh with radial clustering
  - **Airfoil**: Boundary layer mesh with leading/trailing edge refinement
  - **Pipe**: Structured cylindrical mesh with inlet/outlet zones
  - **Channel**: Structured rectangular mesh with wall treatment
  - **Custom STL**: Adaptive background mesh with surface refinement
- **Surface Layer Insertion**: Automatic boundary layer mesh generation with expansion ratios
- **Mesh Convergence Studies**: Systematic mesh refinement with Grid Convergence Index (GCI) analysis
- **Real-time Mesh Validation**: Continuous quality monitoring during generation

### 🌊 **Boundary Conditions**
- **Intelligent Mapping**: Automatic boundary condition mapping to mesh patches
- **Comprehensive Field Support**: 
  - **Velocity (U)**: noSlip, fixedValue, zeroGradient, slip, symmetry
  - **Pressure (p, p_rgh)**: fixedValue, zeroGradient, totalPressure, inletOutlet
  - **Temperature (T)**: fixedValue, zeroGradient, fixedGradient, convective
  - **Turbulence Fields**: 
    - **k** (Turbulent Kinetic Energy): kqRWallFunction, fixedValue, zeroGradient
    - **omega** (Specific Dissipation Rate): omegaWallFunction, fixedValue, zeroGradient
    - **epsilon** (Dissipation Rate): epsilonWallFunction, fixedValue, zeroGradient
    - **nut** (Turbulent Viscosity): nutkWallFunction, calculated, zeroGradient
  - **Multiphase Fields**:
    - **alpha.water** (Volume Fraction): fixedValue, zeroGradient, inletOutlet
    - **p_rgh** (Hydrostatic Pressure): fixedValue, zeroGradient, totalPressure
- **Geometry-Specific Conditions**: Optimized boundary conditions for each geometry type
- **AI-Enhanced Generation**: OpenAI-powered boundary condition optimization with solver-specific recommendations
- **Patch Type Adaptation**: Automatic adjustment for wall, symmetry, empty, and cyclic patches
- **Heat Transfer**: Automatic temperature field generation with proper thermal boundary conditions

### 📊 **Visualization & Analysis**
- **Comprehensive Visualization Types**:
  - **Pressure Field**: Contour plots with customizable color maps
  - **Velocity Field**: Vector plots and magnitude contours
  - **Streamlines**: Enhanced seeding with wake-focused placement
  - **Surface Analysis**: Surface pressure and shear stress distribution
  - **Advanced Vortex Analysis**:
    - **Vorticity Magnitude**: 3D vorticity field visualization
    - **Q-Criterion**: Vortex core identification with isosurfaces
    - **Time-Averaged Flow**: Mean flow analysis for unsteady cases
  - **Temperature Distribution**: Thermal field visualization for heat transfer
  - **Turbulence Fields**: k, omega, epsilon, and nut visualization
  - **Multiphase Visualization**: Volume fraction and interface tracking
- **Intelligent Visualization Selection**: Automatic visualization type selection based on:
  - Geometry type (cylinder → vortex shedding analysis)
  - Flow conditions (high Re → turbulence visualization)
  - Solver type (interFoam → multiphase fields)
  - Time dependency (unsteady → animation support)
- **ParaView Integration**: 
  - Automatic .foam file generation
  - ParaView state files for reproducible visualizations
  - Batch processing with pvpython
  - Animation support for time-dependent flows
- **Multiple Export Formats**: PNG images, VTK data, ParaView state files
- **Custom Visualization Scripts**: Automated ParaView Python script generation

### 🔄 **Workflow Management**
- **Multi-Agent Architecture**: Specialized agents for each workflow step:
  1. **Orchestrator Agent**: Manages workflow progression and error recovery
  2. **Natural Language Interpreter**: Parses user prompts with OpenAI GPT-4
  3. **Mesh Generator**: Creates geometry-specific mesh configurations
  4. **Boundary Condition Agent**: Generates physics-accurate boundary conditions
  5. **Solver Selector**: AI-powered solver selection with confidence scoring
  6. **Case Writer**: Assembles complete OpenFOAM case directories
  7. **User Approval Agent**: Interactive configuration review and modification
  8. **Simulation Executor**: Monitors OpenFOAM execution with real-time progress
  9. **Mesh Convergence Agent**: Orchestrates systematic mesh refinement studies
  10. **Visualization Agent**: Generates publication-quality visualizations
  11. **Results Review Agent**: Analyzes results and manages iterative workflows
  12. **Error Handler**: AI-powered error explanation and recovery suggestions
- **Intelligent Error Recovery**: 
  - **AI-Powered Error Analysis**: OpenAI-based error explanation in user-friendly language
  - **Automatic Parameter Adjustment**: Dynamic solver and mesh parameter tuning
  - **Retry Logic**: Intelligent retry strategies with alternative approaches
  - **User-Guided Recovery**: Interactive error resolution with specific suggestions
  - **Context-Aware Solutions**: Error handling based on geometry, solver, and flow conditions
- **Progress Tracking**: Real-time progress indicators with ETA calculations
- **Iterative Workflow**: Support for multiple simulation iterations with result comparison
- **GPU Acceleration Support**: 
  - Optional GPU acceleration with `--use-gpu` flag
  - PETSc4Foam and AmgX backend support
  - Automatic GPU detection and configuration
  - Fallback to CPU if GPU libraries unavailable

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

**Command Format:**
```bash
uv run python src/foamai/cli.py solve "Your CFD problem description" [OPTIONS]
```

**Examples:**
```bash
# Basic flow simulation
uv run python src/foamai/cli.py solve "Flow around a cylinder at 10 m/s"

# With Reynolds number specification
uv run python src/foamai/cli.py solve "Flow around cylinder at Re 1000 with coarse mesh"

# Use custom STL geometry
uv run python src/foamai/cli.py solve "Turbulent flow around car at 60 m/s" --stl-file path/to/car.stl

# Skip user approval for automated runs
uv run python src/foamai/cli.py solve "Flow in pipe with 0.1m diameter" --no-user-approval

# Enable verbose output for debugging
uv run python src/foamai/cli.py solve "Flow over airfoil" --verbose

# GPU acceleration
uv run python src/foamai/cli.py solve "Flow around cylinder" --use-gpu --verbose

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
- `--use-gpu`: Enable GPU acceleration (requires PETSc4Foam or AmgX)

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

### 🎯 **GPU Acceleration**
FoamAI includes optional GPU acceleration support for compatible OpenFOAM installations:

#### **GPU Backend Support**
- **PETSc4Foam**: GPU-accelerated linear solvers using PETSc
- **AmgX**: NVIDIA-optimized algebraic multigrid solvers
- **Automatic Detection**: Detects available GPU libraries and configures automatically
- **Fallback Support**: Gracefully falls back to CPU if GPU libraries unavailable

#### **GPU Usage**
```bash
# Enable GPU acceleration
uv run python src/foamai/cli.py solve "Flow around cylinder" --use-gpu

# Explicit GPU request in prompt
uv run python src/foamai/cli.py solve "Flow around cylinder with GPU acceleration"
```

#### **GPU Configuration**
- **Automatic Configuration**: Detects NVIDIA GPUs and CUDA installation
- **Backend Selection**: Automatically selects best available GPU backend
- **Memory Management**: Optimizes GPU memory usage for large simulations
- **Multi-GPU Support**: Supports multiple GPU configurations (planned)

#### **Performance Benefits**
- **Large Mesh Simulations**: Significant speedup for meshes > 100k cells
- **Pressure Solvers**: GPU-accelerated GAMG and AMG solvers
- **Turbulence Models**: Accelerated turbulence field calculations
- **Time-Dependent Flows**: Faster time integration for unsteady simulations

#### **Installation Requirements**
- NVIDIA GPU with CUDA support
- PETSc4Foam compiled with GPU support, OR
- AmgX library for NVIDIA GPUs
- CUDA 11.0+ runtime environment

```bash
# Check GPU availability
uv run python src/foamai/cli.py solve "Flow around cylinder" --use-gpu --verbose
```

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
- GPU acceleration requires separate installation of PETSc4Foam or AmgX
- English language only (multilingual support planned)
- Requires OpenFOAM and ParaView installation
- Some advanced solvers may need additional OpenFOAM modules

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

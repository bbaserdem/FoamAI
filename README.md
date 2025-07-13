# FoamAI - Natural Language CFD Assistant

AI-powered computational fluid dynamics (CFD) assistant that converts natural language descriptions into OpenFOAM simulations with ParaView visualization.

## Project Structure

```
FoamAI/
├── src/                     # Core application code
│   ├── foamai-core/        # Core simulation logic
│   ├── foamai-server/      # FastAPI backend server
│   ├── foamai-client/      # Client library
│   └── foamai-desktop/     # Desktop application
├── infra/                  # AWS infrastructure (Terraform)
├── docker/                 # Container definitions
├── tests/                  # Test files
├── examples/               # Demo scripts and examples
├── dev/                    # Development utilities
├── docs/                   # Project documentation
└── .github/               # CI/CD workflows
```

## Quick Start

### Prerequisites

- Python 3.11+
- OpenFOAM 10
- ParaView 5.10+
- Docker & Docker Compose

### Development Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/bbaserdem/FoamAI.git
cd FoamAI
uv sync
```

2. **Local development:**
```bash
# Start local services
docker-compose -f dev/docker-compose.local.yml up -d

# Run examples
python examples/demo_user_approval.py
```

3. **Run tests:**
```bash
python -m pytest tests/
```

### Production Deployment

1. **Build and deploy via Terraform:**
```bash
cd infra
terraform apply
```

2. **Images are automatically built via GitHub Actions and available at:**
- `ghcr.io/bbaserdem/foamai/api:latest`
- `ghcr.io/bbaserdem/foamai/openfoam:latest` 
- `ghcr.io/bbaserdem/foamai/pvserver:latest`

## Documentation

- **[DevOps Documentation](docs/task_4_devops/)** - Deployment and infrastructure
- **[Testing Guide](docs/TESTING.md)** - Comprehensive testing documentation
- **[Development Workflow](docs/)** - Additional development guides

## Architecture

- **Backend:** FastAPI server with Celery workers
- **CFD Engine:** OpenFOAM 10 with Python integration
- **Visualization:** ParaView server for remote rendering
- **Infrastructure:** AWS EC2 with Terraform
- **CI/CD:** GitHub Actions with container registry

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

## Contributing

1. Check the [docs/](docs/) directory for project documentation
2. Run tests from the [tests/](tests/) directory
3. Try examples from the [examples/](examples/) directory
4. Use development configurations from [dev/](dev/)

## License

See [LICENSE](LICENSE) for details.

# FoamAI Desktop Application

This is the desktop GUI for FoamAI, providing an intuitive interface for CFD simulations with natural language input.

## Quick Start

### Prerequisites
- **Python 3.12** (specifically version 3.12 for ParaView compatibility)
- **ParaView 6.0.0** (exact version required)

### One-Command Setup & Run

```bash
# On Windows (PowerShell/Command Prompt)
bash setup_desktop.sh

# On macOS/Linux
./setup_desktop.sh
```

This script will:
1. Verify Python 3.12 and ParaView 6.0.0 installations
2. Locate ParaView automatically
3. Set up the PYTHONPATH environment variable
4. Create virtual environment and install dependencies
5. Launch the application

### Options

```bash
# Custom ParaView location
./setup_desktop.sh --paraview-path "/path/to/paraview"

# Setup without running
./setup_desktop.sh --skip-run

# Help
./setup_desktop.sh --help
```

### Manual Run (After Setup)

**Windows:**
```bash
venv\Scripts\activate
set PYTHONPATH=.typing;C:\Program Files\ParaView 6.0.0\bin\Lib\site-packages
python -m foamai_desktop.main
```

**macOS/Linux:**
```bash
source venv/bin/activate
export PYTHONPATH=".typing:/Applications/ParaView-6.0.0.app/Contents/bin/site-packages"
python -m foamai_desktop.main
```

## Troubleshooting

- **Python 3.12 not found**: Install from [python.org](https://www.python.org/downloads/)
- **ParaView not detected**: Install from [paraview.org](https://www.paraview.org/download/) or use `--paraview-path`
- **Permission issues**: Run `chmod +x setup_desktop.sh` or use `bash setup_desktop.sh`

## What's in This Directory

- `setup_desktop.sh` - Automated setup script
- `foamai_desktop/` - Main application source code
- `venv/` - Virtual environment (created after first run)
- `.typing/` - Custom type definitions (created after first run)
- `pyproject.toml` - Project dependencies

For complete documentation, see the main project [README](../../README.md). 
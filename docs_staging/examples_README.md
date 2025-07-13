# Examples Directory

This directory contains demo scripts and examples showing how to use FoamAI components.

## Available Examples

- `demo_user_approval.py` - Demonstrates the user approval workflow for mesh generation
- `open_in_paraview.py` - Shows how to launch ParaView with simulation results

## Running Examples

From the project root:

```bash
# Run the user approval demo
uv run python examples/demo_user_approval.py

# Open simulation results in ParaView
uv run python examples/open_in_paraview.py
```

## Prerequisites

Examples require:
- FoamAI dependencies installed (`uv sync`)
- OpenFOAM and ParaView installations
- Sample simulation data (generated from running actual simulations)

For complete development setup, see the [Contributing Guide](Contributing.md).

## Purpose

These examples are intended for:
- New developers learning the codebase
- Testing component integration
- Demonstrating workflow capabilities
- Documentation and tutorials 
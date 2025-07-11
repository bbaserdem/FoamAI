# Tests Directory

This directory contains all test files for the FoamAI project.

## Test Files

- `test_user_approval.py` - Tests for user approval workflow
- `test_new_solvers.py` - Tests for solver selection and physics types  
- `test_visualization_demo.py` - Tests for ParaView visualization integration

## Running Tests

From the project root:

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python tests/test_user_approval.py

# Run with verbose output
python -m pytest tests/ -v
```

## Test Environment

Tests require:
- OpenFOAM installation (for solver tests)
- ParaView installation (for visualization tests)
- All project dependencies installed via `uv sync` 
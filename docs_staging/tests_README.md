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
uv run pytest tests/

# Run specific test file
uv run python tests/test_user_approval.py

# Run with verbose output
uv run pytest tests/ -v

# Run with coverage
uv run pytest --cov=src/ --cov-report=html
```

## Test Environment

Tests require:
- OpenFOAM installation (for solver tests)
- ParaView installation (for visualization tests)
- All project dependencies installed via `uv sync --group test`

For complete testing setup and workflows, see the [Contributing Guide](Contributing.md#testing-infrastructure). 
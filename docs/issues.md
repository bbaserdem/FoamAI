# FoamAI Development Issues - Current State

## Overview
Working on the FoamAI natural language to CFD simulation pipeline. The main issue is with the solver selection logic and how it maps physics types to appropriate OpenFOAM solvers.

## Current Modified Files
- `src/agents/case_writer.py`
- `src/agents/nl_interpreter.py` 
- `src/agents/solver_selector.py`
- `src/agents/state.py`
- `test_new_solvers.py` (new file, untracked)

## Key Issues Identified

### 1. Solver Mapping Incomplete
**File**: `src/agents/solver_selector.py`

The solver mapping dictionary is missing several physics types:
- "heat_transfer" 
- "multiphase"
- "reacting"
- Other physics types that may come from NL interpretation

**Current Implementation**:
```python
SOLVER_MAPPING = {
    "incompressible": "simpleFoam",
    "compressible": "rhoSimpleFoam",
    "turbulent": "simpleFoam",
    # Missing mappings for other physics types
}
```

### 2. Physics Type Detection Mismatch
**File**: `src/agents/nl_interpreter.py`

The NL interpreter can output physics types that don't have corresponding solver mappings:
- Line 126-152: Maps various descriptions to physics types like "heat_transfer", "multiphase", etc.
- These don't align with the limited solver mappings

### 3. Error Handling
When no solver is found for a physics type, the system fails with:
```
No solver found for physics type: heat_transfer
```

## Test File Created
`test_new_solvers.py` - Contains test cases for different physics types to verify solver selection

## What Needs to Be Done Tomorrow

### Immediate Tasks:
1. **Expand SOLVER_MAPPING** in `solver_selector.py`:
   - Add mappings for all physics types that can be output by the NL interpreter
   - Consider combinations of physics (e.g., turbulent + heat_transfer)
   - Add appropriate OpenFOAM solvers for each case

2. **Review Physics Type Detection**:
   - Ensure NL interpreter outputs are consistent with solver expectations
   - May need to standardize physics type naming/structure

3. **Implement Fallback Logic**:
   - Add default solver selection when exact match isn't found
   - Consider physics similarity for solver selection

4. **Test Coverage**:
   - Run the test_new_solvers.py file to verify all physics types work
   - Add more comprehensive test cases

### Architecture Considerations:
- The current design has a disconnect between what the NL interpreter outputs and what the solver selector expects
- May need an intermediate mapping layer or more sophisticated solver selection logic
- Consider whether physics types should be a list/set rather than single values

## Example Command Being Used:
```
uv run python src/foamai/cli.py solve "Prompt here" --verbose --export-images
```

## Next Steps:
1. Review the complete list of OpenFOAM solvers and their capabilities
2. Create a comprehensive mapping between physics types and appropriate solvers
3. Test with various natural language inputs to ensure robust solver selection
4. Consider implementing a more sophisticated solver selection algorithm that can handle:
   - Multiple physics types
   - Solver capabilities/limitations
   - Performance considerations 
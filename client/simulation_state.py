"""
Simulation State Management
Tracks the current state of mesh, solver, and parameters for CFD simulation setup
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

class ComponentState(Enum):
    """State of a simulation component"""
    EMPTY = "empty"
    POPULATED = "populated"
    LOCKED = "locked"
    ERROR = "error"

@dataclass
class MeshData:
    """Data for mesh component"""
    description: str = ""
    file_path: Optional[str] = None
    file_type: str = ""  # stl, foam, etc.
    content: Optional[str] = None
    generated_by_ai: bool = False
    
    def is_empty(self) -> bool:
        return not self.description and not self.file_path

@dataclass
class SolverData:
    """Data for solver component"""
    name: str = ""
    description: str = ""
    justification: str = ""
    parameters: Dict[str, Any] = None
    available_solvers: Dict[str, str] = None  # name -> description
    generated_by_ai: bool = False
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.available_solvers is None:
            self.available_solvers = {
                "simpleFoam": "Steady-state solver for incompressible, turbulent flows",
                "pimpleFoam": "Transient solver for incompressible, turbulent flows",
                "icoFoam": "Transient solver for incompressible, laminar flows",
                "buoyantSimpleFoam": "Steady-state solver for buoyant, incompressible flows",
                "rhoPimpleFoam": "Transient solver for compressible, turbulent flows",
                "potentialFoam": "Potential flow solver for incompressible flows"
            }
    
    def is_empty(self) -> bool:
        return not self.name and not self.description

@dataclass
class ParametersData:
    """Data for parameters component"""
    description: str = ""
    parameters: Dict[str, Any] = None
    file_path: Optional[str] = None
    content: Optional[str] = None
    generated_by_ai: bool = False
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
    
    def is_empty(self) -> bool:
        return not self.description and not self.parameters and not self.file_path

class SimulationState:
    """Main simulation state manager"""
    
    def __init__(self):
        self.mesh = MeshData()
        self.solver = SolverData()
        self.parameters = ParametersData()
        
        # Component states
        self.mesh_state = ComponentState.EMPTY
        self.solver_state = ComponentState.EMPTY
        self.parameters_state = ComponentState.EMPTY
        
        # Lock states
        self.mesh_locked = False
        self.solver_locked = False
        self.parameters_locked = False
        
        # Current task state
        self.current_task_id: Optional[str] = None
        self.processing = False
    
    def reset(self):
        """Reset all simulation state"""
        self.mesh = MeshData()
        self.solver = SolverData()
        self.parameters = ParametersData()
        self.mesh_state = ComponentState.EMPTY
        self.solver_state = ComponentState.EMPTY
        self.parameters_state = ComponentState.EMPTY
        self.mesh_locked = False
        self.solver_locked = False
        self.parameters_locked = False
        self.current_task_id = None
        self.processing = False
    
    def update_mesh(self, mesh_data: MeshData):
        """Update mesh data if not locked"""
        if not self.mesh_locked:
            self.mesh = mesh_data
            self.mesh_state = ComponentState.POPULATED if not mesh_data.is_empty() else ComponentState.EMPTY
    
    def update_solver(self, solver_data: SolverData):
        """Update solver data if not locked"""
        if not self.solver_locked:
            self.solver = solver_data
            self.solver_state = ComponentState.POPULATED if not solver_data.is_empty() else ComponentState.EMPTY
    
    def update_parameters(self, parameters_data: ParametersData):
        """Update parameters data if not locked"""
        if not self.parameters_locked:
            self.parameters = parameters_data
            self.parameters_state = ComponentState.POPULATED if not parameters_data.is_empty() else ComponentState.EMPTY
    
    def set_mesh_locked(self, locked: bool):
        """Set mesh lock state"""
        self.mesh_locked = locked
        if locked and self.mesh_state == ComponentState.POPULATED:
            self.mesh_state = ComponentState.LOCKED
        elif not locked and self.mesh_state == ComponentState.LOCKED:
            self.mesh_state = ComponentState.POPULATED
    
    def set_solver_locked(self, locked: bool):
        """Set solver lock state"""
        self.solver_locked = locked
        if locked and self.solver_state == ComponentState.POPULATED:
            self.solver_state = ComponentState.LOCKED
        elif not locked and self.solver_state == ComponentState.LOCKED:
            self.solver_state = ComponentState.POPULATED
    
    def set_parameters_locked(self, locked: bool):
        """Set parameters lock state"""
        self.parameters_locked = locked
        if locked and self.parameters_state == ComponentState.POPULATED:
            self.parameters_state = ComponentState.LOCKED
        elif not locked and self.parameters_state == ComponentState.LOCKED:
            self.parameters_state = ComponentState.POPULATED
    
    def can_run_simulation(self) -> bool:
        """Check if simulation can be run (all components populated)"""
        return (self.mesh_state in [ComponentState.POPULATED, ComponentState.LOCKED] and
                self.solver_state in [ComponentState.POPULATED, ComponentState.LOCKED] and
                self.parameters_state in [ComponentState.POPULATED, ComponentState.LOCKED] and
                not self.processing)
    
    def get_unlocked_components(self) -> list:
        """Get list of components that are not locked"""
        unlocked = []
        if not self.mesh_locked:
            unlocked.append("mesh")
        if not self.solver_locked:
            unlocked.append("solver")
        if not self.parameters_locked:
            unlocked.append("parameters")
        return unlocked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for API calls"""
        return {
            "mesh": {
                "description": self.mesh.description,
                "file_path": self.mesh.file_path,
                "file_type": self.mesh.file_type,
                "locked": self.mesh_locked
            },
            "solver": {
                "name": self.solver.name,
                "description": self.solver.description,
                "justification": self.solver.justification,
                "parameters": self.solver.parameters,
                "locked": self.solver_locked
            },
            "parameters": {
                "description": self.parameters.description,
                "parameters": self.parameters.parameters,
                "file_path": self.parameters.file_path,
                "locked": self.parameters_locked
            },
            "unlocked_components": self.get_unlocked_components()
        } 
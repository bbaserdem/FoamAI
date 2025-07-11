"""CFD State Schema for LangGraph workflow."""

from typing import Any, Dict, List, Optional, TypedDict
from enum import Enum


class CFDStep(str, Enum):
    """Enumeration of CFD workflow steps."""
    START = "start"
    NL_INTERPRETATION = "nl_interpretation"
    MESH_GENERATION = "mesh_generation"
    BOUNDARY_CONDITIONS = "boundary_conditions"
    SOLVER_SELECTION = "solver_selection"
    CASE_WRITING = "case_writing"
    USER_APPROVAL = "user_approval"
    SIMULATION = "simulation"
    VISUALIZATION = "visualization"
    RESULTS_REVIEW = "results_review"
    ERROR_HANDLER = "error_handler"
    COMPLETE = "complete"
    ERROR = "error"


class GeometryType(str, Enum):
    """Supported geometry types."""
    CYLINDER = "cylinder"
    AIRFOIL = "airfoil"
    PIPE = "pipe"
    CHANNEL = "channel"
    SPHERE = "sphere"
    CUBE = "cube"
    CUSTOM = "custom"


class SolverType(str, Enum):
    """Available OpenFOAM solvers."""
    SIMPLE_FOAM = "simpleFoam"
    PIMPLE_FOAM = "pimpleFoam"
    INTER_FOAM = "interFoam"  # Multiphase flow solver
    RHO_PIMPLE_FOAM = "rhoPimpleFoam"  # Compressible transient solver
    CHT_MULTI_REGION_FOAM = "chtMultiRegionFoam"  # Conjugate heat transfer
    REACTING_FOAM = "reactingFoam"  # Reactive flows with combustion
    # Future additions:
    # RHOSIMPLE_FOAM = "rhoSimpleFoam"  # Compressible steady
    # BUOYANT_SIMPLE_FOAM = "buoyantSimpleFoam"  # Heat transfer with buoyancy


class FlowType(str, Enum):
    """Flow analysis types."""
    LAMINAR = "laminar"
    TURBULENT = "turbulent"
    TRANSITIONAL = "transitional"


class AnalysisType(str, Enum):
    """Analysis types."""
    STEADY = "steady"
    UNSTEADY = "unsteady"


class CFDState(TypedDict):
    """State structure that flows between all agents in the CFD workflow."""
    
    # User input
    user_prompt: str
    stl_file: Optional[str]  # Path to STL file for custom geometry
    
    # Parsed parameters from NL interpretation
    parsed_parameters: Dict[str, Any]
    geometry_info: Dict[str, Any]
    
    # Agent-specific outputs
    mesh_config: Dict[str, Any]
    boundary_conditions: Dict[str, Any]
    solver_settings: Dict[str, Any]
    
    # File paths and directories
    case_directory: str
    work_directory: str
    
    # Simulation results
    simulation_results: Dict[str, Any]
    visualization_path: str
    
    # Error handling
    errors: List[str]
    warnings: List[str]
    
    # Workflow control
    current_step: CFDStep
    retry_count: int
    max_retries: int
    error_recovery_attempts: Optional[Dict[str, bool]]
    
    # User approval tracking
    user_approved: bool
    user_approval_enabled: bool
    
    # Quality metrics
    mesh_quality: Optional[Dict[str, Any]]
    convergence_metrics: Optional[Dict[str, Any]]
    
    # Configuration
    verbose: bool
    export_images: bool
    output_format: str
    force_validation: bool
    
    # Iterative workflow and conversation context
    session_history: List[Dict[str, Any]]  # History of all runs in this session
    current_iteration: int  # Current iteration number (0-based)
    conversation_active: bool  # Whether to continue the conversation or exit
    previous_results: Optional[Dict[str, Any]]  # Results from previous iteration for comparison 
    
    # Remote execution configuration
    execution_mode: str  # "local" or "remote"
    server_url: Optional[str]  # URL of remote OpenFOAM server
    project_name: Optional[str]  # Name of project on remote server
    
    # User approval workflow fields for desktop UI integration
    awaiting_user_approval: bool  # True when workflow is paused for user approval
    workflow_paused: bool  # True when workflow is paused waiting for external input
    config_summary: Optional[Dict[str, Any]]  # Configuration summary for UI display 
"""Configuration management for FoamAI."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FoamAISettings(BaseSettings):
    """FoamAI application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    
    # OpenFOAM Configuration
    openfoam_path: Optional[str] = Field(None, description="Path to OpenFOAM installation")
    openfoam_version: str = Field("2312", description="OpenFOAM version")
    openfoam_variant: str = Field("ESI", description="OpenFOAM variant: ESI or Foundation")
    openfoam_source_script: Optional[str] = Field(None, description="Path to the script to source to activate the OpenFOAM environment")

    # ParaView Configuration
    paraview_path: Optional[str] = Field(None, description="Path to ParaView installation")
    paraview_server_port: int = Field(11111, description="ParaView server port")
    
    # Docker Configuration
    use_docker: bool = Field(False, description="Use Docker for OpenFOAM execution")
    docker_container_name: Optional[str] = Field(None, description="Name of the Docker container for OpenFOAM")
    docker_mount_path: Optional[str] = Field(None, description="Path inside the Docker container where the project is mounted")

    # Application Configuration
    log_level: str = Field("INFO", description="Logging level")
    max_simulation_time: int = Field(3600, description="Maximum simulation time in seconds")
    work_dir: str = Field("./work", description="Working directory for cases")
    results_dir: str = Field("./results", description="Results directory")
    
    # Development Configuration
    debug: bool = Field(False, description="Enable debug mode")
    verbose: bool = Field(False, description="Enable verbose logging")
    
    def get_work_dir(self) -> Path:
        """Get the work directory as a Path object."""
        return Path(self.work_dir).expanduser().resolve()
    
    def get_results_dir(self) -> Path:
        """Get the results directory as a Path object."""
        return Path(self.results_dir).expanduser().resolve()
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        work_dir = self.get_work_dir()
        results_dir = self.get_results_dir()
        
        work_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (work_dir / "logs").mkdir(exist_ok=True)
        (work_dir / "temp").mkdir(exist_ok=True)
        (results_dir / "visualizations").mkdir(exist_ok=True)
    
    def get_openfoam_env(self) -> dict:
        """Get OpenFOAM environment variables."""
        env = os.environ.copy()
        
        if self.openfoam_path:
            # Determine platform directory based on variant
            if self.openfoam_variant == "Foundation":
                # Foundation version typically uses linux64GccDPOpt
                platform_dir = "linux64GccDPOpt"
            else:
                # ESI version uses linux64GccDPInt32Opt
                platform_dir = "linux64GccDPInt32Opt"
            
            # Add OpenFOAM paths
            foam_bin = Path(self.openfoam_path) / "platforms" / platform_dir / "bin"
            if foam_bin.exists():
                env["PATH"] = f"{foam_bin}:{env.get('PATH', '')}"
            
            # Set OpenFOAM environment variables
            env["FOAM_INSTALL_DIR"] = str(self.openfoam_path)
            env["WM_PROJECT_VERSION"] = self.openfoam_version
        
        return env
    
    def get_paraview_env(self) -> dict:
        """Get ParaView environment variables."""
        env = os.environ.copy()
        
        if self.paraview_path:
            pv_bin = Path(self.paraview_path) / "bin"
            if pv_bin.exists():
                env["PATH"] = f"{pv_bin}:{env.get('PATH', '')}"
        
        # Set display for headless rendering
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0.0"
        
        return env
    
    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        return bool(self.openai_api_key)
    
    def get_configuration_status(self) -> dict:
        """Get detailed configuration status."""
        return {
            "openai_api_key": bool(self.openai_api_key),
            "openfoam_path": bool(self.openfoam_path),
            "paraview_path": bool(self.paraview_path),
            "use_docker": self.use_docker,
            "docker_container_name": bool(self.docker_container_name),
            "work_dir_exists": self.get_work_dir().exists(),
            "results_dir_exists": self.get_results_dir().exists(),
            "debug_mode": self.debug,
            "verbose_mode": self.verbose
        }


# Global settings instance
_settings: Optional[FoamAISettings] = None


def get_settings() -> FoamAISettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = FoamAISettings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (mainly for testing)."""
    global _settings
    _settings = None 
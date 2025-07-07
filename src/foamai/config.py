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
    
    # ParaView Configuration
    paraview_path: Optional[str] = Field(None, description="Path to ParaView installation")
    paraview_server_port: int = Field(11111, description="ParaView server port")
    
    # Application Configuration
    log_level: str = Field("INFO", description="Logging level")
    max_simulation_time: int = Field(3600, description="Maximum simulation time in seconds")
    work_dir: str = Field("./work", description="Working directory for simulations")
    results_dir: str = Field("./results", description="Results directory")
    
    # Development Configuration
    debug: bool = Field(False, description="Enable debug mode")
    verbose: bool = Field(False, description="Enable verbose output")
    
    def get_work_dir(self) -> Path:
        """Get the work directory as a Path object."""
        return Path(self.work_dir).resolve()
    
    def get_results_dir(self) -> Path:
        """Get the results directory as a Path object."""
        return Path(self.results_dir).resolve()
    
    def ensure_directories(self) -> None:
        """Ensure work and results directories exist."""
        self.get_work_dir().mkdir(parents=True, exist_ok=True)
        self.get_results_dir().mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = FoamAISettings()


def get_settings() -> FoamAISettings:
    """Get the global settings instance."""
    return settings 
"""
Simple configuration module for foamai-core.
Provides access to environment variables and settings.
"""
import os
from typing import Optional


class Settings:
    """Settings container for environment variables."""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.perplexity_api_key = os.getenv('PERPLEXITY_API_KEY')
        
    @property
    def openai_api_key(self) -> Optional[str]:
        return self._openai_api_key
    
    @openai_api_key.setter
    def openai_api_key(self, value: Optional[str]):
        self._openai_api_key = value


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings() 
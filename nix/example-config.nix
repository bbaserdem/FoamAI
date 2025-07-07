# Example FlowGenius Home Manager Configuration
#
# This file shows different ways to configure FlowGenius through home-manager.
# Copy the relevant sections to your home.nix or create a separate module.

{ config, lib, pkgs, ... }:

{
  # Import the FlowGenius home-manager module
  imports = [ ./hm.nix ];

  # Basic configuration - minimal setup
  programs.flowgenius = {
    enable = true;
    # Uses defaults:
    # - openaiKeyPath = "~/.openai_api_key"
    # - projectsRoot = "~/Learning" 
    # - linkStyle = "obsidian"
    # - defaultModel = "gpt-4o-mini"
  };

  # Advanced configuration - custom paths and settings
  # programs.flowgenius = {
  #   enable = true;
  #   openaiKeyPath = "${config.home.homeDirectory}/.config/secrets/openai_api_key";
  #   projectsRoot = "${config.home.homeDirectory}/Documents/LearningProjects";
  #   linkStyle = "markdown";
  #   defaultModel = "gpt-4o";
  #   createProjectsDirectory = true;
  # };

  # Development configuration - for FlowGenius development
  # programs.flowgenius = {
  #   enable = true;
  #   package = pkgs.python3Packages.buildPythonApplication {
  #     pname = "flowgenius-dev";
  #     version = "dev";
  #     src = /path/to/your/flowgenius/checkout;
  #     pyproject = true;
  #     build-system = with pkgs.python3Packages; [ hatchling ];
  #     dependencies = with pkgs.python3Packages; [
  #       openai langchain-core click platformdirs 
  #       pydantic-settings ruamel-yaml textual
  #     ];
  #   };
  #   openaiKeyPath = "${config.home.homeDirectory}/.secrets/openai-dev";
  #   projectsRoot = "${config.home.homeDirectory}/dev/flowgenius-testing";
  #   defaultModel = "gpt-4o"; # Use best model for testing
  # };

  # Security-focused configuration
  # programs.flowgenius = {
  #   enable = true;
  #   openaiKeyPath = "${config.home.homeDirectory}/.local/secrets/openai";
  #   projectsRoot = "${config.home.homeDirectory}/.local/share/flowgenius";
  #   linkStyle = "obsidian";
  #   defaultModel = "gpt-4o-mini";
  #   createProjectsDirectory = true;
  # };

  # Obsidian integration configuration  
  # programs.flowgenius = {
  #   enable = true;
  #   openaiKeyPath = "${config.home.homeDirectory}/.secrets/openai_api_key";
  #   projectsRoot = "${config.home.homeDirectory}/Obsidian/Learning";
  #   linkStyle = "obsidian"; # Perfect for Obsidian vaults
  #   defaultModel = "gpt-4o-mini";
  # };

  # Multi-user setup (e.g., for work vs personal)
  # You would typically put this in separate home-manager profiles
  # programs.flowgenius = {
  #   enable = true;
  #   openaiKeyPath = "${config.home.homeDirectory}/.config/work/openai_key";
  #   projectsRoot = "${config.home.homeDirectory}/WorkLearning";
  #   linkStyle = "markdown";
  #   defaultModel = "gpt-4o-mini";
  # };

  # Ensure the API key file has correct permissions
  home.activation.flowgeniusApiKey = lib.hm.dag.entryAfter ["writeBoundary"] ''
    if [ -f "${config.programs.flowgenius.openaiKeyPath}" ]; then
      $DRY_RUN_CMD chmod 600 "${config.programs.flowgenius.openaiKeyPath}"
    fi
  '';

  # Optional: Create the API key file template if it doesn't exist
  # (You'll still need to add your actual API key)
  home.file.".openai_api_key".text = lib.mkIf (!builtins.pathExists "${config.home.homeDirectory}/.openai_api_key") ''
    # Replace this with your actual OpenAI API key
    # Get your key from: https://platform.openai.com/api-keys
    sk-your-openai-api-key-here
  '';
} 
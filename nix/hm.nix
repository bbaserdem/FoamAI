# FlowGenius Home Manager Module
#
# This module provides declarative configuration for FlowGenius through home-manager.
# It generates the ~/.config/flowgenius/config.yaml file based on the options you set.
#
# Usage in your home.nix:
#   imports = [ /path/to/flowgenius/nix/hm.nix ];
#   programs.flowgenius = {
#     enable = true;
#     openaiKeyPath = "${config.home.homeDirectory}/.secrets/openai_api_key";
#     projectsRoot = "${config.home.homeDirectory}/Learning";
#     linkStyle = "obsidian";
#     defaultModel = "gpt-4o-mini";
#   };

{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.programs.flowgenius;
  
  configFormat = pkgs.formats.yaml { };
  
  flowgeniusConfig = {
    openai_key_path = cfg.openaiKeyPath;
    projects_root = cfg.projectsRoot;
    link_style = cfg.linkStyle;
    default_model = cfg.defaultModel;
  };
  
  configFile = configFormat.generate "config.yaml" flowgeniusConfig;

in {
  options.programs.flowgenius = {
    enable = mkEnableOption "FlowGenius AI learning assistant";

    package = mkOption {
      type = types.package;
      default = pkgs.python3Packages.buildPythonApplication {
        pname = "flowgenius";
        version = "0.5.15";
        
        src = ../.;
        
        pyproject = true;
        
        build-system = with pkgs.python3Packages; [
          hatchling
        ];
        
        dependencies = with pkgs.python3Packages; [
          openai
          langchain-core
          click
          platformdirs
          pydantic-settings
          ruamel-yaml
          textual
        ];
        
        meta = {
          description = "AI-assisted learning assistant that eliminates research paralysis";
          homepage = "https://github.com/user/flowgenius";
          license = lib.licenses.mit;
        };
      };
      description = "The FlowGenius package to use.";
    };

    openaiKeyPath = mkOption {
      type = types.str;
      default = "${config.home.homeDirectory}/.openai_api_key";
      example = "${config.home.homeDirectory}/.secrets/openai_api_key";
      description = ''
        Path to the file containing your OpenAI API key.
        
        The file should contain only the API key, starting with 'sk-'.
        Make sure this file has restricted permissions (600) for security.
      '';
    };

    projectsRoot = mkOption {
      type = types.str;
      default = "${config.home.homeDirectory}/Learning";
      example = "${config.home.homeDirectory}/Documents/FlowGenius";
      description = ''
        Root directory where FlowGenius will create learning projects.
        
        Each project gets its own subdirectory with a unique ID.
        The directory will be created automatically if it doesn't exist.
      '';
    };

    linkStyle = mkOption {
      type = types.enum [ "obsidian" "markdown" ];
      default = "obsidian";
      description = ''
        Style of links to use in generated markdown files.
        
        - "obsidian": Uses [[wiki-style]] links compatible with Obsidian
        - "markdown": Uses standard [text](link) markdown links
      '';
    };

    defaultModel = mkOption {
      type = types.str;
      default = "gpt-4o-mini";
      example = "gpt-4o";
      description = ''
        Default OpenAI model to use for content generation.
        
        Common options:
        - "gpt-4o-mini": Fast and cost-effective for most tasks
        - "gpt-4o": More capable but more expensive
        - "gpt-3.5-turbo": Older but very fast and cheap
        
        Make sure you have access to the model you specify.
      '';
    };

    createProjectsDirectory = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Whether to automatically create the projects root directory.
        
        When enabled, home-manager will ensure the directory exists
        and has the correct permissions.
      '';
    };
  };

  config = mkIf cfg.enable {
    home.packages = [ cfg.package ];

    # Generate the FlowGenius configuration file
    xdg.configFile."flowgenius/config.yaml" = {
      source = configFile;
    };

    # Optionally create the projects directory
    home.file = mkIf cfg.createProjectsDirectory {
      "${removePrefix "${config.home.homeDirectory}/" cfg.projectsRoot}/.keep" = {
        text = "# FlowGenius projects directory\n# This file ensures the directory is created\n";
      };
    };

    # Add shell completion if available
    programs.bash.initExtra = mkIf config.programs.bash.enable ''
      # FlowGenius completion
      if command -v flowgenius >/dev/null 2>&1; then
        eval "$(_FLOWGENIUS_COMPLETE=bash_source flowgenius)"
      fi
    '';

    programs.zsh.initExtra = mkIf config.programs.zsh.enable ''
      # FlowGenius completion
      if command -v flowgenius >/dev/null 2>&1; then
        eval "$(_FLOWGENIUS_COMPLETE=zsh_source flowgenius)"
      fi
    '';

    programs.fish.shellInit = mkIf config.programs.fish.enable ''
      # FlowGenius completion
      if command -v flowgenius >/dev/null 2>&1
        eval (env _FLOWGENIUS_COMPLETE=fish_source flowgenius)
      end
    '';
  };

  meta = {
    maintainers = with lib.maintainers; [ /* your-github-handle */ ];
    doc = ''
      ## FlowGenius Configuration

      FlowGenius is an AI-assisted learning assistant that helps you create
      structured learning plans from freeform goals.

      ### Basic Setup

      ```nix
      programs.flowgenius = {
        enable = true;
        openaiKeyPath = "''${config.home.homeDirectory}/.secrets/openai_api_key";
        projectsRoot = "''${config.home.homeDirectory}/Learning";
      };
      ```

      ### Security Note

      Make sure your OpenAI API key file has restricted permissions:
      ```bash
      chmod 600 ~/.secrets/openai_api_key
      ```

      ### Usage

      After enabling, run the configuration wizard:
      ```bash
      flowgenius wizard
      ```

      Or start creating learning projects directly:
      ```bash
      flowgenius new "learn Rust programming"
      ```
    '';
  };
} 
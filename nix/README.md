# FlowGenius Nix Integration

This directory contains Nix integration files for FlowGenius, allowing you to manage FlowGenius declaratively through home-manager.

## Home Manager Module

The `hm.nix` file provides a complete home-manager module for FlowGenius that:

- 📦 **Builds FlowGenius** from source using your local checkout
- ⚙️ **Generates configuration** declaratively in `~/.config/flowgenius/config.yaml`
- 📁 **Creates directories** automatically (projects root)
- 🔧 **Enables shell completion** for bash/zsh/fish
- 🏠 **Follows home-manager conventions** for consistent UX

## Quick Setup

### 1. Import the Module

Add to your `home.nix` or `flake.nix`:

```nix
{
  imports = [ /path/to/flowgenius/nix/hm.nix ];
  
  programs.flowgenius = {
    enable = true;
    openaiKeyPath = "${config.home.homeDirectory}/.secrets/openai_api_key";
    projectsRoot = "${config.home.homeDirectory}/Learning";
    linkStyle = "obsidian";
    defaultModel = "gpt-4o-mini";
  };
}
```

### 2. Set Up Your API Key

```bash
# Create secure API key file
echo "sk-your-actual-api-key-here" > ~/.secrets/openai_api_key
chmod 600 ~/.secrets/openai_api_key
```

### 3. Apply Configuration

```bash
home-manager switch
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable` | bool | `false` | Enable FlowGenius |
| `package` | package | (built from source) | FlowGenius package to use |
| `openaiKeyPath` | string | `~/.openai_api_key` | Path to OpenAI API key file |
| `projectsRoot` | string | `~/Learning` | Root directory for projects |
| `linkStyle` | enum | `"obsidian"` | Link style: "obsidian" or "markdown" |
| `defaultModel` | string | `"gpt-4o-mini"` | Default OpenAI model |
| `createProjectsDirectory` | bool | `true` | Auto-create projects directory |

## Advanced Examples

### Custom Package Source

```nix
programs.flowgenius = {
  enable = true;
  package = pkgs.python3Packages.buildPythonApplication {
    # Custom build configuration
    pname = "flowgenius";
    version = "dev";
    src = fetchFromGitHub {
      owner = "your-username";
      repo = "flowgenius";
      rev = "main";
      sha256 = "...";
    };
    # ... rest of build config
  };
};
```

### Multiple Learning Directories

```nix
programs.flowgenius = {
  enable = true;
  projectsRoot = "${config.home.homeDirectory}/Documents/Learning";
  
  # You can have multiple instances with different configs
  # by using different config file locations
};
```

### Development Setup

```nix
programs.flowgenius = {
  enable = true;
  openaiKeyPath = "${config.home.homeDirectory}/.config/secrets/openai";
  projectsRoot = "${config.home.homeDirectory}/dev/learning-projects";
  defaultModel = "gpt-4o"; # Use more capable model for development
};
```

## Features

### Automatic Dependencies

The module automatically includes all required Python dependencies:
- `openai` - OpenAI API client
- `langchain-core` - LangChain framework
- `click` - CLI framework
- `platformdirs` - Cross-platform directory paths
- `pydantic-settings` - Configuration management
- `ruamel-yaml` - YAML processing
- `textual` - TUI framework (optional)

### Shell Integration

When enabled, the module automatically sets up shell completion for:
- **Bash**: `_FLOWGENIUS_COMPLETE=bash_source`
- **Zsh**: `_FLOWGENIUS_COMPLETE=zsh_source`  
- **Fish**: `_FLOWGENIUS_COMPLETE=fish_source`

### File Management

The module handles:
- ✅ Configuration file generation at `~/.config/flowgenius/config.yaml`
- ✅ Projects directory creation (with `.keep` file)
- ✅ Proper XDG directory compliance
- ✅ Path resolution and validation

## Integration with Existing Config

If you already have a FlowGenius configuration from running `flowgenius wizard`, the home-manager module will **override** it. To migrate:

1. **Check current config**:
   ```bash
   cat ~/.config/flowgenius/config.yaml
   ```

2. **Transfer settings** to your home-manager configuration

3. **Apply home-manager**:
   ```bash
   home-manager switch
   ```

## Troubleshooting

### Permission Issues
```bash
# Fix API key permissions
chmod 600 ~/.secrets/openai_api_key

# Fix projects directory
chmod 755 ~/Learning
```

### Module Not Found
```nix
# Use absolute path
imports = [ /absolute/path/to/flowgenius/nix/hm.nix ];

# Or relative in flakes
imports = [ ./path/to/flowgenius/nix/hm.nix ];
```

### Build Failures
```bash
# Clean and rebuild
nix-collect-garbage
home-manager switch --show-trace
```

## Contributing

When modifying the home-manager module:

1. **Test changes** with a minimal configuration
2. **Update options** documentation 
3. **Verify shell completion** works across shells
4. **Check XDG compliance** for config paths
5. **Update this README** with new options

## See Also

- [Home Manager Manual](https://nix-community.github.io/home-manager/)
- [FlowGenius CLI Documentation](../README.md)
- [Nix Package Manager](https://nixos.org/manual/nix/stable/) 
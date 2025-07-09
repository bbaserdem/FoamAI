# OpenFOAM Desktop Assistant

A desktop application for simplified interaction with OpenFOAM CFD simulations through AI assistance and 3D visualization.

## Features

- **Conversational AI Interface**: Natural language interaction for simulation setup
- **Automated Mesh Generation**: AI-driven mesh generation with validation workflow
- **3D Visualization**: Embedded VTK/ParaView integration for mesh and results visualization
- **Time-step Navigation**: Navigate through simulation results with intuitive controls
- **Cross-platform Support**: Works on Windows, macOS, and Linux

## Architecture

The application follows a client-server architecture:

- **Client (Desktop App)**: PySide6-based GUI with chat interface and ParaView visualization
- **Server**: OpenFOAM server with REST API and ParaView server (pvserver)
- **Communication**: REST API for simulation management, ParaView server for visualization

## Requirements

### System Requirements
- Python 3.7 or higher
- OpenFOAM server with REST API
- ParaView server (pvserver)
- Minimum 4GB RAM recommended
- Graphics card with OpenGL support

### Python Dependencies
- PySide6 >= 6.5.0
- requests >= 2.31.0
- paraview >= 5.11.0
- vtk >= 9.2.0
- numpy >= 1.24.0
- python-dotenv >= 1.0.0

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd foamtest
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application:**
   Create a `.env` file in the project root with the following settings:
   ```env
   # Server Configuration
   SERVER_HOST=localhost
   SERVER_PORT=8000
   
   # ParaView Server Configuration
   PARAVIEW_SERVER_HOST=localhost
   PARAVIEW_SERVER_PORT=11111
   
   # Application Settings
   WINDOW_WIDTH=1200
   WINDOW_HEIGHT=800
   
   # Chat Interface Settings
   CHAT_HISTORY_LIMIT=100
   
   # ParaView Settings
   PARAVIEW_TIMEOUT=30
   
   # Request Timeout (seconds)
   REQUEST_TIMEOUT=60
   ```

4. **Verify server connections:**
   - Ensure OpenFOAM server is running on the specified host/port
   - Ensure ParaView server (pvserver) is running on the specified host/port

## Usage

### Quick Start - Test the Complete Workflow

**🚀 EASIEST: Start Everything at Once**
```bash
# Install dependencies (including Flask for the test server)
pip install -r requirements.txt

# Start ALL servers and the desktop app automatically
python start_all_servers.py
```

This will start the OpenFOAM test server, ParaView server, and desktop application in the correct order!

**Alternative: Manual Startup**
```bash
# Test just the workflow (server + client, no ParaView)
python test_workflow.py
```

### Starting Components Separately

**Option 1: Manual three-step startup**
```bash
# Terminal 1 - Start test server
python start_server.py

# Terminal 2 - Start ParaView server
python start_paraview_server.py

# Terminal 3 - Start desktop application  
python main.py
```

**Option 2: Use the quick start script**
```bash
python run.py
```

### User Workflow

1. **Scenario Input**: Describe your simulation scenario in natural language
   - Example: "I want to see effects of 10 mph wind on a cube sitting on the ground"

2. **Mesh Generation**: The AI generates a mesh based on your description
   - The mesh is automatically displayed in the 3D visualization area

3. **Mesh Validation**: Review the generated mesh
   - Click "✓ Yes, mesh looks correct" to approve
   - Click "✗ No, needs adjustment" to provide feedback for regeneration

4. **Simulation Execution**: Once approved, the simulation runs automatically
   - Progress is shown in the chat interface

5. **Results Visualization**: View and interact with simulation results
   - Use visualization controls to display different fields (pressure, velocity, streamlines)
   - Navigate through time steps using the time controls

### Example Scenarios

- **External Aerodynamics**: "Simulate airflow around a cylinder at 5 m/s"
- **Wind Engineering**: "Model wind effects on a building at 15 mph"
- **Heat Transfer**: "Analyze heat transfer in a pipe with 80°C inlet temperature"
- **Fluid Dynamics**: "Study flow separation around a sphere at Reynolds number 1000"

### Interface Components

#### Chat Interface
- **Message Input**: Type your scenarios and feedback
- **Chat History**: View conversation with AI assistant
- **Validation Buttons**: Approve or reject generated meshes
- **Status Indicator**: Shows current operation status

#### 3D Visualization Area
- **Mesh Display**: View generated meshes in 3D
- **Results Visualization**: Display simulation results with different field variables
- **Interactive Controls**: Rotate, zoom, and pan the 3D view
- **Field Buttons**: Switch between pressure, velocity, and streamlines
- **Time Navigation**: Move through simulation time steps

#### Menu System
- **File Menu**: New session, settings, exit
- **Connection Menu**: Test connections, connect/disconnect ParaView
- **Help Menu**: User guide, about dialog

## Configuration

### Server Settings
Modify the following in your `.env` file:

```env
# OpenFOAM REST API server
SERVER_HOST=your-server-host
SERVER_PORT=your-server-port

# ParaView server for visualization
PARAVIEW_SERVER_HOST=your-paraview-host
PARAVIEW_SERVER_PORT=your-paraview-port
```

### Application Settings
Customize the application behavior:

```env
# Window dimensions
WINDOW_WIDTH=1400
WINDOW_HEIGHT=900

# Chat history limit
CHAT_HISTORY_LIMIT=200

# Connection timeout
REQUEST_TIMEOUT=120
```

## Troubleshooting

### Common Issues

1. **Server Connection Failed**
   - Verify OpenFOAM server is running
   - Check host/port configuration in `.env`
   - Test network connectivity

2. **ParaView Connection Failed**
   - Ensure pvserver is running with correct port
   - Check firewall settings
   - Verify ParaView installation

3. **Visualization Not Loading**
   - Check ParaView server logs
   - Verify OpenFOAM file paths are accessible
   - Ensure sufficient system resources

4. **Dependencies Missing**
   - Run `pip install -r requirements.txt`
   - Check Python version compatibility
   - Verify ParaView Python library installation

### Log Files

Application logs are stored in the `logs/` directory:
- `openfoam_app.log`: Main application log
- Check logs for detailed error information

### Performance Tips

1. **Large Meshes**: 
   - Use server-side rendering for meshes >10M cells
   - Adjust visualization quality settings

2. **Network Latency**:
   - Increase timeout values in configuration
   - Use local servers when possible

3. **Memory Usage**:
   - Limit chat history for long sessions
   - Close unused visualization sessions

## Test Server

For testing and development, a complete test server is included that simulates the OpenFOAM workflow using real data from your `testdata/` directory.

### Test Server Features
- ✅ Implements all required API endpoints
- ✅ Uses real OpenFOAM data (pressure, velocity, turbulence fields)
- ✅ Simulates realistic timing (2s mesh generation, 3s simulation)
- ✅ Supports the complete workflow: scenario → mesh → validation → simulation → results
- ✅ Provides debugging endpoints for task monitoring

### Test Server Endpoints
- `GET /` - Health check and server info
- `POST /submit_scenario` - Submit simulation scenario
- `GET /status/<task_id>` - Get task status  
- `POST /approve_mesh` - Approve generated mesh
- `POST /reject_mesh` - Reject mesh with feedback
- `POST /run_simulation` - Start simulation execution
- `GET /results/<task_id>` - Get simulation results
- `GET /download/<filename>` - Download OpenFOAM files
- `GET /list_tasks` - List all tasks (debug)
- `POST /clear_tasks` - Clear all tasks (debug)

### Using Your Own OpenFOAM Data
Place your OpenFOAM case in the `testdata/` directory with:
```
testdata/
├── pitzDailySteady.OpenFOAM    # Main case file for ParaView
├── constant/                   # Mesh and properties
│   └── polyMesh/              # Mesh files
├── system/                     # Solver settings
├── 0/                         # Initial conditions
├── 100/, 200/, etc.           # Time step results
│   ├── p                      # Pressure field
│   ├── U                      # Velocity field
│   └── k, epsilon, nut, etc.  # Other fields
└── postProcessing/            # Post-processing data
```

## API Endpoints

The application expects the following REST API endpoints on the OpenFOAM server:

- `POST /submit_scenario`: Submit simulation scenario
- `POST /approve_mesh`: Approve generated mesh  
- `POST /reject_mesh`: Reject mesh with feedback
- `POST /run_simulation`: Start simulation execution
- `GET /results/{task_id}`: Get simulation results
- `GET /status/{task_id}`: Get task status

## Development

### Project Structure
```
foamtest/
├── main.py                 # Application entry point
├── main_window.py          # Main window class
├── chat_interface.py       # Chat interface widget
├── paraview_widget.py      # ParaView visualization widget
├── api_client.py           # REST API client
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── logs/                  # Application logs
```

### Adding New Features

1. **New Visualization Options**: Extend `paraview_widget.py`
2. **Additional API Endpoints**: Modify `api_client.py`
3. **UI Enhancements**: Update `main_window.py` and component files
4. **Configuration Options**: Add to `config.py`

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files for error details
3. Verify server configurations
4. Consult ParaView and OpenFOAM documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenFOAM for CFD simulation capabilities
- ParaView for 3D visualization
- PySide6 for GUI framework 
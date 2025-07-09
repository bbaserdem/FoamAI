"""STL Processor - Handles STL file parsing and geometry analysis."""

import struct
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger


class STLProcessor:
    """Processes STL files and extracts geometry information."""
    
    def __init__(self, stl_file_path: str):
        """Initialize STL processor with file path."""
        self.stl_file_path = Path(stl_file_path)
        self.vertices = None
        self.normals = None
        self.triangles = None
        self.is_loaded = False
        
    def load_stl(self) -> bool:
        """Load STL file (handles both ASCII and binary formats)."""
        try:
            if self._is_binary_stl():
                return self._load_binary_stl()
            else:
                return self._load_ascii_stl()
        except Exception as e:
            logger.error(f"Failed to load STL file {self.stl_file_path}: {e}")
            return False
    
    def _is_binary_stl(self) -> bool:
        """Check if STL file is binary format."""
        try:
            with open(self.stl_file_path, 'rb') as f:
                header = f.read(80)
                # Check if header contains 'solid' (ASCII indicator)
                if header.startswith(b'solid '):
                    # Could still be binary, check for valid ASCII content
                    f.seek(0)
                    try:
                        content = f.read(1024).decode('ascii')
                        return 'facet normal' not in content
                    except UnicodeDecodeError:
                        return True
                return True
        except Exception:
            return False
    
    def _load_binary_stl(self) -> bool:
        """Load binary STL file."""
        try:
            with open(self.stl_file_path, 'rb') as f:
                # Skip 80-byte header
                f.read(80)
                
                # Read number of triangles
                num_triangles = struct.unpack('<I', f.read(4))[0]
                
                vertices = []
                normals = []
                
                for _ in range(num_triangles):
                    # Read normal vector (3 floats)
                    normal = struct.unpack('<3f', f.read(12))
                    normals.append(normal)
                    
                    # Read 3 vertices (9 floats)
                    v1 = struct.unpack('<3f', f.read(12))
                    v2 = struct.unpack('<3f', f.read(12))
                    v3 = struct.unpack('<3f', f.read(12))
                    
                    vertices.extend([v1, v2, v3])
                    
                    # Skip attribute byte count
                    f.read(2)
                
                self.vertices = np.array(vertices)
                self.normals = np.array(normals)
                self.triangles = np.arange(len(vertices)).reshape(-1, 3)
                self.is_loaded = True
                
                logger.info(f"Loaded binary STL with {num_triangles} triangles")
                return True
                
        except Exception as e:
            logger.error(f"Error loading binary STL: {e}")
            return False
    
    def _load_ascii_stl(self) -> bool:
        """Load ASCII STL file."""
        try:
            with open(self.stl_file_path, 'r') as f:
                lines = f.readlines()
            
            vertices = []
            normals = []
            current_normal = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('facet normal'):
                    # Extract normal vector
                    parts = line.split()
                    current_normal = [float(parts[2]), float(parts[3]), float(parts[4])]
                
                elif line.startswith('vertex'):
                    # Extract vertex coordinates
                    parts = line.split()
                    vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
                    vertices.append(vertex)
                
                elif line.startswith('endfacet'):
                    # End of facet, add normal for this triangle
                    if current_normal:
                        normals.append(current_normal)
            
            self.vertices = np.array(vertices)
            self.normals = np.array(normals)
            self.triangles = np.arange(len(vertices)).reshape(-1, 3)
            self.is_loaded = True
            
            logger.info(f"Loaded ASCII STL with {len(normals)} triangles")
            return True
            
        except Exception as e:
            logger.error(f"Error loading ASCII STL: {e}")
            return False
    
    def analyze_geometry(self) -> Dict[str, Any]:
        """Analyze STL geometry and extract key properties."""
        if not self.is_loaded:
            if not self.load_stl():
                return {}
        
        try:
            # Calculate bounding box
            min_coords = np.min(self.vertices, axis=0)
            max_coords = np.max(self.vertices, axis=0)
            dimensions = max_coords - min_coords
            
            # Calculate characteristic length (largest dimension)
            characteristic_length = np.max(dimensions)
            
            # Calculate approximate surface area
            surface_area = self._calculate_surface_area()
            
            # Calculate approximate volume (if mesh is watertight)
            volume = self._calculate_volume()
            
            # Detect surfaces for boundary conditions
            surfaces = self._classify_surfaces()
            
            geometry_info = {
                "file_path": str(self.stl_file_path),
                "num_triangles": len(self.normals),
                "num_vertices": len(self.vertices),
                "bounding_box": {
                    "min": min_coords.tolist(),
                    "max": max_coords.tolist(),
                    "dimensions": dimensions.tolist()
                },
                "characteristic_length": float(characteristic_length),
                "surface_area": float(surface_area),
                "volume": float(volume) if volume > 0 else None,
                "surfaces": surfaces,
                "is_watertight": self._check_watertight(),
                "mesh_recommendations": self._generate_mesh_recommendations(characteristic_length)
            }
            
            return geometry_info
            
        except Exception as e:
            logger.error(f"Error analyzing STL geometry: {e}")
            return {}
    
    def _calculate_surface_area(self) -> float:
        """Calculate total surface area of the STL mesh."""
        total_area = 0.0
        
        for i in range(0, len(self.vertices), 3):
            if i + 2 < len(self.vertices):
                v1 = self.vertices[i]
                v2 = self.vertices[i + 1]
                v3 = self.vertices[i + 2]
                
                # Calculate triangle area using cross product
                edge1 = v2 - v1
                edge2 = v3 - v1
                cross = np.cross(edge1, edge2)
                area = 0.5 * np.linalg.norm(cross)
                total_area += area
        
        return total_area
    
    def _calculate_volume(self) -> float:
        """Calculate volume using divergence theorem (works for watertight meshes)."""
        volume = 0.0
        
        try:
            for i in range(0, len(self.vertices), 3):
                if i + 2 < len(self.vertices):
                    v1 = self.vertices[i]
                    v2 = self.vertices[i + 1]
                    v3 = self.vertices[i + 2]
                    
                    # Calculate signed volume of tetrahedron formed with origin
                    volume += np.dot(v1, np.cross(v2, v3)) / 6.0
            
            return abs(volume)
            
        except Exception:
            return 0.0
    
    def _classify_surfaces(self) -> List[Dict[str, Any]]:
        """Classify surfaces based on normal directions for boundary conditions."""
        surfaces = []
        
        # Group triangles by normal direction
        normal_groups = {}
        tolerance = 0.1  # Tolerance for grouping normals
        
        for i, normal in enumerate(self.normals):
            # Normalize normal
            normal = normal / (np.linalg.norm(normal) + 1e-10)
            
            # Find existing group or create new one
            group_found = False
            for key, group in normal_groups.items():
                if np.linalg.norm(normal - np.array(key)) < tolerance:
                    group.append(i)
                    group_found = True
                    break
            
            if not group_found:
                normal_groups[tuple(normal)] = [i]
        
        # Create surface definitions for major groups
        for normal_vec, triangle_indices in normal_groups.items():
            if len(triangle_indices) > len(self.normals) * 0.05:  # At least 5% of triangles
                normal_array = np.array(normal_vec)
                
                # Classify surface type based on normal direction
                surface_type = self._classify_surface_type(normal_array)
                
                # Calculate surface area for this group
                area = len(triangle_indices) * (self._calculate_surface_area() / len(self.normals))
                
                surfaces.append({
                    "name": surface_type,
                    "normal": normal_vec,
                    "triangle_count": len(triangle_indices),
                    "area": area,
                    "recommended_bc": self._recommend_boundary_condition(surface_type, normal_array)
                })
        
        return surfaces
    
    def _classify_surface_type(self, normal: np.ndarray) -> str:
        """Classify surface type based on normal direction."""
        # Determine dominant direction
        abs_normal = np.abs(normal)
        dominant_axis = np.argmax(abs_normal)
        
        if dominant_axis == 0:  # X-direction
            if normal[0] > 0:
                return "outlet_surface"
            else:
                return "inlet_surface"
        elif dominant_axis == 1:  # Y-direction
            return "side_surface"
        else:  # Z-direction
            if normal[2] > 0:
                return "top_surface"
            else:
                return "bottom_surface"
    
    def _recommend_boundary_condition(self, surface_type: str, normal: np.ndarray) -> Dict[str, str]:
        """Recommend boundary conditions based on surface type."""
        if surface_type == "inlet_surface":
            return {
                "U": "fixedValue",
                "p": "zeroGradient",
                "description": "Velocity inlet"
            }
        elif surface_type == "outlet_surface":
            return {
                "U": "zeroGradient", 
                "p": "fixedValue",
                "description": "Pressure outlet"
            }
        else:
            return {
                "U": "noSlip",
                "p": "zeroGradient", 
                "description": "Wall"
            }
    
    def _check_watertight(self) -> bool:
        """Check if the mesh is watertight (simplified check)."""
        # This is a simplified check - a full implementation would check edge connectivity
        return len(self.vertices) % 3 == 0 and len(self.normals) > 0
    
    def _generate_mesh_recommendations(self, characteristic_length: float) -> Dict[str, Any]:
        """Generate mesh size recommendations based on geometry."""
        # Base cell size should be a fraction of characteristic length
        base_cell_size = characteristic_length / 20  # Start with 20 cells across
        
        return {
            "base_cell_size": base_cell_size,
            "surface_refinement_levels": {
                "min": 2,
                "max": 4
            },
            "layer_settings": {
                "n_layers": 3,
                "thickness_ratio": 0.1,
                "expansion_ratio": 1.3
            },
            "domain_size_multiplier": 10,  # Domain should be 10x larger than object
            "estimated_cells": self._estimate_cell_count(base_cell_size)
        }
    
    def _estimate_cell_count(self, cell_size: float) -> int:
        """Estimate total cell count for mesh."""
        if not self.is_loaded:
            return 0
        
        # Calculate domain volume
        min_coords = np.min(self.vertices, axis=0)
        max_coords = np.max(self.vertices, axis=0)
        dimensions = max_coords - min_coords
        
        # Expand domain
        domain_dimensions = dimensions * 10
        domain_volume = np.prod(domain_dimensions)
        
        # Estimate cells
        cells_per_direction = domain_dimensions / cell_size
        estimated_cells = int(np.prod(cells_per_direction))
        
        return min(estimated_cells, 1000000)  # Cap at 1M cells for initial estimate


def process_stl_file(stl_file_path: str) -> Dict[str, Any]:
    """Process STL file and return geometry information."""
    processor = STLProcessor(stl_file_path)
    return processor.analyze_geometry()


def validate_stl_file(stl_file_path: str) -> Tuple[bool, List[str]]:
    """Validate STL file and return success status with any warnings."""
    warnings = []
    
    try:
        stl_path = Path(stl_file_path)
        
        # Check file exists
        if not stl_path.exists():
            return False, ["STL file does not exist"]
        
        # Check file size
        file_size = stl_path.stat().st_size
        if file_size == 0:
            return False, ["STL file is empty"]
        
        if file_size > 100 * 1024 * 1024:  # 100MB limit
            warnings.append("STL file is very large (>100MB) - processing may be slow")
        
        # Try to load and validate
        processor = STLProcessor(stl_file_path)
        if not processor.load_stl():
            return False, ["Failed to load STL file - may be corrupted"]
        
        # Check for reasonable geometry
        if len(processor.vertices) < 3:
            return False, ["STL file contains too few vertices"]
        
        if len(processor.normals) < 1:
            return False, ["STL file contains no valid triangles"]
        
        # Generate warnings for problematic geometry
        geometry_info = processor.analyze_geometry()
        
        if not geometry_info.get("is_watertight", False):
            warnings.append("STL mesh may not be watertight - this could affect volume calculations")
        
        char_length = geometry_info.get("characteristic_length", 0)
        if char_length > 100:
            warnings.append("Geometry is very large - consider scaling down for better mesh generation")
        elif char_length < 0.001:
            warnings.append("Geometry is very small - consider scaling up for better mesh generation")
        
        return True, warnings
        
    except Exception as e:
        return False, [f"Error validating STL file: {str(e)}"] 
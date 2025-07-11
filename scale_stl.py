#!/usr/bin/env python3
"""
Scale STL file by a given factor.
Usage: python scale_stl.py input.stl output.stl scale_factor
"""

import struct
import sys
import numpy as np
from pathlib import Path


def scale_binary_stl(input_file: str, output_file: str, scale_factor: float):
    """Scale a binary STL file by the given factor."""
    
    print(f"Scaling {input_file} by factor {scale_factor}...")
    
    with open(input_file, 'rb') as f_in:
        # Read header
        header = f_in.read(80)
        print(f"Header: {header[:20]}...")
        
        # Read number of triangles
        num_triangles_data = f_in.read(4)
        num_triangles = struct.unpack('<I', num_triangles_data)[0]
        print(f"Number of triangles: {num_triangles}")
        
        # Read all triangle data
        triangles = []
        for i in range(num_triangles):
            triangle_data = f_in.read(50)
            if len(triangle_data) != 50:
                print(f"Warning: incomplete triangle data at triangle {i}")
                break
                
            # Unpack triangle data (normal + 3 vertices + attribute)
            data = struct.unpack('<12fH', triangle_data)
            
            # Scale vertices but keep normal unchanged
            normal = data[0:3]  # Normal vector (don't scale)
            
            # Scale the 3 vertices
            v1 = [data[3] * scale_factor, data[4] * scale_factor, data[5] * scale_factor]
            v2 = [data[6] * scale_factor, data[7] * scale_factor, data[8] * scale_factor]
            v3 = [data[9] * scale_factor, data[10] * scale_factor, data[11] * scale_factor]
            
            attribute = data[12]  # Attribute bytes
            
            triangles.append((normal, v1, v2, v3, attribute))
            
            if (i + 1) % 5000 == 0:
                print(f"Processed {i + 1}/{num_triangles} triangles...")
    
    # Write scaled STL
    print(f"Writing scaled STL to {output_file}...")
    with open(output_file, 'wb') as f_out:
        # Write header (modify to indicate scaling)
        scaled_header = f"Scaled STL (factor {scale_factor})".ljust(80)[:80].encode('ascii')
        f_out.write(scaled_header)
        
        # Write number of triangles
        f_out.write(struct.pack('<I', len(triangles)))
        
        # Write scaled triangles
        for normal, v1, v2, v3, attribute in triangles:
            # Pack triangle data
            triangle_data = struct.pack('<12fH', 
                                      normal[0], normal[1], normal[2],  # Normal (unchanged)
                                      v1[0], v1[1], v1[2],              # Vertex 1 (scaled)
                                      v2[0], v2[1], v2[2],              # Vertex 2 (scaled)
                                      v3[0], v3[1], v3[2],              # Vertex 3 (scaled)
                                      attribute)                         # Attribute
            f_out.write(triangle_data)
    
    print(f"Successfully scaled STL file!")
    print(f"Original size: ~{5697.509:.1f} m")
    print(f"New size: ~{5697.509 * scale_factor:.1f} m")


def get_stl_bounds(stl_file: str):
    """Get the bounding box of an STL file for verification."""
    vertices = []
    
    with open(stl_file, 'rb') as f:
        # Skip header
        f.read(80)
        
        # Read number of triangles
        num_triangles = struct.unpack('<I', f.read(4))[0]
        
        for i in range(min(num_triangles, 1000)):  # Sample first 1000 triangles
            triangle_data = f.read(50)
            if len(triangle_data) != 50:
                break
                
            data = struct.unpack('<12fH', triangle_data)
            
            # Extract vertices
            v1 = [data[3], data[4], data[5]]
            v2 = [data[6], data[7], data[8]]
            v3 = [data[9], data[10], data[11]]
            
            vertices.extend([v1, v2, v3])
    
    if vertices:
        vertices = np.array(vertices)
        min_coords = vertices.min(axis=0)
        max_coords = vertices.max(axis=0)
        dimensions = max_coords - min_coords
        
        print(f"Bounding box: {min_coords} to {max_coords}")
        print(f"Dimensions: {dimensions}")
        print(f"Characteristic length: {np.max(dimensions):.3f}")
    else:
        print("No vertices found")


if __name__ == "__main__":
    # Scale F1.stl from ~5.7km to ~5.7m
    input_file = "stl/F1.stl"
    output_file = "stl/F1_scaled.stl"
    scale_factor = 0.001  # Scale down by 1000x
    
    print("=" * 60)
    print("STL SCALING TOOL")
    print("=" * 60)
    
    # Check if input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file {input_file} not found!")
        sys.exit(1)
    
    # Get original bounds
    print(f"\nOriginal STL bounds:")
    get_stl_bounds(input_file)
    
    # Scale the STL
    print(f"\nScaling STL...")
    scale_binary_stl(input_file, output_file, scale_factor)
    
    # Verify scaled bounds
    print(f"\nScaled STL bounds:")
    get_stl_bounds(output_file)
    
    print(f"\n✅ Done! Scaled STL saved as: {output_file}")
    print(f"Now you can use: --stl-file {output_file}") 
import struct
import sys

def read_binary_stl(filename):
    """Read binary STL file and return triangles"""
    with open(filename, 'rb') as f:
        # Skip the 80-byte header
        header = f.read(80)
        
        # Read the number of triangles
        num_triangles = struct.unpack('<I', f.read(4))[0]
        
        triangles = []
        for i in range(num_triangles):
            # Read normal vector (3 floats)
            normal = struct.unpack('<3f', f.read(12))
            
            # Read 3 vertices (9 floats total)
            vertex1 = struct.unpack('<3f', f.read(12))
            vertex2 = struct.unpack('<3f', f.read(12))
            vertex3 = struct.unpack('<3f', f.read(12))
            
            # Skip the 2-byte attribute count
            f.read(2)
            
            triangles.append((normal, vertex1, vertex2, vertex3))
        
        return triangles

def write_ascii_stl(filename, triangles, solid_name="object"):
    """Write ASCII STL file"""
    with open(filename, 'w') as f:
        f.write(f"solid {solid_name}\n")
        
        for normal, v1, v2, v3 in triangles:
            f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n")
            f.write(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n")
            f.write(f"      vertex {v3[0]:.6e} {v3[1]:.6e} {v3[2]:.6e}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        
        f.write(f"endsolid {solid_name}\n")

def is_binary_stl(filename):
    """Check if STL file is binary format"""
    with open(filename, 'rb') as f:
        # Read first 80 bytes
        header = f.read(80)
        
        # Try to read triangle count
        try:
            num_triangles = struct.unpack('<I', f.read(4))[0]
            # Calculate expected file size for binary STL
            expected_size = 80 + 4 + (num_triangles * 50)  # header + count + triangles
            
            # Get actual file size
            f.seek(0, 2)  # Go to end
            actual_size = f.tell()
            
            # If sizes match, it's likely binary
            return actual_size == expected_size
        except:
            return False

def convert_stl_to_ascii(input_file, output_file):
    """Convert STL file to ASCII format"""
    if is_binary_stl(input_file):
        print(f"Converting binary STL {input_file} to ASCII format...")
        triangles = read_binary_stl(input_file)
        write_ascii_stl(output_file, triangles, "DeLorean")
        print(f"Converted to ASCII STL: {output_file}")
    else:
        print(f"File {input_file} is already in ASCII format")
        # Just copy the file
        with open(input_file, 'r') as src, open(output_file, 'w') as dst:
            dst.write(src.read())

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_stl.py <input_stl> <output_stl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    convert_stl_to_ascii(input_file, output_file) 
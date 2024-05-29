from pxr import Gf
import re, os
import numpy as np

###################################
# Current bugs
# Specular color is lost by Blender, so stored in a json
# file - needs to be manually editted

# Only set up for Blender, Principled BSDF

# Uncertain about normals and UVs - it produces a lot more


from collections import namedtuple
from pxr import Usd, UsdGeom, UsdShade
import json

Material = namedtuple('Material', ['name', 'face_color', 'power', 'specular_color', 'emissive_color', 'texture_filename'])

class USDToXConverter:
    def __init__(self, usd_file):
        self.stage = Usd.Stage.Open(usd_file)
        self.materials = []
        self.frames = []

    def convert(self, output_x_file):
        self.extract_materials()
        self.extract_frames()

        # Load specular colors
        specular_colors = self.load_specular_colors_from_json(output_x_file.removesuffix('.x')+'_speculars.json')
        updated_materials = []
        for material in self.materials:
            if material.name in specular_colors:
                specular_color = tuple(specular_colors[material.name])
            else:
                specular_color = material.specular_color
            # Create a new Material instance with the updated specular color
            updated_material = Material(
                name=material.name,
                face_color=material.face_color,
                power=material.power,
                specular_color=specular_color,
                emissive_color=material.emissive_color,
                texture_filename=material.texture_filename
            )
            updated_materials.append(updated_material)
        self.materials = updated_materials
        
        self.write_x_file(output_x_file)
        print(".x file created.")

    def load_specular_colors_from_json(self, json_file):
        if not os.path.exists(json_file):
            print(f"Specular colors file '{json_file}' not found. Using default values.")
            return {}
        
        try:
            with open(json_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading specular colors file '{json_file}': {e}. Using default values.")
            return {}

    def extract_material_root(self):
        material_paths = ['/Materials', '/root/_materials']
        for path in material_paths:
            material_root = self.stage.GetPrimAtPath(path)
            if material_root.IsValid():
                return material_root
        return None

    def extract_materials(self):
        material_root = self.extract_material_root()

        for material_prim in material_root.GetChildren():
            shader = UsdShade.Shader.Get(self.stage, f'{material_prim.GetPath()}/Principled_BSDF')
            
            if shader:
                specular = (0,0,0) #Updated by external JSON file
                emissive = shader.GetInput('emissiveColor').Get()
                roughness = shader.GetInput('roughness').Get()
                
                texture_filename = None
                if shader.GetInput('diffuseColor').GetConnectedSource():
                    usd_texture = UsdShade.Shader.Get(self.stage, shader.GetInput('diffuseColor').GetConnectedSource()[0].GetPath().pathString)
                    texture_filename = str(usd_texture.GetInput('file').Get()).replace('@','')
                    diffuse = (1,1,1,1)
                else:
                    diffuse = shader.GetInput('diffuseColor').Get()

                face_color = tuple(diffuse)
                specular_color = tuple(specular)
                emissive_color = tuple(emissive)
                power = 1.0 / roughness if roughness else 0.0

                material = Material(material_prim.GetName(), face_color, power, specular_color, emissive_color, texture_filename)
                self.materials.append(material)

    def extract_frames(self):
        root = self.stage.GetPseudoRoot()
        for child in root.GetChildren():
            self.parse_frame(child)

        #remove excess root from Blender
        if self.frames[0]['name'] == 'root':
            self.frames = self.frames[0]['frames']

    def parse_frame(self, prim, parent=None):
        frame_data = {'name': prim.GetName(), 'transform_matrix': None, 'meshes': [], 'frames': []}
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            transform_attr = xformable.GetLocalTransformation()
            if transform_attr:
                matrix = transform_attr
                frame_data['transform_matrix'] = matrix

        if prim.GetTypeName() == 'Xform':
            for child in prim.GetChildren():
                self.parse_frame(child, frame_data)
            
            if parent:
                parent['frames'].append(frame_data)
            else:
                self.frames.append(frame_data)
        elif prim.GetTypeName() == 'Mesh':
            mesh = self.extract_mesh(prim)
            #add the mesh to the parent
            parent['meshes'].append(mesh)

    def extract_mesh(self, prim):
        mesh_data = {'name': prim.GetName(), 'vertices': [], 'normals': [], 'normal_faces': [], 'uvs': [], 'colors': [], 'faces': [], 'materials': {'material_indices': [], 'materials': []}}
        usd_mesh = UsdGeom.Mesh(prim)

        if mesh_data['name'].endswith('_001'):
            mesh_data['name'] = mesh_data['name'].removesuffix('_001')
        
        transform_matrix = np.array([
            [ 1.0,  0.0,  0.0,  0.0],
            [ 0.0,  -1.0,  0.0,  0.0],
            [ 0.0,  0.0,  1.0,  0.0],
            [ 0.0,  0.0,  0.0,  1.0]
        ])

        # Extract vertices
        #base_vertices = [tuple(np.dot(transform_matrix, np.append(point, 1.0))[:3]) for point in usd_mesh.GetPointsAttr().Get()]
        base_vertices = usd_mesh.GetPointsAttr().Get()
        
        mesh_data['vertices'] = base_vertices

        # Extract normals and apply transformation
        base_normals = [tuple(np.dot(transform_matrix[:3, :3], normal)) for normal in usd_mesh.GetNormalsAttr().Get()]

        # Extract faces
        face_vertex_indices = usd_mesh.GetFaceVertexIndicesAttr().Get()
        if face_vertex_indices:
            faces = [face_vertex_indices[i:i+3] for i in range(0, len(face_vertex_indices), 3)]
            for face in faces:
                if len(face) != 3:
                    print(f"Error: Non-triangulated face or edge found in mesh {mesh_data['name']}.")
                    exit(1)
            mesh_data['faces'] = faces
        else:
            print(f"Warning: No face vertex indices found for mesh {mesh_data['name']}")

        # Extract UVs and remap vertices, normals, and colors
        primvar_api = UsdGeom.PrimvarsAPI(usd_mesh)
        if primvar_api.HasPrimvar("st"):
            uvs = primvar_api.GetPrimvar("st").Get()
            uv_indices = usd_mesh.GetFaceVertexIndicesAttr().Get()

            new_vertices = []
            new_normals = []
            new_uvs = []
            new_colors = []
            vertex_map = {}
            new_normal_faces = []

            if primvar_api.HasPrimvar("displayColor"):
                colors = primvar_api.GetPrimvar("displayColor").Get()
            else:
                colors = [(1.0, 1.0, 1.0)] * len(base_vertices)

            for face_index, face in enumerate(mesh_data['faces']):
                new_normal_face = []
                for i in range(3):
                    vertex_index = face[i]
                    uv_index = face_index * 3 + i  # Adjust index mapping here
                    vertex = base_vertices[vertex_index]
                    normal = base_normals[uv_index]
                    uv = uvs[uv_index]
                    color = colors[vertex_index]

                    key = (vertex, uv, color)
                    if key in vertex_map:
                        new_vertex_index = vertex_map[key]
                    else:
                        new_vertex_index = len(new_vertices)
                        vertex_map[key] = new_vertex_index
                        new_vertices.append(vertex)
                        new_normals.append(normal)
                        new_uvs.append(uv)
                        new_colors.append(color)

                    face[i] = new_vertex_index
                    new_normal_face.append(new_vertex_index)
                new_normal_faces.append(new_normal_face)

            mesh_data['vertices'] = new_vertices
            mesh_data['normals'] = [(norm[0], norm[1], norm[2]) for norm in new_normals]  # Ensure normals are in the correct order
            mesh_data['uvs'] = [(uv[0], 1.0 - uv[1]) for uv in new_uvs]  # Correctly flip the V coordinate
            mesh_data['colors'] = new_colors
            mesh_data['normal_faces'] = new_normal_faces

        # Extract material groups using GeomSubset
        material_binding = UsdShade.MaterialBindingAPI(usd_mesh)
        binding_rel = material_binding.GetDirectBindingRel()
        targets = binding_rel.GetTargets()
        subsets = UsdGeom.Subset.GetAllGeomSubsets(usd_mesh)
        if len(subsets) == 0:
            if targets:
                mesh_data['materials']['materials'].append(str(targets[0]).split("/")[-1])
        else:
            face_to_material = [0] * len(mesh_data['faces'])
            for material_index, subset in enumerate(subsets):
                indices = subset.GetIndicesAttr().Get()
                if indices:
                    for index in indices:
                        face_to_material[index] = material_index
                    binding_rel = subset.GetPrim().GetRelationship('material:binding')
                    targets = binding_rel.GetTargets()
                    if targets:
                        mesh_data['materials']['materials'].append(str(targets[0]).split('/')[-1])
            mesh_data['materials']['material_indices'] = face_to_material

        return mesh_data

    def write_x_file(self, output_x_file):
        with open(output_x_file, 'w', encoding='shift_jis') as file:
            file.write("xof 0303txt 0032\n")
            file.write("""
Header {
	1; 0; 1;
}

""")
            self.write_materials(file)

            # Get the X File heirachy
            json_hierarchy = None
            if(os.path.exists(output_x_file.removesuffix('.x')+'_frames.json')):
                with open(output_x_file.removesuffix('.x')+'_frames.json', 'r') as f:
                    d = json.load(f)
                    json_hierarchy = decode_json_to_frames(d)
            else:
                print("Error: missing - "+output_x_file.removesuffix('.x')+'_frames.json')
                exit()

            self.write_frames(file, json_hierarchy, self.frames)

    def write_materials(self, file):
        for material in self.materials:
            file.write("Material "+material.name+" {\n")
            file.write(f"\t{material.face_color[0]:.6f};{material.face_color[1]:.6f};{material.face_color[2]:.6f};1.0;;\n")
            file.write(f"\t{material.power:.6f};\n")
            file.write(f"\t{material.specular_color[0]:.6f};{material.specular_color[1]:.6f};{material.specular_color[2]:.6f};;\n")
            file.write(f"\t{material.emissive_color[0]:.6f};{material.emissive_color[1]:.6f};{material.emissive_color[2]:.6f};;\n")
            if material.texture_filename:
                file.write("\tTextureFilename {"+"\n\t\t\""+material.texture_filename+"\";\n\t}\n")
            file.write("}\n\n")
    
    def find_frame_by_name_or_nickname(self, frames, name, nickname):
        for frame in frames:
            if frame['name'] == name or frame['name'] == nickname:
                return frame
        return None

    def write_frames(self, file, json_frame, frames, indent=0):
        # Normally, this would be printed with indent + 1 to get good formatting, but Recettear
        # wants weird, not properly formatted .x files!
        indent_str = '\t' * indent

        frame = self.find_frame_by_name_or_nickname(frames, json_frame.name, json_frame.nickname)
        if not frame:
            print(f"Frame not found for JSON Frame: {json_frame.name}/{json_frame.nickname}")  # Debug statement
            exit
            

        if frame['name'] == "Frame_World":
            #fix for Blender's import/export
            frame['transform_matrix'] = Gf.Matrix4d(
                1.000000, 0.000000, 0.000000, 0.000000, 
                0.000000, 1.000000, 0.000000, 0.000000, 
                0.000000, 0.000000, 1.000000, 0.000000, 
                0.000000, 0.000000, 0.000000, 1.000000
            )

        file.write(f"{indent_str}Frame {json_frame.name} {{\n")
        if frame['transform_matrix']:
            file.write(f"{indent_str}\tFrameTransformMatrix {{\n")

            matrix = frame['transform_matrix']
            row = matrix.GetRow(0)
            row1 = matrix.GetRow(1)
            row2 = matrix.GetRow(2)
            row3 = matrix.GetRow(3)

            file.write(f"{indent_str}\t\t{row[0]:0.6f},{row[1]:0.6f},{row[2]:0.6f},{row[3]:0.6f},\n")
            file.write(f"{indent_str}\t\t{row1[0]:0.6f},{row1[1]:0.6f},{row1[2]:0.6f},{row1[3]:0.6f},\n")
            file.write(f"{indent_str}\t\t{row2[0]:0.6f},{row2[1]:0.6f},{row2[2]:0.6f},{row2[3]:0.6f},\n")
            file.write(f"{indent_str}\t\t{row3[0]:0.6f},{row3[1]:0.6f},{row3[2]:0.6f},{row3[3]:0.6f};;\n")

            file.write(f"{indent_str}\t}}\n\n")

        for mesh in frame['meshes']:
            self.write_mesh(file, mesh, json_frame.name.removeprefix("Frame_"), indent)

        for child in json_frame.children:
            self.write_frames(file, child, frame['frames'], indent)

        file.write(f"{indent_str}}}\n\n")

    def write_mesh(self, file, mesh, org_name, indent):
        indent_str = '\t' * indent
        file.write(f"{indent_str}Mesh {org_name} {{\n")

        # Vertices
        file.write(f"{indent_str}\t{len(mesh['vertices'])};\n")
        for vertex in mesh['vertices'][:-1]:
            file.write(f"{indent_str}\t{vertex[0]:0.6f};{vertex[1]:0.6f};{vertex[2]:0.6f};,\n")
        file.write(f"{indent_str}\t{mesh['vertices'][-1][0]:0.6f},{mesh['vertices'][-1][1]:0.6f},{mesh['vertices'][-1][2]:0.6f};;\n\n")

        # Faces
        file.write(f"{indent_str}\t{len(mesh['faces'])};\n")
        for face in mesh['faces'][:-1]:
            file.write(f"{indent_str}\t3;{face[0]},{face[1]},{face[2]};,\n")
        file.write(f"{indent_str}\t3;{mesh['faces'][-1][0]},{mesh['faces'][-1][1]},{mesh['faces'][-1][2]};;\n\n")

        # Materials
        file.write(indent_str + "\tMeshMaterialList {\n")
        if len(mesh['materials']['materials']) == 1:
            file.write(f"{indent_str}\t\t1;1;0;;\n")
            file.write(f"{indent_str}\t\t"+"{"+mesh['materials']['materials'][0]+"}\n")
        else:
            num_materials = len(mesh['materials']['materials'])
            num_faces = len(mesh['faces'])
            file.write(f"{indent_str}\t\t{num_materials};\n")
            file.write(f"{indent_str}\t\t{num_faces};\n")

            # Write material indices for each face, in lines of up to 30
            material_indices = mesh['materials']['material_indices']
            indices_str = indent_str + "\t\t"
            for i, idx in enumerate(material_indices):
                indices_str += str(idx) + ","
                if (i + 1) % 30 == 0:
                    indices_str += "\n" + indent_str + "\t\t"
            indices_str = indices_str.removesuffix("\n" + indent_str + "\t\t")
            indices_str = indices_str.removesuffix(",")  + ";;\n"
            file.write(indices_str)
            
            # Write material names
            for material in mesh['materials']['materials']:
                file.write(indent_str + "\t\t{" + material + "}\n")

        file.write(indent_str + "\t}\n\n")

        # Normals
        file.write(f"{indent_str}\tMeshNormals {{\n")
        file.write(f"{indent_str}\t\t{len(mesh['normals'])};\n")
        for normal in mesh['normals'][:-1]:
            file.write(f"{indent_str}\t\t{normal[0]:0.6f},{normal[1]:0.6f},{normal[2]:0.6f};,\n")
        file.write(f"{indent_str}\t\t{mesh['normals'][-1][0]:0.6f},{mesh['normals'][-1][1]:0.6f},{mesh['normals'][-1][2]:0.6f};;\n\n")

        file.write(f"{indent_str}\t\t{len(mesh['normal_faces'])};\n")
        for face in mesh['normal_faces'][:-1]:
            file.write(f"{indent_str}\t\t3;{face[0]},{face[1]},{face[2]};,\n")
        file.write(f"{indent_str}\t\t3;{mesh['normal_faces'][-1][0]},{mesh['normal_faces'][-1][1]},{mesh['normal_faces'][-1][2]};;\n")
        file.write(f"{indent_str}\t}}\n\n")

        # Vertex Colors
        if mesh['colors']:
            file.write(f"{indent_str}\tMeshVertexColors {{\n")
            file.write(f"{indent_str}\t\t{len(mesh['colors'])};\n")
            for i, color in enumerate(mesh['colors'][:-1]):
                file.write(f"{indent_str}\t\t{i};{color[0]:0.6f},{color[1]:0.6f},{color[2]:0.6f},1.0;,\n")
            file.write(f"{indent_str}\t\t{len(mesh['colors'])-1};{mesh['colors'][-1][0]:0.6f},{mesh['colors'][-1][1]:0.6f},{mesh['colors'][-1][2]:0.6f},1.0;;\n")
            file.write(f"{indent_str}\t}}\n\n")

        # Texture Coordinates
        if mesh['uvs']:
            file.write(f"{indent_str}\tMeshTextureCoords {{\n")
            file.write(f"{indent_str}\t\t{len(mesh['uvs'])};\n")
            for uv in mesh['uvs'][:-1]:
                file.write(f"{indent_str}\t\t{uv[0]:0.6f};{(uv[1]):0.6f};,\n")
            file.write(f"{indent_str}\t\t{mesh['uvs'][-1][0]:0.6f};{(mesh['uvs'][-1][1]):0.6f};;\n")
            file.write(f"{indent_str}\t}}\n\n")

        file.write(f"{indent_str}}}\n")

class FrameJSON:
    def __init__(self, name, nickname):
        self.name = name
        self.nickname = nickname
        self.children = []

def decode_json_to_frames(json_data):
    def decode_frame(frame_dict):
        frame = FrameJSON(frame_dict['name'], frame_dict['nickname'])
        frame.children = [decode_frame(child) for child in frame_dict.get('children', [])]
        return frame
    return decode_frame(json_data)



if __name__ == "__main__":
    converter = USDToXConverter('train_iwa_2.usdc')
    converter.convert('train_iwa_2.x')

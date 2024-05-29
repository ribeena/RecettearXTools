import re, json
from collections import namedtuple, defaultdict

print_debug = False
print_anim_debug = False
Material = namedtuple('Material', ['name', 'face_color', 'power', 'specular_color', 'emissive_color', 'texture_filename'])
Keyframe = namedtuple('Keyframe', ['frame', 'dim', 'values'])
Animation = namedtuple('Animation', ['type', 'bone_name', 'keyframes'])

class XFileParser:
    def __init__(self, filename):
        self.filename = filename
        self.frames = []
        self.materials = []
        self.animations = {}
        self.json_root = None
        self.frame_json = None
        self.parent_frame_json = None

    def parse(self):
        with open(self.filename, 'r', encoding='shift_jis', errors='ignore') as file:
            lines = iter(file.readlines())
            self.parse_lines(lines)

    def parse_lines(self, lines):
        
        materials_data = []
        state = 'materials'

        frame_data = {'name': None, 'transform_matrix': None, 'meshes': [], 'frames': []}
        current_frame = frame_data
        frame_json = None
        frame_stack = []
        mesh_data = None

        for line in lines:
            line = line.split("//")[0] #ignore any comments
            line = line.strip()

            if state == 'materials':
                if line.startswith('Material '):
                    name = line.split()[1]
                    if print_debug: print(f"Material: {name}")

                    line = next(lines).strip()
                    properties = list(filter(None, line.split(';')))
                    face_color = tuple(map(float, properties[0:4]))

                    line = next(lines).strip()
                    properties = list(filter(None, line.split(';')))
                    power = float(properties[0])
                
                    line = next(lines).strip()
                    properties = list(filter(None, line.split(';')))
                    specular_color = tuple(map(float, properties[0:4]))

                    line = next(lines).strip()
                    properties = list(filter(None, line.split(';')))
                    emissive_color = tuple(map(float, properties[0:4]))
                
                    line = next(lines).strip()
                    texture_filename = None

                    if line.startswith('TextureFilename '):
                        line = next(lines).strip()
                        texture_filename = line.split('"')[1]
                        line = next(lines).strip()
                
                    materials_data.append(Material(name, face_color, power, specular_color, emissive_color, texture_filename))
                elif line.startswith('Frame '):
                    self.materials.extend(materials_data)

                    #create the root frame
                    frame_name = line.split()[1]
                    current_frame['name'] = frame_name

                    frame_json = FrameJSON(frame_name)
                    self.json_root = frame_json
                    self.parent_frame_json = frame_json

                    state = 'header'

            else:
                if line.startswith('Frame '):
                    frame_name = line.split()[1]
                    new_frame = {'name': frame_name, 'transform_matrix': None, 'meshes': [], 'frames': []}
                    current_frame['frames'].append(new_frame)
                    frame_stack.append(current_frame)

                    frame_json = FrameJSON(frame_name)
                
                    if self.parent_frame_json.name == current_frame["name"]:
                        self.parent_frame_json.children.append(frame_json)
                        frame_json.parent = self.parent_frame_json
                    else:
                        # Start a new parent structure
                        self.parent_frame_json = self.parent_frame_json.children[-1]

                        frame_json.parent = self.parent_frame_json
                        self.parent_frame_json.children.append(frame_json)

                    current_frame = new_frame
                    state = 'header'

                    if print_debug: print(f"Frame: {frame_name}")
            
                elif line.startswith('AnimationSet '):
                    print("Start animation")
                    self.parse_animation_set(lines, line)

                elif line.startswith('Mesh '):
                    mesh_name = line.split()[1]
                    mesh_data = {'name': mesh_name, 'vertices': [], 'normals': [], 'normal_faces': [], 'uvs': [], 'colors': [], 'faces': [], 'materials': {'material_indices': [], 'materials': []}}
                    current_frame['meshes'].append(mesh_data)
                    state = 'vertices_count'
                    if print_debug: print(f"Mesh: {mesh_name}")

                elif line.startswith('FrameTransformMatrix'):
                    matrix_data = []
                    line = next(lines).strip()
                    while not line.endswith(';;'):
                        matrix_data.append(line)
                        line = next(lines).strip()
                    matrix_data.append(line[:-2].strip())
                    current_frame['transform_matrix'] = ' '.join(matrix_data)
                    if print_debug: print(f"Transform Matrix: {current_frame['transform_matrix']}")
                    state = 'mesh'
                    continue

                elif state == 'vertices_count' and re.match(r'^\d+;$', line):
                    vertex_count = int(line[:-1])
                    state = 'vertices'
                    if print_debug: print(f"Vertices to process: {vertex_count}")

                elif state == 'vertices':
                    if line == '}':
                        state = 'mesh'
                        continue
                    vertices = line.split(';')[:-1]
                    if len(vertices) == 3:
                        mesh_data['vertices'].append(tuple(map(float, vertices)))
                    if line.endswith(';;'):
                        mesh_data['vertices'].append(tuple(map(float, vertices[:3])))
                        state = 'faces_count'

                elif state == 'faces_count' and re.match(r'^\d+;$', line):
                    face_count = int(line[:-1])
                    state = 'faces'
                    if print_debug: print(f"Faces to process: {face_count}")
                    continue

                elif state == 'faces':
                    #face_data = re.findall(r'\d+', line)
                    face_data = line.split(';')[1]
                    face_data = face_data.split(',')
                    if face_data:
                        mesh_data['faces'].append(list(map(int, face_data)))
                    if len(mesh_data['faces']) == face_count:
                        state = 'mesh'

                elif state == 'mesh' and line.startswith('MeshMaterialList'):
                    mesh_data['materials'] = self.parse_material_list(lines)
                    if print_debug: print(f"Materials: {mesh_data['materials']}")

                elif state == 'mesh' and line.startswith('MeshNormals'):
                    state = 'normals_count'

                elif state == 'normals_count' and re.match(r'^\d+;$', line):
                    normals_count = int(line[:-1])
                    state = 'normals'
                    if print_debug: print(f"Normals to process: {normals_count}")

                elif state == 'normals':
                    if line == '}':
                        state = 'mesh'
                        continue
                    normals = line.split(';')[:-1]
                    if len(normals) == 3:
                        mesh_data['normals'].append(tuple(map(float, normals)))
                    if line.endswith(';;'):
                        mesh_data['normals'].append(tuple(map(float, normals[:3])))
                        state = 'normal_faces_count'
                        #print(mesh_data['normals'])
                        continue

                elif state == 'normal_faces_count' and re.match(r'^\d+;$', line):
                    normal_face_count = int(line[:-1])
                    state = 'normal_faces'
                    if print_debug: print(f"Normal faces to process: {normal_face_count}")
                    continue

                elif state == 'normal_faces':
                    if line == '}':
                        state = 'mesh'
                        continue
                    face_data = line.split(';')[1]
                    face_data = face_data.split(',')
                    if face_data:
                        mesh_data['normal_faces'].append(list(map(int, face_data)))

                elif state == 'mesh' and line.startswith('MeshTextureCoords'):
                    state = 'uvs_count'

                elif state == 'uvs_count' and re.match(r'^\d+;$', line):
                    uvs_count = int(line[:-1])
                    state = 'uvs'
                    if print_debug: print(f"UVs to process: {uvs_count}")

                elif state == 'uvs':
                    if line == '}':
                        state = 'mesh'
                        continue
                    uvs = line.split(';')[:-1]
                    if len(uvs) == 2:
                        mesh_data['uvs'].append(tuple(map(float, uvs)))
                    elif line.endswith(';;'):
                        mesh_data['uvs'].append(tuple(map(float, uvs[:2])))

                elif state == 'mesh' and line.startswith('MeshVertexColors'):
                    state = 'colors_count'

                elif state == 'colors_count' and re.match(r'^\d+;$', line):
                    colors_count = int(line[:-1])
                    state = 'colors'
                    if print_debug: print(f"Vertex Colours to process: {colors_count}")

                elif state == 'colors':
                    if line == '}':
                        state = 'mesh'
                    colors = list(filter(None, line.split(';')[1:]))
                    if len(colors) >= 3:
                        colors = colors[:3]
                        mesh_data['colors'].append(tuple(map(float, colors)))

                elif line == '}':
                    if state == 'mesh':
                        state = None

                        continue
                    elif frame_stack:
                        if print_debug: print(f"--- Frame finished: {current_frame['name']}")
                        current_frame = frame_stack.pop()

                        if self.parent_frame_json.name != current_frame["name"]:
                            print(f"--- json {self.parent_frame_json.name}")
                            self.parent_frame_json = self.parent_frame_json.parent
                        
                    elif state != 'header':
                        if print_debug: print(f"--- process finished ---")
                        if self.json_root is not None:
                            #print("tree is...")
                            #print(self.json_root.toJSON())
                            # The file is ready to write
                            self.export_to_json(self.filename.removesuffix(".x")+"_frames.json")

                            # record the frames
                            self.frames.append(frame_data)

    def export_to_json(self, output_json_file):
        with open(output_json_file, 'w') as f:
            f.write(self.json_root.toJSON())

    def parse_material_list(self, lines):
        material_data = {'material_indices': [], 'materials': []}
        material_list_str = ""
        while True:
            line = next(lines).strip()
            material_list_str += line + " "
            if line.endswith(';;'):
                break

        material_list_str = material_list_str[:-2]  # Remove the trailing ";;"
        parts = material_list_str.split(';')
        material_count = int(parts[0])
        face_count = int(parts[1])

        # Correctly parse the material indices
        indices_str = parts[2].replace(',', ' ')
        indices = indices_str.split()
        material_indices = list(map(int, indices))

        material_data['material_indices'] = material_indices[:face_count]

        for _ in range(material_count):
            line = next(lines).strip()
            while not line.endswith('}'):
                line += ' ' + next(lines).strip()
            material_name = re.search(r'{(.+?)}', line).group(1).strip()
            material_data['materials'].append(material_name)

        line = next(lines).strip()
        while line != '}':
            line = next(lines).strip()

        return material_data
    
    def parse_animation_set(self, lines, line):
        animation_set_name = None
        animation_name = None
        key_type = None
        key_data = []
        bone_name = None
        play_once_val = False
        stripped_line = line

        state = 'animation_set'
        while state != 'finished':
            stripped_line = stripped_line.split('//')[0].strip()
            
            if state == 'animation_set' and stripped_line.startswith('AnimationSet '):
                animation_set_name = stripped_line.split()[1]
                if print_anim_debug: print("Animation Set: "+animation_set_name)
                self.animations[animation_set_name] = {'animations': defaultdict(list), 'play_once': {}}
                state = 'animation'
            
            elif state == 'animation' and stripped_line.startswith('Animation '):
                animation_name = stripped_line.split()[1]
                if print_anim_debug: print("  Animation: "+animation_name)
                self.animations[animation_set_name]['animations'][animation_name] = []
                state = 'bone'
            
            elif state == 'bone' and stripped_line.startswith('{') and stripped_line.endswith('}'):
                bone_name = stripped_line.split('{')[1].split('}')[0]
                if print_anim_debug: print("    Bone: "+bone_name)
                state = 'key'

            elif state == 'key' and stripped_line.startswith('AnimationOptions '):
                play_once_val = stripped_line.removeprefix('AnimationOptions {').split(";")[0].strip() == '0'
                self.animations[animation_set_name]['play_once'][animation_name] = play_once_val
                if print_anim_debug: print(f'      Play once: {play_once_val}') 

            elif state == 'key' and stripped_line.startswith('AnimationKey '):
                key_data = []
                key_type = None
            
            elif stripped_line.startswith('}'):
                if state == 'key_data':
                    for entry in key_data:
                        frame, dim, values = entry.split(';')
                        self.animations[animation_set_name]['animations'][animation_name].append(Animation(
                            type=key_type,
                            bone_name=bone_name,
                            keyframes=[Keyframe(
                                frame=int(frame),
                                dim=int(dim),
                                values=list(map(float, values.strip().split(',')))
                            )]
                        ))
                    state = 'key'
                elif state == 'key':
                    state = 'animation'
                elif state == 'animation':
                    state = 'finished'
                    return
            
            elif state == 'key' and stripped_line.endswith(';'):
                key_type = stripped_line.split(';')[0]
                if key_type == '0':
                    key_type = 'Rotation'
                elif key_type == '1':
                    key_type = 'Scale'
                elif key_type == '2':
                    key_type = 'Position'
                state = 'key_count'
                if print_anim_debug: print('    Key for: '+key_type)

            elif state == 'key_count' and stripped_line.endswith(';'):
                key_count = int(stripped_line.split(';')[0])
                state = 'key_data'

            elif state == 'key_data' and stripped_line.endswith(';'):
                key_data.append(stripped_line.split('//')[0].split(';;')[0])
                if print_anim_debug: print('      '+stripped_line.split('//')[0].split(';;')[0])
            
            stripped_line = next(lines)

    # To print parsed data for debugging
    def print_parsed_data(self, frames, materials, indent=0):
        indent_str = '  ' * indent
        for material in materials:
            if material:
                print(material)
                print(f"Material: {material.name}")
                print(f"{indent_str}  Face Color: {material.face_color}")
                print(f"{indent_str}  Specular Color: {material.specular_color}")
                print(f"{indent_str}  Emissive Color: {material.emissive_color}")
                print(f"{indent_str}  Roughness: {material.power}")
                if material.texture_filename:
                    print(f"{indent_str}  File: {material.texture_filename}")

        for frame in frames:
            print(f"{indent_str}Frame: {frame['name']}")
            if frame['transform_matrix']:
                print(f"{indent_str}  Transform Matrix: {frame['transform_matrix']}")
            for mesh in frame['meshes']:
                print(f"{indent_str}  Mesh: {mesh['name']}")
                print(f"{indent_str}    Vertices: {len(mesh['vertices'])}")
                print(f"{indent_str}    Normals: {len(mesh['normals'])}")
                print(f"{indent_str}    Face Normals: {len(mesh['normal_faces'])}")
                print(f"{indent_str}    UVs: {len(mesh['uvs'])}")
                print(f"{indent_str}    Colors: {len(mesh['colors'])}")
                print(f"{indent_str}    Faces: {len(mesh['faces'])}")
                print(f"{indent_str}    Material Indices: {len(mesh['materials']['material_indices'])}")
                print(f"{indent_str}    Materials: {len(mesh['materials']['materials'])}")
            if frame['frames']:
                self.print_parsed_data(frame['frames'], [], indent + 1)

class FrameJSON:
    def __init__(self, name, parent=None):
        self.name = name
        self.nickname = name.removeprefix("Frame_")
        self.parent = parent
        self.children = []

    def toJSON(self, indent=0):
        toreturn = ("  "*indent)+"{\n"
        toreturn += f'{("  "*indent)}  "name": "{self.name}",\n'
        toreturn += f'{("  "*indent)}  "nickname": "{self.nickname}"'
        if self.children and len(self.children) > 0:
            toreturn += f',\n{("  "*indent)}  "children": ['
            for child in self.children:
                toreturn += "\n"+child.toJSON(indent+2)+','
            toreturn = toreturn.removesuffix(',')
            toreturn += f'\n{("  "*indent)}  ]\n'
        else:
            toreturn += '\n'
        toreturn += ("  "*indent)+"}"
        return toreturn

if __name__ == "__main__":
    print_debug = True
    parser = XFileParser('train_iwa.x')
    parser.parse()
    parser.print_parsed_data(parser.frames, parser.materials)

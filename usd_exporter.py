from pxr import Usd, UsdGeom, Gf, Sdf, UsdShade, UsdSkel, Vt, Tf
import json

class USDExporter:
    def __init__(self, frames, materials, animations):
        self.frames = frames
        self.materials = materials
        self.animations = animations

        self.textureList = []
        self.skipAnimations = True

    def export(self, output_usd_file):
        stage = Usd.Stage.CreateNew(output_usd_file)
        self.create_materials(stage)
        self.process_frames(stage, self.frames, None)
        if not self.skipAnimations:
            self.add_animation_sets(stage, self.animations)
        
        if len(self.textureList):
            print("Copy the following files into this directory:")
            self.textureList.sort()
            for texture in self.textureList:
                print("  -  "+texture)

        stage.GetRootLayer().Save()

        # Save specular colors to JSON
        self.save_specular_colors_to_json(output_usd_file.removesuffix('.usd') +'_speculars.json')
    
    def save_specular_colors_to_json(self, json_file):
        specular_colors = {material.name: material.specular_color for material in self.materials}
        with open(json_file, 'w') as f:
            json.dump(specular_colors, f, indent=4)
        print(f"Specular color file created: '{json_file}'")

    
    def add_to_texture_list(self, filename):
        if filename in self.textureList:
            return
        else:
            self.textureList.append(filename)

    def create_materials(self, stage):
        
        for material in self.materials:
            
            mat_path = f'/Materials/{material.name}'
            usd_material = UsdShade.Material.Define(stage, mat_path)
            
            # Creating the shader
            shader_path = f'{mat_path}/Shader'
            usd_shader = UsdShade.Shader.Define(stage, shader_path)
            usd_shader.CreateIdAttr('UsdPreviewSurface')
            
            # Setting shader parameters
            usd_shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(*material.face_color[:3]))

            #usd_shader.CreateInput('specularColor', Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(*material.specular_color))
            usd_shader.CreateInput('customSpecularColor', Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(*material.specular_color))
            
            usd_shader.CreateInput('emissiveColor', Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(*material.emissive_color))
            usd_shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1.0 / material.power)
            
            if material.texture_filename:
                texture_path = f'{mat_path}/Texture'
                usd_texture = UsdShade.Shader.Define(stage, texture_path)
                usd_texture.CreateIdAttr('UsdUVTexture')
                usd_texture.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(material.texture_filename.strip('"'))
                self.add_to_texture_list(material.texture_filename) #just a helper so you know the textures the file uses
                usd_texture.CreateOutput('rgb', Sdf.ValueTypeNames.Float3)
                usd_shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(usd_texture.ConnectableAPI(), 'rgb')

            # Binding shader to material
            usd_material.CreateSurfaceOutput().ConnectToSource(usd_shader.ConnectableAPI(), 'surface')

    def process_frames(self, stage, frames, parent):
        for frame in frames:
            frame_name = frame['name']
            transform_matrix = frame['transform_matrix']
            meshes = frame['meshes']

            if parent:
                xform = UsdGeom.Xform.Define(stage, parent.GetPath().AppendChild(frame_name))
            else:
                xform = UsdGeom.Xform.Define(stage, f'/{frame_name}')

            if transform_matrix:
                transform_matrix_parts = [x.strip() for x in transform_matrix.split(',')]
                transform_matrix_parts = list(map(float, transform_matrix_parts))
                matrix = Gf.Matrix4d(*transform_matrix_parts)
                xform.AddTransformOp().Set(matrix)

            for mesh in meshes:
                self.add_mesh(stage, mesh, xform)

            self.process_frames(stage, frame['frames'], xform)

    def add_mesh(self, stage, mesh, xform):
        mesh_name = mesh['name']
        mesh_path = xform.GetPath().AppendChild(mesh_name)
        usd_mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        usd_mesh.GetPointsAttr().Set([Gf.Vec3f(*vertex) for vertex in mesh['vertices']])
        usd_mesh.GetFaceVertexIndicesAttr().Set([index for face in mesh['faces'] for index in face])
        usd_mesh.GetFaceVertexCountsAttr().Set([len(face) for face in mesh['faces']])

        if mesh['normals']:
            usd_mesh.GetNormalsAttr().Set([Gf.Vec3f(*normal) for normal in mesh['normals']])
            usd_mesh.SetNormalsInterpolation('vertex')

        if mesh['uvs']:

            primvar_api = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim())
            uv_set = primvar_api.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying)
            #flip UV
            # Adjust UV coordinates to fix vertical mirroring
            adjusted_uvs = []
            for uv in mesh['uvs']:
                u, v = uv
                adjusted_uv = [u, 1.0 - v]  # Flip V coordinate
                adjusted_uvs.append(adjusted_uv)
            uv_set.Set([Gf.Vec2f(*uv) for uv in adjusted_uvs])

        if mesh['colors']:
            primvar_api = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim())
            color_set = primvar_api.CreatePrimvar("displayColor", Sdf.ValueTypeNames.Color3fArray,"vertex")
            color_set.Set([Gf.Vec3f(color[0], color[1], color[2]) for color in mesh['colors']])

        if 'materials' in mesh:
            if len(mesh['materials']['materials']) > 0:
                if len(mesh['materials']['material_indices']) == 1:
                    material_path = f"/Materials/{mesh['materials']['materials'][0]}"
                    material = UsdShade.Material.Get(stage, material_path)
                    usd_shader = UsdShade.Shader.Get(stage, f'{material_path}/Shader')
                    UsdShade.MaterialBindingAPI(usd_mesh).Bind(material)
                else:
                    # Group face indices by material index
                    material_faces = {}
                    for face_index, material_index in enumerate(mesh['materials']['material_indices']):
                        if material_index not in material_faces:
                            material_faces[material_index] = []
                        material_faces[material_index].append(face_index)
                    
                    # Apply materials to face subsets
                    for material_index, face_indexes in material_faces.items():
                        if material_index < len(mesh['materials']['materials']):
                            material_name = mesh['materials']['materials'][material_index]
                            material_path = f'/Materials/{material_name}'
                            
                            # Get or create material and shader
                            material = UsdShade.Material.Get(stage, material_path)
                            usd_shader = UsdShade.Shader.Get(stage, f'{material_path}/Shader')
                            
                            # Create face subset and bind material
                            face_subset = UsdGeom.Subset.Define(stage, mesh_path.AppendChild(f'MaterialSubset_{material_index}'))
                            face_subset.CreateElementTypeAttr(UsdGeom.Tokens.face)
                            face_subset.CreateIndicesAttr(face_indexes)

                            # Bind material to the subset
                            subset_binding_api = UsdShade.MaterialBindingAPI(face_subset.GetPrim())
                            subset_binding_api.Bind(material)
        else:
            print(f"{mesh['name']} doesn't have materials")
        
    def add_animation_sets(self, stage, animations):
        for anim_set_name, anim_set_data in animations.items():
            self.create_usd_skeleton(stage, anim_set_name, anim_set_data)

    def create_usd_skeleton(self, stage, anim_set_name, anim_set_data):
        root_path = f"/{anim_set_name}"
        skeleton = UsdSkel.Skeleton.Define(stage, root_path + "/Skeleton")
        bone_names = set()

        for anim_name, anim_list in anim_set_data['animations'].items():
            for animation in anim_list:
                bone_names.add(animation.bone_name)

        joints = list(bone_names)
        skeleton.CreateJointsAttr().Set(joints)

        # Use identity matrices for the bind transforms and rest transforms
        transforms = [Gf.Matrix4d(1.0) for _ in joints]
        skeleton.CreateBindTransformsAttr().Set(transforms)
        skeleton.CreateRestTransformsAttr().Set(transforms)

        # Create the animation and set the joint names
        anim = UsdSkel.Animation.Define(stage, root_path + "/Anim")
        anim.CreateJointsAttr().Set(joints)

        # Create a mapping of joint names to indices
        joint_indices = {joint_name: index for index, joint_name in enumerate(joints)}

        # Initialize rotation, scale, and position data
        rotation_times = set()
        scale_times = set()
        position_times = set()

        # Collect keyframes for each joint
        rotation_keyframes = {joint: [] for joint in joints}
        scale_keyframes = {joint: [] for joint in joints}
        position_keyframes = {joint: [] for joint in joints}

        for joint_name in joints:
            for anim_name, anim_list in anim_set_data['animations'].items():
                for animation in anim_list:
                    if animation.bone_name == joint_name:
                        for keyframe in animation.keyframes:
                            frame = keyframe.frame
                            if animation.type == 'Rotation':
                                rotation_times.add(frame)
                                rotation_keyframes[joint_name].append((frame, Gf.Quatf(
                                    keyframe.values[3], keyframe.values[0], keyframe.values[1], keyframe.values[2]
                                )))
                            elif animation.type == 'Scale':
                                scale_times.add(frame)
                                scale_keyframes[joint_name].append((frame, Gf.Vec3f(
                                    keyframe.values[0], keyframe.values[1], keyframe.values[2]
                                )))
                            elif animation.type == 'Position':
                                position_times.add(frame)
                                position_keyframes[joint_name].append((frame, Gf.Vec3f(
                                    keyframe.values[0], keyframe.values[1], keyframe.values[2]
                                )))

        # Sort times and keyframes
        rotation_times = sorted(rotation_times)
        scale_times = sorted(scale_times)
        position_times = sorted(position_times)

        # Ensure all joints have values for all time steps
        def ensure_values_for_all_times(joint_keyframes, times, default_value):
            values = {time: default_value for time in times}
            for frame, value in joint_keyframes:
                values[frame] = value
            return [values[time] for time in times]
        
        end_time = 0

        # Set the rotation values and times
        for time in rotation_times:
            rotation_values_per_joint = [
                ensure_values_for_all_times(rotation_keyframes[joint_name], rotation_times, Gf.Quatf(1.0, 0.0, 0.0, 0.0))
                for joint_name in joints
            ]
            for joint_index, values in enumerate(rotation_values_per_joint):
                vt_rotation_values = Vt.QuatfArray(values)
                anim.GetRotationsAttr().Set(vt_rotation_values, time)
                if time > end_time: end_time = time

        # Set the scale values and times
        for time in scale_times:
            scale_values_per_joint = [
                ensure_values_for_all_times(scale_keyframes[joint_name], scale_times, Gf.Vec3f(1.0, 1.0, 1.0))
                for joint_name in joints
            ]
            for joint_index, values in enumerate(scale_values_per_joint):
                vt_scale_values = Vt.Vec3fArray(values)
                anim.GetScalesAttr().Set(vt_scale_values, time)
                if time > end_time: end_time = time

        # Set the position values and times
        for time in position_times:
            position_values_per_joint = [
                ensure_values_for_all_times(position_keyframes[joint_name], position_times, Gf.Vec3f(0.0, 0.0, 0.0))
                for joint_name in joints
            ]
            for joint_index, values in enumerate(position_values_per_joint):
                vt_position_values = Vt.Vec3fArray(values)
                anim.GetTranslationsAttr().Set(vt_position_values, time)
                if time > end_time: end_time = time

        # Bind the skeleton to the animation
        skel_anim_binding = UsdSkel.BindingAPI.Apply(stage.GetPrimAtPath(root_path + "/Skeleton"))
        skel_anim_binding.CreateAnimationSourceRel().AddTarget(anim.GetPath())

        # Set animation preview timeline
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(end_time)

        # Handle play once / loop option
        # for anim_name in anim_set_data['animations']:
        #     play_once_val = anim_set_data['play_once'][anim_name]
        #     if play_once_val:
        #         anim.GetPrim().SetMetadata("playMode", "playOnce")
        #     else:
        #         anim.GetPrim().SetMetadata("playMode", "loop")

        return skeleton
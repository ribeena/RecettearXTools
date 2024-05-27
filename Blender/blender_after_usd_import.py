import bpy
############## Recettear USD Toolkit - Better Material Previews
# This script adjusts the materials of the selected objects in Blender.
# It connects vertex colors to the Base Color of Principled BSDF shaders.
# For .tga files, it also connects the alpha channel and sets blend mode to "Alpha Blend".
# For .bmp files, it converts #00FF00 pixels to alpha 0, connects to alpha, and sets blend mode to "Alpha Clip".

# Run this script after importing the USD file into Blender.

def make_green_alpha(mat, tex_node, principled_node):
    """Converts green (#00FF00) pixels to alpha 0 and connects to the BSDF node"""
    # Create a Separate RGB node to separate the texture colors
    separate_rgb_node = mat.node_tree.nodes.new("ShaderNodeSeparateRGB")
    separate_rgb_node.location = tex_node.location[0] + 300, tex_node.location[1]

    # Create Math nodes to isolate the green channel and check R and B are less than 0.01
    green_isolation_node = mat.node_tree.nodes.new("ShaderNodeMath")
    green_isolation_node.operation = 'GREATER_THAN'
    green_isolation_node.inputs[1].default_value = 0.99  # Threshold for green channel
    green_isolation_node.location = separate_rgb_node.location[0] + 150, separate_rgb_node.location[1]

    red_check_node = mat.node_tree.nodes.new("ShaderNodeMath")
    red_check_node.operation = 'LESS_THAN'
    red_check_node.inputs[1].default_value = 0.01  # Threshold for red channel
    red_check_node.location = separate_rgb_node.location[0] + 150, separate_rgb_node.location[1] - 100

    blue_check_node = mat.node_tree.nodes.new("ShaderNodeMath")
    blue_check_node.operation = 'LESS_THAN'
    blue_check_node.inputs[1].default_value = 0.01  # Threshold for blue channel
    blue_check_node.location = separate_rgb_node.location[0] + 150, separate_rgb_node.location[1] - 200

    # Create a Multiply node to combine the checks
    multiply_node = mat.node_tree.nodes.new("ShaderNodeMath")
    multiply_node.operation = 'MULTIPLY'
    multiply_node.location = green_isolation_node.location[0] + 150, green_isolation_node.location[1]

    multiply_node_2 = mat.node_tree.nodes.new("ShaderNodeMath")
    multiply_node_2.operation = 'MULTIPLY'
    multiply_node_2.location = multiply_node.location[0] + 150, multiply_node.location[1]

    # Create an Invert node to invert the green mask
    invert_node = mat.node_tree.nodes.new("ShaderNodeInvert")
    invert_node.location = multiply_node_2.location[0] + 150, multiply_node_2.location[1]

    # Link nodes
    mat.node_tree.links.new(tex_node.outputs["Color"], separate_rgb_node.inputs[0])
    mat.node_tree.links.new(separate_rgb_node.outputs["G"], green_isolation_node.inputs[0])
    mat.node_tree.links.new(separate_rgb_node.outputs["R"], red_check_node.inputs[0])
    mat.node_tree.links.new(separate_rgb_node.outputs["B"], blue_check_node.inputs[0])
    mat.node_tree.links.new(green_isolation_node.outputs["Value"], multiply_node.inputs[0])
    mat.node_tree.links.new(red_check_node.outputs["Value"], multiply_node.inputs[1])
    mat.node_tree.links.new(multiply_node.outputs["Value"], multiply_node_2.inputs[0])
    mat.node_tree.links.new(blue_check_node.outputs["Value"], multiply_node_2.inputs[1])
    mat.node_tree.links.new(multiply_node_2.outputs["Value"], invert_node.inputs["Color"])
    mat.node_tree.links.new(invert_node.outputs["Color"], principled_node.inputs["Alpha"])

    # Set blend mode to Alpha Clip
    mat.blend_method = 'CLIP'

# Iterate through all the selected objects
for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        # Check if the object has materials
        if obj.data.materials:
            for mat in obj.data.materials:
                # Ensure the material uses nodes
                mat.use_nodes = True

                # Find Principled BSDF node
                principled_node = None
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        principled_node = node
                        break

                if principled_node:
                    # Find Base Color texture node
                    base_color_socket = principled_node.inputs.get("Base Color")
                    if base_color_socket and base_color_socket.is_linked:
                        tex_node = base_color_socket.links[0].from_node
                        if tex_node.type == 'TEX_IMAGE':
                            # Set the interpolation to Closest
                            tex_node.interpolation = 'Closest'
                            
                            # Determine texture file type
                            texture_file = tex_node.image.filepath.lower()
                            if texture_file.endswith('.tga'):
                                # Use Mix RGB node and Color Attribute node for .tga files
                                mat.node_tree.links.remove(base_color_socket.links[0])

                                # Create Mix RGB node
                                mix_rgb_node = mat.node_tree.nodes.new("ShaderNodeMixRGB")
                                mix_rgb_node.blend_type = 'MULTIPLY'
                                mix_rgb_node.location = tex_node.location[0] + 150, tex_node.location[1] - 200

                                # Create Color Attribute node
                                color_attribute_node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
                                color_attribute_node.layer_name = "displayColor"
                                color_attribute_node.location = tex_node.location[0] + 300, tex_node.location[1] + 200

                                # Connect nodes
                                mat.node_tree.links.new(tex_node.outputs["Color"], mix_rgb_node.inputs[1])
                                mat.node_tree.links.new(color_attribute_node.outputs["Color"], mix_rgb_node.inputs[2])
                                mat.node_tree.links.new(mix_rgb_node.outputs["Color"], principled_node.inputs["Base Color"])

                                # Connect the alpha channel and set blend mode to Alpha Blend
                                mat.node_tree.links.new(tex_node.outputs["Alpha"], principled_node.inputs["Alpha"])
                                mat.blend_method = 'BLEND'

                            elif texture_file.endswith('.bmp'):
                                # Remove connection from Base Color input
                                mat.node_tree.links.remove(base_color_socket.links[0])

                                # Create Mix RGB node
                                mix_rgb_node = mat.node_tree.nodes.new("ShaderNodeMixRGB")
                                mix_rgb_node.blend_type = 'MULTIPLY'
                                mix_rgb_node.location = tex_node.location[0] + 150, tex_node.location[1] - 200

                                # Create Color Attribute node
                                color_attribute_node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
                                color_attribute_node.layer_name = "displayColor"
                                color_attribute_node.location = tex_node.location[0] + 300, tex_node.location[1] + 200

                                # Connect nodes
                                mat.node_tree.links.new(tex_node.outputs["Color"], mix_rgb_node.inputs[1])
                                mat.node_tree.links.new(color_attribute_node.outputs["Color"], mix_rgb_node.inputs[2])
                                mat.node_tree.links.new(mix_rgb_node.outputs["Color"], principled_node.inputs["Base Color"])

                                # Make green color transparent for .bmp files
                                make_green_alpha(mat, tex_node, principled_node)

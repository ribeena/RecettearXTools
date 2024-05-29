import bpy
import bmesh

#########################################
# Run this script with freshly imported shape
# selected to remove any doubles and Mark
# sharp on those edges

# Tolerance for merging vertices
merge_distance = 0.0001

def merge_vertices_and_mark_sharp(obj):
    # Ensure we are in edit mode and have access to the mesh data
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="EDGE")

    # Get the BMesh representation of the mesh
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    # Select boundaries
    bpy.ops.mesh.select_non_manifold(use_boundary=True)

    # Mark the edges as sharp
    bpy.ops.mesh.mark_sharp()

    bpy.ops.mesh.select_all(action='SELECT')
    
    # Update the BMesh to reflect changes
    bmesh.update_edit_mesh(me, loop_triangles=True, destructive=True)

    # Merge vertices by distance
    bpy.ops.mesh.remove_doubles(threshold=merge_distance)

    # Update the BMesh again after merge
    bm = bmesh.from_edit_mesh(me)
    bmesh.update_edit_mesh(me, loop_triangles=True, destructive=True)

    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

# Ensure you have the object selected
obj = bpy.context.object

if obj and obj.type == 'MESH':
    merge_vertices_and_mark_sharp(obj)
else:
    print("No mesh object selected")

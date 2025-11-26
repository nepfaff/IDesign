import bpy
import json
import math
import os

object_name = 'Cube'
object_to_delete = bpy.data.objects.get(object_name)

# Check if the object exists before trying to delete it
if object_to_delete is not None:
    bpy.data.objects.remove(object_to_delete, do_unlink=True)

def import_glb(file_path, object_name):
    bpy.ops.import_scene.gltf(filepath=file_path)
    imported_object = bpy.context.view_layer.objects.active
    if imported_object is not None:
        imported_object.name = object_name

def create_room(width, depth, height):
    # Create floor
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0, 0))

    # Extrude to create walls
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(0, 0, height)})
    bpy.ops.object.mode_set(mode='OBJECT')

    # Scale the walls to the desired dimensions
    bpy.ops.transform.resize(value=(width, depth, 1))

    bpy.context.active_object.location.x += width / 2
    bpy.context.active_object.location.y += depth / 2

def find_glb_files(directory):
    glb_files = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".glb"):
                key = file.split(".")[0]
                if key not in glb_files:
                    glb_files[key] = os.path.join(root, file)
    return glb_files

def get_highest_parent_objects():
    highest_parent_objects = []

    for obj in bpy.data.objects:
        # Check if the object has no parent
        if obj.parent is None:
            highest_parent_objects.append(obj)
    return highest_parent_objects

def delete_empty_objects():
    # Iterate through all objects in the scene
    for obj in bpy.context.scene.objects:
        # Check if the object is empty (has no geometry)
        print(obj.name, obj.type)
        if obj.type == 'EMPTY':
            bpy.context.view_layer.objects.active = obj
            bpy.data.objects.remove(obj)

def select_meshes_under_empty(empty_object_name):
    # Get the empty object
    empty_object = bpy.data.objects.get(empty_object_name)
    print(empty_object is not None)
    if empty_object is not None and empty_object.type == 'EMPTY':
        # Iterate through the children of the empty object
        for child in empty_object.children:
            # Check if the child is a mesh
            if child.type == 'MESH':
                # Select the mesh
                child.select_set(True)
                bpy.context.view_layer.objects.active = child
            else:
                select_meshes_under_empty(child.name)

def rescale_object(obj, scale):
    # Ensure the object has a mesh data
    if obj.type == 'MESH':
        bbox_dimensions = obj.dimensions
        scale_factors = (
                         scale["length"] / bbox_dimensions.x, 
                         scale["width"] / bbox_dimensions.y, 
                         scale["height"] / bbox_dimensions.z
                        )
        obj.scale = scale_factors


objects_in_room = {}
file_path = "scene_graph.json"
with open(file_path, 'r') as file:
    data = json.load(file)
    for item in data:
        if item["new_object_id"] not in ["south_wall", "north_wall", "east_wall", "west_wall", "middle of the room", "ceiling"]:
            objects_in_room[item["new_object_id"]] = item

directory_path = os.path.join(os.getcwd(), "Assets")
glb_file_paths = find_glb_files(directory_path)

for item_id, object_in_room in objects_in_room.items():
    glb_file_path = os.path.join(directory_path, glb_file_paths[item_id])
    import_glb(glb_file_path, item_id)

parents = get_highest_parent_objects()
empty_parents = [parent for parent in parents if parent.type == "EMPTY"]
print(empty_parents)

for empty_parent in empty_parents:
    bpy.ops.object.select_all(action='DESELECT')
    select_meshes_under_empty(empty_parent.name)
    
    bpy.ops.object.join()
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    
    joined_object = bpy.context.view_layer.objects.active
    if joined_object is not None:
        joined_object.name = empty_parent.name + "-joined"

bpy.context.view_layer.objects.active = None

MSH_OBJS = [m for m in bpy.context.scene.objects if m.type == 'MESH']
for OBJS in MSH_OBJS:
    bpy.context.view_layer.objects.active = OBJS
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    OBJS.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.objects.active = OBJS
    OBJS.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

MSH_OBJS = [m for m in bpy.context.scene.objects if m.type == 'MESH']
for OBJS in MSH_OBJS:
    item = objects_in_room[OBJS.name.split("-")[0]]
    object_position = (item["position"]["x"], item["position"]["y"], item["position"]["z"])  # X, Y, and Z coordinates
    object_rotation_z = (item["rotation"]["z_angle"] / 180.0) * math.pi + math.pi # Rotation angles in radians around the X, Y, and Z axes
    
    bpy.ops.object.select_all(action='DESELECT')
    OBJS.select_set(True)
    OBJS.location = object_position
    bpy.ops.transform.rotate(value=object_rotation_z,  orient_axis='Z')
    rescale_object(OBJS, item["size_in_meters"])

bpy.ops.object.select_all(action='DESELECT')
delete_empty_objects()

# Get room dimensions from scene graph
room_width = 4.0
room_depth = 4.0
room_height = 2.5

for item in data:
    if item["new_object_id"] == "middle of the room":
        room_width = item["size_in_meters"]["length"]
        room_depth = item["size_in_meters"]["width"]
    if item["new_object_id"] == "ceiling":
        room_height = item["position"]["z"]

# Don't create room walls for cleaner render - just show furniture
# create_room(room_width, room_depth, room_height)

# Create a simple floor plane instead
bpy.ops.mesh.primitive_plane_add(size=max(room_width, room_depth) * 1.5, location=(room_width/2, room_depth/2, 0))
floor = bpy.context.active_object
floor.name = "Floor"

# Setup camera for rendering
def setup_camera_and_render(room_width, room_depth, room_height, output_path="render.png"):
    from mathutils import Vector

    # Position camera to see the whole room from above corner
    camera = bpy.data.objects.get('Camera')
    if camera is None:
        bpy.ops.object.camera_add()
        camera = bpy.context.active_object

    # Room center (looking at floor level where furniture is)
    room_center = Vector((room_width/2, room_depth/2, 0.5))

    # Position camera high above looking down into room
    camera.location = (room_width/2, -2, room_height * 2.5)

    # Point camera at room center using direction vector
    direction = room_center - camera.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()

    # Wider field of view
    camera.data.lens = 24

    # Set as active camera
    bpy.context.scene.camera = camera

    # Remove existing lights
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Add sun light
    bpy.ops.object.light_add(type='SUN', location=(room_width/2, room_depth/2, room_height + 2))
    sun = bpy.context.active_object
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(45), 0, math.radians(45))

    # Add point light inside room for fill
    bpy.ops.object.light_add(type='POINT', location=(room_width/2, room_depth/2, room_height - 0.5))
    point = bpy.context.active_object
    point.data.energy = 500

    # Set world background to light blue-gray
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.7, 0.75, 0.8, 1)

    # Render settings
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.filepath = output_path
    bpy.context.scene.render.image_settings.file_format = 'PNG'

    # Render
    bpy.ops.render.render(write_still=True)
    print(f"Render saved to: {output_path}")

# Save blend file
blend_output = os.path.join(os.getcwd(), "scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_output)
print(f"Blend file saved to: {blend_output}")

# Render the scene
render_output = os.path.join(os.getcwd(), "render.png")
setup_camera_and_render(room_width, room_depth, room_height, render_output)
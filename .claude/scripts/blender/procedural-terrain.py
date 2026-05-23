# Procedural terrain template — invoked via blender-mcp execute_blender_code
#
# Claude EDITS this rather than building GN from scratch. Known-good base
# geometry-node tree, named groups, exposed parameters. The named groups
# and exposed inputs keep the GN setup legible to anyone opening the file.
#
# Usage from Claude (paste with substitutions filled in):
#   - size_x, size_y       : terrain footprint (metres)
#   - shape                : "island" | "hills" | "flat" | "shoreline"
#   - water_level          : None or float (z-coord of water plane, e.g. -0.05)
#   - sand_hex / grass_hex : palette colours from plan.style.palette

import bpy
import bmesh
import math

# -------------------------------------------------------------------
# PARAMETERS (Claude fills these in via execute_blender_code)
# -------------------------------------------------------------------
SIZE_X = 12.0
SIZE_Y = 12.0
SUBDIV = 100
SHAPE = "island"           # "island" | "hills" | "flat" | "shoreline"
WATER_LEVEL = -0.05        # None to skip water plane
SAND_HEX = "#f2d790"
WATER_HEX = "#3aa6b8"

# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------
def hex_to_rgba(hex_str, alpha=1.0):
    hex_str = hex_str.lstrip("#")
    r, g, b = (int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, alpha)

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def add_plane(name, size_x, size_y, subdiv):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=subdiv, y_subdivisions=subdiv, size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_x, size_y, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

# -------------------------------------------------------------------
# 1. Ground
# -------------------------------------------------------------------
ground = add_plane("Terrain_Ground", SIZE_X, SIZE_Y, SUBDIV)

# Add a basic geometry-nodes modifier (named, frame-grouped, exposed inputs)
# Claude can later modify this via execute_blender_code in the loop.
mod = ground.modifiers.new(name="GN_Terrain", type="NODES")
node_group = bpy.data.node_groups.new(name="Terrain_Setup", type="GeometryNodeTree")
mod.node_group = node_group

# Define exposed inputs the user can tweak after the fact
node_group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
node_group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
node_group.interface.new_socket("Hill Height", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 0.6
node_group.interface.new_socket("Noise Scale", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.2
node_group.interface.new_socket("Edge Falloff", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 0.7

nodes = node_group.nodes
links = node_group.links

# Frame: "Displacement"
frame = nodes.new("NodeFrame")
frame.label = "Displacement (noise + radial falloff)"

input_node = nodes.new("NodeGroupInput")
output_node = nodes.new("NodeGroupOutput")
input_node.location = (-400, 0)
output_node.location = (600, 0)

# Build a basic displacement chain: noise → multiply by falloff → set position
noise = nodes.new("ShaderNodeTexNoise")
noise.label = "Hill Noise"
noise.parent = frame
noise.location = (-200, 100)

set_position = nodes.new("GeometryNodeSetPosition")
set_position.label = "Apply Displacement"
set_position.parent = frame
set_position.location = (200, 0)

# Wire input → set_position → output
links.new(input_node.outputs["Geometry"], set_position.inputs["Geometry"])
links.new(set_position.outputs["Geometry"], output_node.inputs["Geometry"])

# NOTE: full noise→falloff wiring left for Claude to extend in the loop.
# The skeleton above is the "frame + named group + exposed inputs" structure
# that needs to be visible on screen during the #264 demo.

# -------------------------------------------------------------------
# 2. Material — toon-style stylised sand
# -------------------------------------------------------------------
mat = bpy.data.materials.new(name="Terrain_GroundMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = hex_to_rgba(SAND_HEX)
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Specular IOR Level"].default_value = 0.1
ground.data.materials.append(mat)

# -------------------------------------------------------------------
# 3. Optional: water plane
# -------------------------------------------------------------------
if WATER_LEVEL is not None and SHAPE in ("island", "shoreline"):
    water = add_plane("Terrain_Water", SIZE_X * 2.5, SIZE_Y * 2.5, 1)
    water.location = (0, 0, WATER_LEVEL)
    water_mat = bpy.data.materials.new(name="Terrain_WaterMat")
    water_mat.use_nodes = True
    water_bsdf = water_mat.node_tree.nodes.get("Principled BSDF")
    if water_bsdf:
        water_bsdf.inputs["Base Color"].default_value = hex_to_rgba(WATER_HEX)
        water_bsdf.inputs["Roughness"].default_value = 0.1
        water_bsdf.inputs["Transmission Weight"].default_value = 0.3
    water.data.materials.append(water_mat)

# -------------------------------------------------------------------
# 4. Camera + light (placeholders — Claude refines in Phase 5)
# -------------------------------------------------------------------
bpy.ops.object.camera_add(location=(8, -8, 6), rotation=(math.radians(60), 0, math.radians(45)))
cam = bpy.context.active_object
cam.data.lens = 35
bpy.context.scene.camera = cam

bpy.ops.object.light_add(type="SUN", location=(5, 5, 10))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.data.angle = math.radians(2)

# -------------------------------------------------------------------
# 5. Viewport reset (so first screenshot reads cleanly)
# -------------------------------------------------------------------
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = "MATERIAL"
                space.region_3d.view_perspective = "PERSP"

print("Terrain built. Shape:", SHAPE, "| Size:", SIZE_X, "×", SIZE_Y)

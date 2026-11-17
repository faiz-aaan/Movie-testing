"""Blender scene, built 100% from Python and directed with three cameras.

Set: a dark hall with receding stone pillars, haze with a god-ray spotlight,
a hanging bronze maze dial (texture from demo/build/disc.png as colour + bump),
and an extruded bronze 3D word on the floor.

Run:  blender -b -P scene_maze_hall.py -- <out_dir> [stills|dolly] [samples]
"""
import bpy, math, os, sys, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders")
MODE = argv[1] if len(argv) > 1 else "stills"
SAMPLES = int(argv[2]) if len(argv) > 2 else 48
HERE = os.path.dirname(os.path.abspath(__file__))
DISC_TEX = os.path.join(HERE, "..", "demo", "build", "disc.png")
os.makedirs(OUT, exist_ok=True)
random.seed(4)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------- render settings ----------
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.fps = 24
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Punchy"
sc.render.image_settings.file_format = "PNG"


def mat(name, base, metal=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


BRONZE = mat("bronze", (0.55, 0.32, 0.14), 1.0, 0.32)
STONE = mat("stone", (0.09, 0.075, 0.065), 0.0, 0.85)
FLOOR = mat("floor", (0.05, 0.04, 0.035), 0.3, 0.35)

# ---------- set ----------
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
bpy.context.object.data.materials.append(FLOOR)

for side in (-1, 1):  # two rows of pillars receding into the dark
    for i in range(7):
        y = 4 + i * 5
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.55, depth=12, location=(side * 5.5, y, 6))
        p = bpy.context.object
        p.data.materials.append(STONE)
        bpy.ops.object.shade_smooth()
        for z in (0.25, 11.75):  # base + capital
            bpy.ops.mesh.primitive_cube_add(size=1, location=(side * 5.5, y, z))
            bpy.context.object.scale = (1.5, 1.5, 0.5)
            bpy.context.object.data.materials.append(STONE)

bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 36, 10), rotation=(math.radians(90), 0, 0))
bpy.context.object.data.materials.append(STONE)

# ---------- hero: hanging maze dial ----------
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=2.6, depth=0.25, location=(0, 14, 5.2), rotation=(math.radians(90), 0, 0))
disc = bpy.context.object
bpy.ops.object.shade_smooth()
dm = mat("disc", (0.5, 0.3, 0.13), 1.0, 0.3)
if os.path.exists(DISC_TEX):
    nt = dm.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(DISC_TEX)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapn = nt.nodes.new("ShaderNodeMapping")
    mapn.inputs["Location"].default_value = (0.5, 0.5, 0)
    mapn.inputs["Scale"].default_value = (1 / 5.2, 1 / 5.2, 1)
    nt.links.new(coord.outputs["Object"], mapn.inputs["Vector"])
    # object space: disc face lies in local XY
    nt.links.new(mapn.outputs["Vector"], tex.inputs["Vector"])
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
disc.data.materials.append(dm)
disc.rotation_euler[2] = 0
disc.keyframe_insert("rotation_euler", frame=1)
disc.rotation_euler[1] = math.radians(-25)  # slow spin around its face normal
disc.keyframe_insert("rotation_euler", frame=48)

for x in (-1.2, 1.2):  # chains
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=6, location=(x, 14, 10.3))
    bpy.context.object.data.materials.append(BRONZE)

# ---------- hero: 3D word on the floor ----------
bpy.ops.object.text_add(location=(0, 8, 0))
txt = bpy.context.object
txt.data.body = "TIME"
fpath = os.path.join(HERE, "..", "demo", "fonts", "BebasNeue-Regular.ttf")
if os.path.exists(fpath):
    txt.data.font = bpy.data.fonts.load(fpath)
txt.data.size = 2.6
txt.data.extrude = 0.18
txt.data.bevel_depth = 0.02
txt.data.align_x = "CENTER"
txt.rotation_euler = (math.radians(90), 0, 0)
txt.data.materials.append(BRONZE)

# ---------- light + atmosphere ----------
bpy.ops.object.light_add(type="SPOT", location=(-4, 6, 17))
spot = bpy.context.object
spot.data.energy = 26000
spot.data.spot_size = math.radians(28)
spot.data.color = (1.0, 0.78, 0.5)
spot.rotation_euler = (Vector((0, 12, 3)) - spot.location).to_track_quat("-Z", "Y").to_euler()
bpy.ops.object.light_add(type="AREA", location=(0, -6, 4))
rim = bpy.context.object
rim.data.energy = 900
rim.data.size = 6
rim.data.color = (0.6, 0.7, 1.0)
rim.rotation_euler = (math.radians(80), 0, 0)

# practical lights: warm uplights at each pillar base (silhouettes the colonnade)
for side in (-1, 1):
    for i in range(7):
        bpy.ops.object.light_add(type="POINT", location=(side * 4.6, 4 + i * 5, 0.6))
        bpy.context.object.data.energy = 140
        bpy.context.object.data.color = (1.0, 0.6, 0.3)
# side key on the 3D word so the bevels catch light
bpy.ops.object.light_add(type="AREA", location=(5, 6, 2.5))
k = bpy.context.object; k.data.energy = 700; k.data.size = 2; k.data.color = (1.0, 0.8, 0.55)
k.rotation_euler = (Vector((0, 8, 1.3)) - k.location).to_track_quat("-Z", "Y").to_euler()
w = bpy.data.worlds.new("w"); sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.003, 0.002, 1)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 16, 8))  # haze volume
haze = bpy.context.object
haze.scale = (24, 44, 16)
hm = bpy.data.materials.new("haze"); hm.use_nodes = True
nt = hm.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
vol = nt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.018
vol.inputs["Color"].default_value = (1, 0.85, 0.7, 1)
nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(hm)

# dust motes: tiny emissive specks in the light beam
DUST = mat("dust", (1, 0.8, 0.5), emit=(1, 0.75, 0.45), strength=6)
for _ in range(140):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=random.uniform(0.008, 0.022), subdivisions=1,
                                          location=(random.uniform(-4, 4), random.uniform(5, 16), random.uniform(0.5, 9)))
    bpy.context.object.data.materials.append(DUST)


# ---------- the director's cameras ----------
def camera(name, loc, look_at, lens, fstop=None, focus=None):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object
    c.name = name
    c.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    c.data.lens = lens
    if fstop:
        c.data.dof.use_dof = True
        c.data.dof.aperture_fstop = fstop
        c.data.dof.focus_distance = focus or (Vector(look_at) - Vector(loc)).length
    return c


shots = {
    # name: (location, look-at, lens mm, f-stop, focus distance)
    "A_wide_establishing": ((0, -9, 3.2), (0, 14, 4.5), 24, None, None),
    "B_lowangle_hero_word": ((2.2, 1.5, 0.35), (0, 8, 1.2), 50, 2.0, 6.9),
    "C_closeup_dial": ((1.6, 7.5, 5.6), (0, 14, 5.2), 85, 2.8, 6.7),
}

if MODE == "stills":
    for name, (loc, at, lens, fs, fd) in shots.items():
        sc.camera = camera(name, loc, at, lens, fs, fd)
        sc.frame_set(1)
        sc.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name, flush=True)
else:  # dolly: push in from wide to the dial over 2 s, rack focus word -> dial
    c = camera("D_dolly", (0, -6, 1.6), (0, 14, 4.0), 32, 2.8, 14)
    sc.camera = c
    c.location = (0, -6, 1.6); c.keyframe_insert("location", frame=1)
    c.data.dof.focus_distance = 14.5; c.data.dof.keyframe_insert("focus_distance", frame=1)
    c.location = (0, 4.5, 3.0); c.keyframe_insert("location", frame=48)
    c.data.dof.focus_distance = 3.6; c.data.dof.keyframe_insert("focus_distance", frame=48)
    sc.frame_start, sc.frame_end = 1, 48
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.filepath = os.path.join(OUT, "dolly_")
    bpy.ops.render.render(animation=True)
    print("dolly done", flush=True)

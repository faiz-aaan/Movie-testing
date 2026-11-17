"""EMBER ROAST - a procedural cafe built in Blender from Python, filmed two ways.

  blender -b -P cafe_scene.py -- <energetic|calm> [only_shot] [test]

Everything (room, counter, espresso machine, cups, beans, lamps, sign, rain,
steam) is generated here. Each film is a list of directed shots: camera path,
lens, focus and prop animation. Frames go to renders/<film>/<shot>/####.png
at 12 fps; post.py interpolates to 24 fps with RIFE and edits to music.
"""
import bpy, math, os, random, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FILM = argv[0] if argv else "energetic"
ONLY = argv[1] if len(argv) > 1 and argv[1] != "-" else None
TEST = len(argv) > 2 and argv[2] == "test"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders", FILM)
R = random.Random(9)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
ee = sc.eevee
ee.taa_render_samples = 6 if FILM == "energetic" else 8
ee.use_raytracing = False
ee.volumetric_tile_size = "16"
ee.volumetric_samples = 32
ee.use_shadows = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.fps = 12 if FILM == "energetic" else 8
sc.render.use_motion_blur = FILM == "energetic"
sc.render.motion_blur_shutter = 0.6
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast" if FILM == "energetic" else "AgX - Base Contrast"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"


# ---------------- materials ----------------
def principled(name, color, metal=0.0, rough=0.5, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


def nodes(m):
    return m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def wood(name, dark=False):
    m = principled(name, (0.2, 0.1, 0.05), 0, 0.45)
    n, l, b = nodes(m)
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1, 14, 1)
    wv = n.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 2.5; wv.inputs["Distortion"].default_value = 6
    ramp = n.new("ShaderNodeValToRGB")
    c0 = (0.06, 0.03, 0.015, 1) if dark else (0.16, 0.075, 0.035, 1)
    c1 = (0.13, 0.06, 0.03, 1) if dark else (0.32, 0.16, 0.07, 1)
    ramp.color_ramp.elements[0].color = c0; ramp.color_ramp.elements[1].color = c1
    l.new(tc.outputs["Object"], mp.inputs["Vector"]); l.new(mp.outputs["Vector"], wv.inputs["Vector"])
    l.new(wv.outputs["Fac"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def marble(name):
    m = principled(name, (0.9, 0.88, 0.84), 0, 0.12)
    n, l, b = nodes(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3; nz.inputs["Detail"].default_value = 12
    wv = n.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 1.2; wv.inputs["Distortion"].default_value = 14
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.35, 0.34, 0.33, 1)
    ramp.color_ramp.elements[1].position = 0.12; ramp.color_ramp.elements[1].color = (0.92, 0.9, 0.86, 1)
    l.new(tc.outputs["Object"], nz.inputs["Vector"]); l.new(nz.outputs["Color"], wv.inputs["Vector"])
    l.new(wv.outputs["Fac"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def brick(name):
    m = principled(name, (0.3, 0.12, 0.07), 0, 0.85)
    n, l, b = nodes(m)
    tc = n.new("ShaderNodeTexCoord"); bk = n.new("ShaderNodeTexBrick")
    bk.inputs["Scale"].default_value = 6; bk.inputs["Mortar Size"].default_value = 0.012
    bk.inputs["Color1"].default_value = (0.32, 0.12, 0.07, 1); bk.inputs["Color2"].default_value = (0.22, 0.08, 0.05, 1)
    bk.inputs["Mortar"].default_value = (0.5, 0.45, 0.4, 1)
    upright = n.new("ShaderNodeMapping"); upright.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    l.new(tc.outputs["Object"], upright.inputs["Vector"]); l.new(upright.outputs["Vector"], bk.inputs["Vector"])
    l.new(bk.outputs["Color"], b.inputs["Base Color"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4
    l.new(bk.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def emissive(name, color, strength):
    m = principled(name, color, 0, 0.5)
    _, _, b = nodes(m)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def planks(name):
    m = principled(name, (0.2, 0.1, 0.05), 0, 0.38)
    n, l, b = nodes(m)
    tc = n.new("ShaderNodeTexCoord"); bk = n.new("ShaderNodeTexBrick")
    bk.inputs["Scale"].default_value = 1.0; bk.inputs["Mortar Size"].default_value = 0.004
    bk.inputs["Brick Width"].default_value = 1.6; bk.inputs["Row Height"].default_value = 0.16
    bk.inputs["Color1"].default_value = (0.20, 0.10, 0.045, 1); bk.inputs["Color2"].default_value = (0.11, 0.05, 0.025, 1)
    bk.inputs["Mortar"].default_value = (0.03, 0.015, 0.01, 1)
    wv = n.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 3; wv.inputs["Distortion"].default_value = 8
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.3, 6, 1)
    mix = n.new("ShaderNodeMixRGB"); mix.blend_type = "MULTIPLY"; mix.inputs["Fac"].default_value = 0.35
    l.new(tc.outputs["Object"], bk.inputs["Vector"]); l.new(tc.outputs["Object"], mp.inputs["Vector"]); l.new(mp.outputs["Vector"], wv.inputs["Vector"])
    l.new(bk.outputs["Color"], mix.inputs["Color1"]); l.new(wv.outputs["Color"], mix.inputs["Color2"])
    l.new(mix.outputs["Color"], b.inputs["Base Color"])
    return m


M = dict(
    floor=planks("floor"), counter_wood=wood("counter", dark=True), marble=marble("marble"), brick=brick("brick"),
    green=principled("green_wall", (0.03, 0.09, 0.06), 0, 0.8),
    ceiling=principled("ceiling", (0.02, 0.015, 0.012), 0, 0.9),
    chrome=principled("chrome", (0.9, 0.9, 0.9), 1, 0.12),
    copper=principled("copper", (0.95, 0.5, 0.3), 1, 0.22),
    black=principled("black", (0.01, 0.01, 0.01), 0.2, 0.35),
    ceramic=principled("ceramic", (0.93, 0.91, 0.87), 0, 0.18, **{"Coat Weight": 0.6}),
    coffee=principled("coffee", (0.05, 0.02, 0.01), 0, 0.08),
    bean=principled("bean", (0.12, 0.05, 0.02), 0, 0.3, **{"Coat Weight": 0.4}),
    glass=principled("glass", (0.9, 0.95, 0.95), 0, 0.03, **{"Transmission Weight": 1.0, "IOR": 1.45}),
    plant=principled("plant", (0.04, 0.16, 0.05), 0, 0.5),
    pot=principled("pot", (0.45, 0.22, 0.12), 0, 0.7),
    gauge=principled("gauge", (0.95, 0.93, 0.88), 0, 0.3),
)
M["neon"] = emissive("neon", (1.0, 0.42, 0.12), 0.0)
M["bulb"] = emissive("bulb", (1.0, 0.7, 0.4), 30.0)

# latte top
lat = principled("latte", (0.5, 0.3, 0.15), 0, 0.15)
n, l, b = nodes(lat)
t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(HERE, "build", "latte.png"))
tc = n.new("ShaderNodeTexCoord"); l.new(tc.outputs["UV"], t.inputs["Vector"]); l.new(t.outputs["Color"], b.inputs["Base Color"])
M["latte"] = lat


# ---------------- geometry helpers ----------------
def box(name, loc, size, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("bv", "BEVEL"); md.width = bevel; md.segments = 2
    o.data.materials.append(mat)
    return o


def cyl(name, loc, r, h, mat, rot=(0, 0, 0), verts=40, fill="NGON", smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot, end_fill_type=fill)
    o = bpy.context.object; o.name = name
    if smooth:
        bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


def sphere(name, loc, r, mat, scale=(1, 1, 1), seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()


def make_cup(name, loc, latte=True):
    root = bpy.data.objects.new(name, None); sc.collection.objects.link(root); root.location = loc
    sauc = cyl(name + "_saucer", (loc[0], loc[1], loc[2] + 0.004), 0.075, 0.008, M["ceramic"], verts=48)
    body = cyl(name + "_body", (loc[0], loc[1], loc[2] + 0.045), 0.045, 0.07, M["ceramic"], verts=48, fill="NOTHING")
    sd = body.modifiers.new("s", "SOLIDIFY"); sd.thickness = 0.004
    bot = cyl(name + "_bottom", (loc[0], loc[1], loc[2] + 0.012), 0.043, 0.006, M["ceramic"], verts=48)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.02, minor_radius=0.005, location=(loc[0] + 0.058, loc[1], loc[2] + 0.05), rotation=(math.radians(90), 0, 0))
    hnd = bpy.context.object; hnd.data.materials.append(M["ceramic"]); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=0.042, fill_type="NGON", location=(loc[0], loc[1], loc[2] + 0.07))
    top = bpy.context.object; top.name = name + "_top"
    top.data.materials.append(M["latte"] if latte else M["coffee"])
    for o in (sauc, body, bot, hnd, top):
        parent(o, root)
    root["top"] = top.name
    return root


# ---------------- the set ----------------
box("floor", (0, 0, -0.05), (16, 12, 0.1), M["floor"])
box("ceiling", (0, 0, 3.65), (16, 12, 0.1), M["ceiling"])
box("backwall", (0, 5.05, 1.8), (16, 0.1, 3.7), M["brick"])
box("rightwall", (7.05, 0, 1.8), (0.1, 12, 3.7), M["green"])
box("frontwall", (0, -6.05, 1.8), (16, 0.1, 3.7), M["green"])
# left wall with a big window (x=-7): opening y -3.2..1.2, z 0.8..3.0
for nm, loc, size in (("lw_a", (-7.05, -4.6, 1.8), (0.1, 2.8, 3.7)), ("lw_b", (-7.05, 3.1, 1.8), (0.1, 3.8, 3.7)),
                      ("lw_low", (-7.05, -1.0, 0.4), (0.1, 4.4, 0.8)), ("lw_high", (-7.05, -1.0, 3.33), (0.1, 4.4, 0.66))):
    box(nm, loc, size, M["green"])
box("sill", (-6.85, -1.0, 0.82), (0.45, 4.6, 0.05), M["counter_wood"])
for y in (-3.2, -1.0, 1.2):
    box("mullion", (-7.0, y, 1.9), (0.06, 0.06, 2.2), M["black"])
box("transom", (-7.0, -1.0, 2.2), (0.06, 4.4, 0.05), M["black"])
glass = box("window_glass", (-7.0, -1.0, 1.9), (0.01, 4.4, 2.2), M["glass"])

# outside backdrop (street light / rain) - shader set per mood
bpy.ops.mesh.primitive_plane_add(size=1, location=(-9.5, -1.0, 1.9), rotation=(0, math.radians(90), 0))
outside = bpy.context.object; outside.scale = (6, 10, 1)
OUT_M = bpy.data.materials.new("outside"); OUT_M.use_nodes = True; outside.data.materials.append(OUT_M)

# plants on the sill
for i, y in enumerate((-2.6, -1.6, 0.4)):
    cyl("pot", (-6.8, y, 0.95), 0.09, 0.2, M["pot"])
    for k in range(9):
        sphere("leaf", (-6.8 + R.uniform(-0.12, 0.12), y + R.uniform(-0.12, 0.12), 1.12 + R.uniform(0, 0.28)), R.uniform(0.05, 0.09), M["plant"], (1, 1, 0.6), 12)

# counter
box("counter_body", (0, 2.75, 0.5), (7.0, 0.8, 1.0), M["counter_wood"], 0.01)
for i in range(36):  # fluted front
    cyl("flute", (-3.4 + i * 0.194, 2.33, 0.5), 0.045, 0.96, M["counter_wood"], verts=16)
box("counter_top", (0, 2.72, 1.03), (7.2, 0.95, 0.06), M["marble"], 0.01)
CT = 1.06  # counter top height

# espresso machine
MX = 0.85
box("mach_body", (MX, 2.85, CT + 0.32), (1.05, 0.5, 0.62), M["chrome"], 0.03)
box("mach_side_l", (MX - 0.535, 2.85, CT + 0.32), (0.02, 0.5, 0.62), M["copper"])
box("mach_side_r", (MX + 0.535, 2.85, CT + 0.32), (0.02, 0.5, 0.62), M["copper"])
box("mach_top", (MX, 2.85, CT + 0.65), (1.0, 0.45, 0.04), M["copper"], 0.01)
box("drip_tray", (MX, 2.5, CT + 0.03), (0.95, 0.22, 0.04), M["chrome"], 0.005)
for gx in (MX - 0.25, MX + 0.25):
    cyl("group", (gx, 2.52, CT + 0.27), 0.05, 0.1, M["chrome"])
    cyl("gauge", (gx, 2.595, CT + 0.48), 0.05, 0.01, M["gauge"], rot=(math.radians(90), 0, 0))
    cyl("gauge_rim", (gx, 2.598, CT + 0.48), 0.055, 0.008, M["copper"], rot=(math.radians(90), 0, 0))
pf = bpy.data.objects.new("portafilter", None); sc.collection.objects.link(pf); pf.location = (MX - 0.25, 2.5, CT + 0.2)
pb = cyl("pf_basket", (MX - 0.25, 2.5, CT + 0.2), 0.047, 0.035, M["chrome"]); parent(pb, pf)
ph = cyl("pf_handle", (MX - 0.25, 2.36, CT + 0.19), 0.016, 0.2, M["counter_wood"], rot=(math.radians(80), 0, 0)); parent(ph, pf)
pf2 = cyl("pf2_basket", (MX + 0.25, 2.5, CT + 0.2), 0.047, 0.035, M["chrome"])
cyl("pf2_handle", (MX + 0.25, 2.36, CT + 0.19), 0.016, 0.2, M["counter_wood"], rot=(math.radians(80), 0, 0))
wand = cyl("steam_wand", (MX + 0.6, 2.55, CT + 0.25), 0.008, 0.36, M["chrome"], rot=(math.radians(-12), 0, 0))
# espresso streams + cup under group 1
pour_cup = make_cup("pour_cup", (MX - 0.25, 2.5, CT + 0.05), latte=False)
streams = []
for dx in (-0.008, 0.008):
    s = cyl("stream", (MX - 0.25 + dx, 2.5, CT + 0.14), 0.0025, 0.08, M["coffee"], verts=12)
    streams.append(s)

# hero cup + beans pile + grinder
hero = make_cup("hero_cup", (-0.7, 2.45, CT))
box("grinder_base", (-1.6, 2.8, CT + 0.15), (0.22, 0.25, 0.3), M["black"], 0.02)
cyl("grinder_hopper", (-1.6, 2.8, CT + 0.43), 0.09, 0.26, M["glass"], verts=32)
cyl("grinder_beans", (-1.6, 2.8, CT + 0.39), 0.08, 0.16, M["bean"], verts=24)

bean_mesh = None
def bean(loc, rot=None):
    global bean_mesh
    if bean_mesh is None:
        o = sphere("bean_src", loc, 0.012, M["bean"], (1.0, 0.72, 0.5), 12)
        bpy.ops.object.transform_apply(scale=True)
        bean_mesh = o.data
        return o
    o = bpy.data.objects.new("bean", bean_mesh); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = rot or (R.uniform(0, 6), R.uniform(0, 6), R.uniform(0, 6))
    return o

pile = [bean((-0.25 + R.gauss(0, 0.07), 2.35 + R.gauss(0, 0.05), CT + 0.008 + abs(R.gauss(0, 0.01)))) for _ in range(70)]
flyers = [bean((0, 0, -5)) for _ in range(90)]  # repositioned per shot

# back shelves with jars + cups
for z in (1.55, 2.0, 2.45):
    box("shelf", (0, 4.85, z), (5.0, 0.3, 0.04), M["counter_wood"])
    for i in range(9):
        x = -2.2 + i * 0.55
        if (i + int(z * 10)) % 3 == 0:
            for k in range(3):
                cyl("stack_cup", (x, 4.85, z + 0.04 + k * 0.06), 0.04, 0.055, M["ceramic"], verts=24)
        else:
            cyl("jar", (x, 4.85, z + 0.13), 0.08, 0.22, M["glass"], verts=32)
            cyl("jar_beans", (x, 4.85, z + 0.1), 0.07, 0.15, M["bean"], verts=24)
            cyl("jar_lid", (x, 4.85, z + 0.245), 0.082, 0.02, M["copper"], verts=32)

# neon sign on the brick
box("sign_board", (0, 4.97, 3.05), (2.9, 0.04, 0.55), M["black"])
bpy.ops.object.text_add(location=(0, 4.93, 2.93), rotation=(math.radians(90), 0, 0))
sign = bpy.context.object; sign.name = "neon_sign"
sign.data.body = "EMBER ROAST"
fpath = os.path.join(HERE, "..", "demo", "fonts", "BebasNeue-Regular.ttf")
sign.data.font = bpy.data.fonts.load(fpath)
sign.data.size = 0.3; sign.data.extrude = 0.008; sign.data.bevel_depth = 0.006; sign.data.align_x = "CENTER"
sign.data.materials.append(M["neon"])
bpy.ops.object.light_add(type="AREA", location=(0, 4.6, 3.05)); signlight = bpy.context.object
signlight.data.size = 2.6; signlight.data.color = (1, 0.45, 0.15); signlight.rotation_euler = (math.radians(-90), 0, 0)

# pendant lamps over the counter
lamps = []
for x in (-2.4, -0.8, 0.8, 2.4):
    root = bpy.data.objects.new("lamp", None); sc.collection.objects.link(root); root.location = (x, 2.0, 3.6)
    cord = cyl("cord", (x, 2.0, 3.12), 0.004, 0.96, M["black"], verts=8); parent(cord, root)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.2, radius2=0.04, depth=0.22, location=(x, 2.0, 2.55), end_fill_type="NOTHING")
    sh = bpy.context.object; sh.data.materials.append(M["copper"]); bpy.ops.object.shade_smooth()
    sd = sh.modifiers.new("s", "SOLIDIFY"); sd.thickness = 0.004; parent(sh, root)
    bl = sphere("bulb", (x, 2.0, 2.47), 0.045, M["bulb"], seg=16); parent(bl, root)
    bpy.ops.object.light_add(type="SPOT", location=(x, 2.0, 2.45)); lt = bpy.context.object
    lt.data.spot_size = math.radians(80); lt.data.spot_blend = 0.6; lt.data.color = (1, 0.72, 0.42)
    lt.data.shadow_soft_size = 0.05; parent(lt, root)
    lamps.append((root, lt))

# tables + chairs
def chair(x, y, rot):
    root = bpy.data.objects.new("chair", None); sc.collection.objects.link(root); root.location = (x, y, 0)
    parts = [cyl("seat", (x, y, 0.46), 0.2, 0.04, M["counter_wood"])]
    for a in range(4):
        ang = a * math.pi / 2 + math.pi / 4
        parts.append(cyl("leg", (x + 0.14 * math.cos(ang), y + 0.14 * math.sin(ang), 0.23), 0.014, 0.46, M["black"], verts=12))
    bx, by = x + 0.2 * math.cos(rot), y + 0.2 * math.sin(rot)
    parts.append(box("back", (bx, by, 0.75), (0.05, 0.36, 0.22), M["counter_wood"], 0.01))
    parts[-1].rotation_euler[2] = rot
    for p in parts:
        parent(p, root)

for (x, y) in ((-3.6, -1.6), (0.0, -2.4), (3.4, -1.2), (-1.8, -4.0), (2.2, -4.2)):
    cyl("table_top", (x, y, 0.76), 0.42, 0.04, M["marble"], verts=48)
    cyl("table_leg", (x, y, 0.38), 0.03, 0.74, M["black"], verts=16)
    cyl("table_foot", (x, y, 0.015), 0.22, 0.03, M["black"], verts=32)
    chair(x - 0.62, y, 0.0); chair(x + 0.62, y, math.pi)
table_cup = make_cup("table_cup", (0.12, -2.35, 0.78))

# atmosphere: room haze + steam over the hero cup
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.8)); haze = bpy.context.object; haze.scale = (14, 11.5, 3.6)
HZ = bpy.data.materials.new("haze"); HZ.use_nodes = True
hn = HZ.node_tree; hn.nodes.remove(hn.nodes["Principled BSDF"])
hv = hn.nodes.new("ShaderNodeVolumePrincipled"); hn.links.new(hv.outputs["Volume"], hn.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(HZ)
haze.hide_render = FILM == "energetic"  # bright morning: no volume, glow added in post


def steam_volume(name, loc, h=0.35, r=0.06):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=r, depth=h, location=(loc[0], loc[1], loc[2] + h / 2))
    o = bpy.context.object; o.name = name
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.remove(nt.nodes["Principled BSDF"])
    v = nt.nodes.new("ShaderNodeVolumePrincipled"); v.inputs["Color"].default_value = (1, 1, 1, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.name = "steam_map"
    mp.inputs["Scale"].default_value = (9, 9, 4)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Detail"].default_value = 6; nz.inputs["Scale"].default_value = 1.5
    nz.inputs["Distortion"].default_value = 1.2
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    fade = nt.nodes.new("ShaderNodeMapRange"); fade.inputs["From Min"].default_value = -1; fade.inputs["From Max"].default_value = 1
    fade.inputs["To Min"].default_value = 1; fade.inputs["To Max"].default_value = 0
    rad = nt.nodes.new("ShaderNodeVectorMath"); rad.operation = "LENGTH"
    vec_xy = nt.nodes.new("ShaderNodeCombineXYZ")
    rfade = nt.nodes.new("ShaderNodeMapRange"); rfade.inputs["From Min"].default_value = 0.2; rfade.inputs["From Max"].default_value = 1.0
    rfade.inputs["To Min"].default_value = 1; rfade.inputs["To Max"].default_value = 0
    thr = nt.nodes.new("ShaderNodeMapRange"); thr.inputs["From Min"].default_value = 0.5; thr.inputs["From Max"].default_value = 0.75
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul2 = nt.nodes.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"
    dens = nt.nodes.new("ShaderNodeMath"); dens.operation = "MULTIPLY"; dens.name = "steam_density"; dens.inputs[1].default_value = 6.0
    L = nt.links
    L.new(tc.outputs["Object"], mp.inputs["Vector"]); L.new(mp.outputs["Vector"], nz.inputs["Vector"])
    L.new(tc.outputs["Object"], sep.inputs["Vector"])
    L.new(sep.outputs["Z"], fade.inputs["Value"])
    L.new(sep.outputs["X"], vec_xy.inputs["X"]); L.new(sep.outputs["Y"], vec_xy.inputs["Y"])
    L.new(vec_xy.outputs["Vector"], rad.inputs[0]); L.new(rad.outputs["Value"], rfade.inputs["Value"])
    L.new(nz.outputs["Fac"], thr.inputs["Value"])
    L.new(thr.outputs["Result"], mul.inputs[0]); L.new(fade.outputs["Result"], mul.inputs[1])
    L.new(mul.outputs["Value"], mul2.inputs[0]); L.new(rfade.outputs["Result"], mul2.inputs[1])
    L.new(mul2.outputs["Value"], dens.inputs[0]); L.new(dens.outputs["Value"], v.inputs["Density"])
    L.new(v.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    o.data.materials.append(m)
    return o, m


steam_hero, STEAM_HERO = steam_volume("steam_hero", (-0.7, 2.45, CT + 0.07))
steam_wand, STEAM_WAND = steam_volume("steam_blast", (MX + 0.64, 2.5, CT + 0.02), h=0.5, r=0.12)
STEAM_WAND.node_tree.nodes["steam_density"].inputs[1].default_value = 0.0
steam_hero.hide_render = True; steam_wand.hide_render = True  # steam is composited in post

# fill lights
bpy.ops.object.light_add(type="AREA", location=(0, -1.0, 3.5)); fill = bpy.context.object
fill.data.size = 8; fill.data.color = (1, 0.85, 0.7)
bpy.ops.object.light_add(type="SUN", location=(-10, -1, 6)); sun = bpy.context.object
sun.rotation_euler = (Vector((0, 0.5, 0)) - Vector((-10, -1.5, 5))).to_track_quat("-Z", "Y").to_euler()
sun.data.color = (1, 0.82, 0.6); sun.data.angle = math.radians(1.5)

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
WBG = world.node_tree.nodes["Background"]


# ---------------- moods ----------------
def outside_shader(kind):
    nt = OUT_M.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    if kind == "day":
        ramp.color_ramp.elements[0].color = (1.0, 0.85, 0.65, 1); ramp.color_ramp.elements[1].color = (0.55, 0.75, 1.0, 1)
        nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = 6.0
    else:  # rainy night: deep blue gradient + animated rain streaks
        ramp.color_ramp.elements[0].color = (0.01, 0.02, 0.05, 1); ramp.color_ramp.elements[1].color = (0.05, 0.09, 0.16, 1)
        nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
        mp = nt.nodes.new("ShaderNodeMapping"); mp.name = "rain_map"; mp.inputs["Scale"].default_value = (60, 3, 1)
        wv = nt.nodes.new("ShaderNodeTexNoise"); wv.inputs["Scale"].default_value = 4; wv.inputs["Detail"].default_value = 2
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
        thr = nt.nodes.new("ShaderNodeMapRange"); thr.inputs["From Min"].default_value = 0.62; thr.inputs["From Max"].default_value = 0.72
        nt.links.new(wv.outputs["Fac"], thr.inputs["Value"])
        # street-light bokeh blobs
        vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 5
        nt.links.new(tc.outputs["Generated"], vo.inputs["Vector"])
        bk = nt.nodes.new("ShaderNodeMapRange"); bk.inputs["From Min"].default_value = 0.12; bk.inputs["From Max"].default_value = 0.02
        nt.links.new(vo.outputs["Distance"], bk.inputs["Value"])
        bkc = nt.nodes.new("ShaderNodeMixRGB"); bkc.blend_type = "ADD"; bkc.inputs["Fac"].default_value = 1
        bkc.inputs["Color2"].default_value = (0, 0, 0, 1)
        warm = nt.nodes.new("ShaderNodeMixRGB"); warm.inputs["Color1"].default_value = (0, 0, 0, 1)
        warm.inputs["Color2"].default_value = (1.0, 0.55, 0.2, 1); nt.links.new(bk.outputs["Result"], warm.inputs["Fac"])
        add1 = nt.nodes.new("ShaderNodeMixRGB"); add1.blend_type = "ADD"; add1.inputs["Fac"].default_value = 1
        nt.links.new(ramp.outputs["Color"], add1.inputs["Color1"]); nt.links.new(warm.outputs["Color"], add1.inputs["Color2"])
        rainc = nt.nodes.new("ShaderNodeMixRGB"); rainc.inputs["Color2"].default_value = (0.4, 0.5, 0.65, 1)
        nt.links.new(thr.outputs["Result"], rainc.inputs["Fac"]); nt.links.new(add1.outputs["Color"], rainc.inputs["Color1"])
        nt.links.new(rainc.outputs["Color"], em.inputs["Color"]); em.inputs["Strength"].default_value = 1.6
    nt.links.new(em.outputs["Emission"], o.inputs["Surface"])


def glass_drops(on):
    n, l, b = nodes(M["glass"])
    if not on:
        return
    tc = n.new("ShaderNodeTexCoord"); vo = n.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 90
    vo.feature = "SMOOTH_F1" if hasattr(vo, "feature") else vo.feature
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35
    l.new(tc.outputs["Object"], vo.inputs["Vector"]); l.new(vo.outputs["Distance"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.08


if FILM == "energetic":
    outside_shader("day"); glass_drops(False)
    sun.data.energy = 9.0
    fill.data.energy = 450
    for _, lt in lamps: lt.data.energy = 60
    signlight.data.energy = 120
    M["neon"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 18
    hv.inputs["Density"].default_value = 0.0025; hv.inputs["Color"].default_value = (1, 0.9, 0.8, 1)
    WBG.inputs["Color"].default_value = (0.25, 0.2, 0.16, 1); WBG.inputs["Strength"].default_value = 0.35
else:
    outside_shader("night"); glass_drops(True)
    sun.data.energy = 0.0
    fill.data.energy = 60; fill.data.color = (0.6, 0.7, 1.0)
    for _, lt in lamps: lt.data.energy = 90
    signlight.data.energy = 160
    M["neon"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 22
    hv.inputs["Density"].default_value = 0.012; hv.inputs["Color"].default_value = (1, 0.85, 0.7, 1)
    WBG.inputs["Color"].default_value = (0.02, 0.03, 0.05, 1); WBG.inputs["Strength"].default_value = 0.5


# ---------------- camera rig ----------------
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
tgt = bpy.data.objects.new("target", None); sc.collection.objects.link(tgt)
tc_ = cam.constraints.new("TRACK_TO"); tc_.target = tgt; tc_.track_axis = "TRACK_NEGATIVE_Z"; tc_.up_axis = "UP_Y"
cam.data.dof.use_dof = True; cam.data.dof.focus_object = tgt
cam.data.sensor_width = 36


def ease(u, kind="io"):
    u = max(0.0, min(1.0, u))
    if kind == "lin": return u
    if kind == "out": return 1 - (1 - u) ** 3
    if kind == "in": return u ** 3
    if kind == "expo": return 1 - 2 ** (-10 * u) if u < 1 else 1
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u


def path(keys, u):
    """piecewise-linear through [(u, value), ...]"""
    for (u0, a), (u1, b) in zip(keys, keys[1:]):
        if u <= u1:
            return lerp(a, b, (u - u0) / max(u1 - u0, 1e-6))
    return keys[-1][1]


def keyall(f):
    cam.keyframe_insert("location", frame=f); cam.data.keyframe_insert("lens", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
    tgt.keyframe_insert("location", frame=f)


ANIMATED = []
BASES = {}
def remember(*objs):
    for o in objs:
        BASES[o.name] = (tuple(o.location), tuple(o.rotation_euler), tuple(o.scale))
remember(pf, hero, pour_cup, table_cup, *streams, *flyers, *[r for r, _ in lamps])


def reset():
    for o in [cam, tgt, *ANIMATED]:
        o.animation_data_clear()
    for name, (l, r, s) in BASES.items():
        o = bpy.data.objects[name]; o.location, o.rotation_euler, o.scale = l, r, s
    for f in flyers:
        f.location = (0, 0, -5)
    for m in (M["neon"], STEAM_HERO, STEAM_WAND, OUT_M, M["glass"]):
        if m.node_tree.animation_data:
            m.node_tree.animation_data_clear()
    ANIMATED.clear()
    cam.rotation_euler = (0, 0, 0)


def key_socket(sock, val, f, index=None):
    if index is None:
        sock.default_value = val; sock.keyframe_insert("default_value", frame=f)
    else:
        sock.default_value[index] = val; sock.keyframe_insert("default_value", index=index, frame=f)


def animate_ambient(n, speed):
    """steam drift + rain motion, every frame"""
    mh = STEAM_HERO.node_tree.nodes["steam_map"]; mw = STEAM_WAND.node_tree.nodes["steam_map"]
    rain = OUT_M.node_tree.nodes.get("rain_map")
    for f in range(1, n + 1):
        key_socket(mh.inputs["Location"], -f * 0.06 * speed, f, 2)
        key_socket(mw.inputs["Location"], -f * 0.25, f, 2)
        if rain:
            key_socket(rain.inputs["Location"], f * 0.35 * speed, f, 1)


def shot_camera(n, loc_keys, tgt_keys, lens_keys, fstop, ease_kind="io", shake=0.0, roll_keys=None, seed=1):
    rs = random.Random(seed)
    cam.data.dof.aperture_fstop = fstop
    ph = [rs.uniform(0, 6) for _ in range(6)]
    for f in range(1, n + 1):
        u = ease((f - 1) / max(n - 1, 1), ease_kind)
        cam.location = path(loc_keys, u)
        if shake:
            cam.location = tuple(c + shake * math.sin(f * (0.9 + i * 0.37) + ph[i]) for i, c in enumerate(cam.location))
        tgt.location = path(tgt_keys, u)
        cam.data.lens = path(lens_keys, u)
        cam.rotation_euler = (0, 0, math.radians(path(roll_keys, u)) if roll_keys else 0)
        keyall(f)


# ---------------- shot library ----------------
P = dict(hero=(-0.7, 2.45, CT + 0.05), group=(MX - 0.25, 2.5, CT + 0.15), wand=(MX + 0.62, 2.52, CT + 0.2),
         sign=(0, 4.93, 3.03), machine=(MX, 2.7, CT + 0.35), table=(0.12, -2.35, 0.82))


def s_neon_on(n):
    shot_camera(n, [(0, (0.3, 1.2, 2.6)), (1, (0.2, 2.6, 2.9))], [(0, P["sign"]), (1, P["sign"])], [(0, 28), (1, 45)], 2.8, "expo")
    b = M["neon"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f in range(1, n + 1):
        on = f > 6 or f in (2, 4)
        key_socket(b, 18 if on else 0.3, f)
    for f in range(1, n + 1):
        signlight.data.energy = 120 if (f > 6 or f in (2, 4)) else 0; signlight.data.keyframe_insert("energy", frame=f)
    ANIMATED.append(signlight)


def s_beans_burst(n):
    c = (-0.25, 2.35, CT)
    shot_camera(n, [(0, (-0.05, 1.75, CT + 0.06)), (1, (-0.1, 1.95, CT + 0.08))], [(0, (-0.25, 2.35, CT + 0.08)), (1, (-0.25, 2.35, CT + 0.1))], [(0, 40), (1, 50)], 2.0, "lin")
    rs = random.Random(3)
    for b in flyers[:70]:
        v = (rs.gauss(0, 0.25), rs.gauss(-0.35, 0.2), rs.uniform(0.7, 1.4)); spin = [rs.uniform(-12, 12) for _ in range(3)]
        delay = rs.uniform(0, 4)
        for f in range(1, n + 1):
            t = max(0, (f - 1 - delay)) / 12.0 * 0.4  # slow-motion
            z = c[2] + 0.02 + v[2] * t - 4.9 * t * t
            b.location = (c[0] + v[0] * t, c[1] + v[1] * t, max(z, CT + 0.006))
            b.rotation_euler = tuple(s * t for s in spin)
            b.keyframe_insert("location", frame=f); b.keyframe_insert("rotation_euler", frame=f)
        ANIMATED.append(b)


def s_portafilter(n):
    shot_camera(n, [(0, (MX - 0.55, 2.05, CT + 0.12)), (1, (MX - 0.5, 2.1, CT + 0.15))], [(0, P["group"]), (1, P["group"])], [(0, 55), (1, 60)], 2.2, "out", 0.002)
    base = BASES[pf.name]
    for f in range(1, n + 1):
        u = ease((f - 1) / 6, "out")
        pf.location = (base[0][0], base[0][1], base[0][2] - 0.06 * (1 - u))
        pf.rotation_euler = (0, 0, math.radians(-40 * (1 - u)))
        pf.keyframe_insert("location", frame=f); pf.keyframe_insert("rotation_euler", frame=f)
    ANIMATED.append(pf)


def s_pour(n):
    g = P["group"]
    shot_camera(n, [(0, (g[0] - 0.3, 2.05, CT + 0.16)), (1, (g[0] + 0.25, 2.05, CT + 0.17))], [(0, (g[0], 2.5, CT + 0.14)), (1, (g[0], 2.5, CT + 0.14))], [(0, 42), (1, 42)], 2.8, "lin", 0.001)
    for s in streams:
        b = BASES[s.name]
        for f in range(1, n + 1):
            u = min(1, f / 5)
            s.scale = (1, 1, max(u, 0.01)); s.location = (b[0][0], b[0][1], CT + 0.18 - 0.04 * u)
            s.keyframe_insert("scale", frame=f); s.keyframe_insert("location", frame=f)
        ANIMATED.append(s)


def s_whip(n):
    shot_camera(n, [(0, (0.2, 1.3, 1.5)), (1, (0.4, 1.3, 1.5))], [(0, P["group"]), (1, P["wand"])], [(0, 32), (1, 32)], 4.0, "in")


def s_steam(n):
    w = P["wand"]
    shot_camera(n, [(0, (w[0] - 0.4, 1.95, CT + 0.05)), (1, (w[0] - 0.3, 2.0, CT + 0.08))], [(0, (w[0], 2.5, CT + 0.25)), (1, (w[0], 2.5, CT + 0.3))], [(0, 35), (1, 40)], 2.8, "out", 0.003)
    d = STEAM_WAND.node_tree.nodes["steam_density"].inputs[1]
    for f in range(1, n + 1):
        key_socket(d, 9.0 * min(1, f / 3), f)


def s_slide(n):
    shot_camera(n, [(0, (1.8, 1.85, CT + 0.12)), (1, (-0.4, 1.85, CT + 0.12))], [(0, (2.2, 2.45, CT + 0.05)), (1, P["hero"])], [(0, 35), (1, 40)], 2.5, "out")
    b = BASES[hero.name]
    for f in range(1, n + 1):
        u = ease((f - 1) / (n - 1), "out")
        hero.location = (lerp(b[0][0] + 2.9, b[0][0], u), b[0][1], b[0][2]); hero.keyframe_insert("location", frame=f)
    ANIMATED.append(hero)


def s_latte_top(n):
    h = P["hero"]
    shot_camera(n, [(0, (h[0], h[1] - 0.001, h[2] + 0.55)), (1, (h[0], h[1] - 0.001, h[2] + 0.25))], [(0, (h[0], h[1], CT + 0.07)), (1, (h[0], h[1], CT + 0.07))], [(0, 50), (1, 50)], 4.0, "out", roll_keys=[(0, 0), (1, 120)])


def s_fpv(n):
    keys = [(0, (-6.5, -1.0, 1.6)), (0.3, (-3.0, -2.0, 1.2)), (0.55, (-0.5, -0.8, 1.9)), (0.8, (0.0, 1.2, 2.1)), (1, (-0.45, 2.05, CT + 0.2))]
    tg = [(0, (-3.0, -1.6, 1.0)), (0.3, (0.0, -1.0, 1.2)), (0.55, (0.0, 2.0, 2.0)), (0.8, (-0.5, 2.6, CT + 0.2)), (1, P["hero"])]
    shot_camera(n, keys, tg, [(0, 18), (1, 26)], 5.6, "io", 0.01, roll_keys=[(0, 0), (0.3, -12), (0.55, 10), (0.8, -6), (1, 0)])


def s_lamps(n):
    shot_camera(n, [(0, (-1.6, 1.2, 1.3)), (1, (-1.2, 1.25, 1.3))], [(0, (0, 2.0, 2.5)), (1, (0.3, 2.0, 2.5))], [(0, 24), (1, 22)], 4.0, "lin", 0.004)
    for i, (root, _) in enumerate(lamps):
        for f in range(1, n + 1):
            root.rotation_euler = (math.radians(9 * math.sin(f * 0.7 + i)), math.radians(6 * math.cos(f * 0.6 + i)), 0)
            root.keyframe_insert("rotation_euler", frame=f)
        ANIMATED.append(root)


def s_shelves(n):
    shot_camera(n, [(0, (-1.6, 4.05, 2.05)), (1, (0.6, 4.05, 2.05))], [(0, (-0.9, 4.85, 2.05)), (1, (1.3, 4.85, 2.05))], [(0, 35), (1, 35)], 2.8, "out")


def s_crash(n):
    shot_camera(n, [(0, (0.5, -3.5, 1.7)), (1, (0.6, 0.6, 1.5))], [(0, P["machine"]), (1, P["machine"])], [(0, 20), (1, 55)], 4.0, "expo")


def s_beans_rain(n):
    c = (-0.25, 2.4, CT)
    shot_camera(n, [(0, (c[0], c[1] - 0.001, CT + 0.7)), (1, (c[0], c[1] - 0.001, CT + 0.6))], [(0, c), (1, c)], [(0, 45), (1, 45)], 5.6, "lin", roll_keys=[(0, 15), (1, 15)])
    rs = random.Random(8)
    for i, b in enumerate(flyers[:80]):
        land = (c[0] + rs.gauss(0, 0.14), c[1] + rs.gauss(0, 0.1), CT + 0.007); t0 = rs.uniform(0, n - 3)
        for f in range(1, n + 1):
            on = f >= t0
            b.location = land if on else (0, 0, -5); b.keyframe_insert("location", frame=f)
        ANIMATED.append(b)


def s_orbit(n):
    h = P["hero"]
    keys = [(i / 8, (h[0] + 0.45 * math.cos(math.radians(-150 + i * 22)), h[1] + 0.45 * math.sin(math.radians(-150 + i * 22)), CT + 0.18)) for i in range(9)]
    shot_camera(n, keys, [(0, (h[0], h[1], CT + 0.06)), (1, (h[0], h[1], CT + 0.06))], [(0, 45), (1, 45)], 2.0, "io")


def s_wide(n, calm=False):
    if calm:
        shot_camera(n, [(0, (5.6, -5.0, 1.55)), (1, (4.9, -4.2, 1.5))], [(0, (-0.5, 2.2, 1.4)), (1, (-0.6, 2.3, 1.4))], [(0, 22), (1, 24)], 8.0, "lin", 0.002)
    else:
        shot_camera(n, [(0, (5.8, -5.2, 2.6)), (1, (3.6, -2.8, 1.6))], [(0, (-1.0, 2.0, 1.3)), (1, (-0.5, 2.3, 1.3))], [(0, 18), (1, 24)], 8.0, "io", 0.006)


def s_sign_final(n, calm=False):
    shot_camera(n, [(0, (0.0, 0.8, 2.2)), (1, (0.0, 2.2, 2.6))], [(0, P["sign"]), (1, P["sign"])], [(0, 30), (1, 34)], 4.0, "out" if not calm else "lin")


# calm-only shots
def c_window(n):
    shot_camera(n, [(0, (-5.6, -0.4, 1.75)), (1, (-6.2, -0.7, 1.8))], [(0, (-7.0, -1.2, 1.75)), (1, (-7.0, -1.2, 1.78))], [(0, 35), (1, 40)], 1.8, "lin", 0.002)


def c_pendant(n):
    x = -0.8
    shot_camera(n, [(0, (x - 0.9, 1.0, 2.3)), (1, (x - 0.8, 1.05, 1.9))], [(0, (x, 2.0, 2.45)), (1, P["hero"])], [(0, 40), (1, 45)], 2.0, "io", 0.001)


def c_steam(n):
    h = P["hero"]
    shot_camera(n, [(0, (h[0] - 0.08, h[1] - 0.7, CT + 0.13)), (1, (h[0] - 0.04, h[1] - 0.6, CT + 0.13))], [(0, (h[0], h[1], CT + 0.1)), (1, (h[0], h[1], CT + 0.1))], [(0, 70), (1, 70)], 1.8, "lin", 0.0008)


def c_counter_dolly(n):
    shot_camera(n, [(0, (-2.6, 1.55, CT + 0.25)), (1, (1.2, 1.55, CT + 0.25))], [(0, (-1.8, 2.6, CT + 0.25)), (1, (2.0, 2.6, CT + 0.3))], [(0, 35), (1, 35)], 2.2, "lin", 0.0015)


def c_rack(n):
    t = P["table"]
    cam.data.dof.focus_object = None
    shot_camera(n, [(0, (0.55, -2.95, 0.98)), (1, (0.5, -2.9, 0.98))], [(0, (t[0], t[1], 0.84)), (1, (t[0] - 0.1, t[1], 0.86))], [(0, 60), (1, 60)], 1.6, "lin", 0.001)
    for f in range(1, n + 1):
        u = ease((f - 1 - n * 0.35) / (n * 0.4), "io")
        cam.data.dof.focus_distance = lerp(0.75, 7.5, u); cam.data.dof.keyframe_insert("focus_distance", frame=f)


SHOTS = {
    "energetic": [("e01_neon", s_neon_on, 12), ("e02_beans", s_beans_burst, 24), ("e03_porta", s_portafilter, 12),
                  ("e04_pour", s_pour, 18), ("e05_whip", s_whip, 6), ("e06_steam", s_steam, 12), ("e07_slide", s_slide, 18),
                  ("e08_latte", s_latte_top, 12), ("e09_fpv", s_fpv, 48), ("e10_lamps", s_lamps, 12), ("e11_shelves", s_shelves, 12),
                  ("e12_crash", s_crash, 12), ("e13_rain", s_beans_rain, 18), ("e14_orbit", s_orbit, 30),
                  ("e15_wide", s_wide, 30), ("e16_sign", s_sign_final, 36)],
    "calm": [("c01_window", c_window, 40), ("c02_pendant", c_pendant, 32), ("c03_steam", c_steam, 40),
             ("c04_dolly", c_counter_dolly, 40), ("c05_rack", c_rack, 32), ("c06_wide", lambda n: s_wide(n, True), 32),
             ("c07_sign", lambda n: s_sign_final(n, True), 24)],
}

import time, json
from bpy_extras.object_utils import world_to_camera_view
T0 = time.time()
TRACK = {"hero_top": None, "pour_top": None, "wand_tip": None, "table_top": None}
CUR = {"name": None, "pts": {}}
def track_points():
    pts = {"hero_top": hero.location + Vector((0, 0, 0.075)), "pour_top": pour_cup.location + Vector((0, 0, 0.075)),
           "wand_tip": Vector((MX + 0.64, 2.5, CT + 0.08)), "table_top": table_cup.location + Vector((0, 0, 0.075))}
    out = {}
    for k, p in pts.items():
        v = world_to_camera_view(sc, cam, p)
        out[k] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
    return out
def on_frame(scene, *a):
    CUR["pts"][scene.frame_current] = track_points()
    print(f"FRAME {scene.frame_current} {time.time() - T0:.0f}s", flush=True)
bpy.app.handlers.render_post.append(on_frame)

for name, fn, n in SHOTS[FILM]:
    if ONLY and ONLY != name:
        continue
    reset()
    cam.data.dof.focus_object = tgt
    fn(n)
    animate_ambient(n, 1.0 if FILM == "energetic" else 0.68)
    sc.frame_start, sc.frame_end = 1, (1 if TEST else n)
    if TEST:
        sc.frame_start = sc.frame_end = max(1, n // 2)
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    sc.render.filepath = d + "/"
    print("SHOT", name, n, flush=True)
    CUR["pts"] = {}
    bpy.ops.render.render(animation=True)
    json.dump({"fps": sc.render.fps, "n": n, "pts": CUR["pts"]}, open(os.path.join(d, "track.json"), "w"))
print("ALL DONE", f"{time.time() - T0:.0f}s", flush=True)

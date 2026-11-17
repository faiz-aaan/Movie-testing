"""Exploded-view teardown scenes (Blender, Eevee, CPU) for a vertical 9:16 film.

  blender -b -P teardown_scene.py -- hp|tv [test <t_seconds>]

hp : Nothing Headphone (1) style over-ear headphones. Cup rotates upright and explodes into
     a vertical stack along its axis, then reassembles.
tv : generic LED-LCD TV lying flat; layers fan upward, then collapse.

Frames -> renders/<name>/####.png at 12 fps (RIFE interpolates to 24 in post).
track.json -> per-frame screen position (0..1) of each labelled part, so labels can be pinned.

The geometry is an ILLUSTRATIVE model built from published layout knowledge, not a scan.
"""
import bpy, math, os, sys, json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WHAT = argv[0] if argv else "hp"
TEST_T = float(argv[2]) if len(argv) > 2 and argv[1] == "test" else None
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders", WHAT)
os.makedirs(OUT, exist_ok=True)
FPS = 12
DUR = {"hp": 14.9, "tv": 8.2}[WHAT]
NF = int(round(DUR * FPS))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.eevee.use_raytracing = False
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.fps = FPS
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.image_settings.file_format = "PNG"


# ---------- materials ----------
def T(rotation=False, scale=False):
    """apply rotation/scale into the mesh but KEEP the object location (default would bake it too)"""
    bpy.ops.object.transform_apply(location=False, rotation=rotation, scale=scale)


def mat(name, color, metal=0.0, rough=0.5, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


M = dict(
    white=mat("white", (0.80, 0.80, 0.78), 0, 0.32, **{"Coat Weight": 0.3}),
    foam=mat("foam", (0.015, 0.015, 0.016), 0, 0.75),
    alu=mat("alu", (0.82, 0.82, 0.85), 1, 0.25),
    gold=mat("gold", (1.0, 0.76, 0.3), 1, 0.28),
    pcb=mat("pcb", (0.02, 0.22, 0.10), 0, 0.4),
    chip=mat("chip", (0.025, 0.025, 0.03), 0.1, 0.3),
    batt=mat("batt", (0.72, 0.74, 0.78), 0.9, 0.3),
    magnet=mat("magnet", (0.09, 0.09, 0.10), 1, 0.3),
    nickel=mat("nickel", (0.78, 0.80, 0.82), 1, 0.2),
    mesh=mat("mesh", (0.04, 0.04, 0.045), 0, 0.6),
    red=mat("red", (0.9, 0.04, 0.03), 0, 0.3, **{"Emission Color": (1, 0.1, 0.05, 1), "Emission Strength": 2.5}),
    glass=mat("glass", (0.004, 0.005, 0.009), 0, 0.04),
    shell=mat("shell", (0.05, 0.05, 0.055), 0, 0.5),
    cover=mat("cover", (0.07, 0.07, 0.075), 0.2, 0.55),
    film=mat("film", (0.16, 0.16, 0.17), 0, 0.8),
    led=mat("led", (1, 1, 1), 0, 0.3, **{"Emission Color": (1, 0.95, 0.85, 1), "Emission Strength": 5}),
    speaker=mat("speaker", (0.03, 0.03, 0.035), 0.1, 0.5),
    stand=mat("stand", (0.5, 0.5, 0.52), 1, 0.3),
    floor=mat("floor", (0.02, 0.02, 0.022), 0.2, 0.25),
)


def box(name, loc, size, m, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size
    T(scale=True)
    if bevel:
        md = o.modifiers.new("bv", "BEVEL"); md.width = bevel; md.segments = 2
    o.data.materials.append(m)
    return o


def cyl_x(name, loc, r, depth, m, verts=64, fill="NGON", solid=0.0):
    """cylinder whose axis is world X"""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=(0, math.pi / 2, 0), end_fill_type=fill)
    o = bpy.context.object; o.name = name
    T(rotation=True)
    bpy.ops.object.shade_smooth()
    if solid:
        s = o.modifiers.new("s", "SOLIDIFY"); s.thickness = solid
    o.data.materials.append(m)
    return o


def cyl_z(name, loc, r, depth, m, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc)
    o = bpy.context.object; o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(m)
    return o


def adopt(child, parent):
    bpy.context.view_layer.update()
    mw = parent.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.copy()   # original matrix_world can be stale
    child.parent = parent
    child.matrix_parent_inverse = mw.inverted()


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None); sc.collection.objects.link(e); e.location = loc
    if parent:
        adopt(e, parent)
    return e


# ---------- studio ----------
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (1, 1, 3.0)
wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "Z"
wv.inputs["Scale"].default_value = 1.2; wv.inputs["Distortion"].default_value = 0.0
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.80; ramp.color_ramp.elements[0].color = (0.012, 0.014, 0.02, 1)
ramp.color_ramp.elements[1].position = 0.88; ramp.color_ramp.elements[1].color = (3.0, 3.0, 3.2, 1)
nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
lp_ = nt.nodes.new("ShaderNodeLightPath"); mixc = nt.nodes.new("ShaderNodeMixRGB")
mixc.inputs["Color2"].default_value = (0.010, 0.011, 0.016, 1)
nt.links.new(lp_.outputs["Is Camera Ray"], mixc.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], mixc.inputs["Color1"])
nt.links.new(mixc.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.9

for nm, loc, e_, sz, col in (("key", (2.5, -3.0, 4.0), 700, 3.0, (1.0, 0.95, 0.9)), ("rim", (-3.0, 2.5, 3.0), 500, 3.0, (0.6, 0.75, 1.0)),
                             ("top", (0, 0, 5.0), 300, 4.0, (1, 1, 1))):
    bpy.ops.object.light_add(type="AREA", location=loc)
    l = bpy.context.object; l.name = nm; l.data.energy = e_; l.data.size = sz; l.data.color = col
    if WHAT == "tv" and nm == "top": l.data.energy = 90          # flat white layers blow out under a strong top light
    l.rotation_euler = (Vector((0, 0, 0)) - l.location).to_track_quat("-Z", "Y").to_euler()

ANCH = {}      # label name -> (object, local offset)
ANIM = []      # callables(t)


# =====================================================================
# HEADPHONES
# =====================================================================
if WHAT == "hp":
    RIG = empty("RIG")
    CX = 0.85

    # headband: upper half torus in the XZ plane + black pad
    def band(name, major, minor, ysc, m, keep_x=None):
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=96, minor_segments=20, rotation=(math.pi / 2, 0, 0))
        o = bpy.context.object; o.name = name
        T(rotation=True)
        import bmesh
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
        if keep_x:
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if abs(v.co.x) > keep_x], context="VERTS")
        bm.to_mesh(o.data); bm.free()
        o.scale = (1, ysc, 1); T(scale=True, rotation=True)
        bpy.ops.object.shade_smooth()
        o.data.materials.append(m)
        return o

    BAND = band("headband", 0.86, 0.045, 2.4, M["white"]); adopt(BAND, RIG)
    PAD = band("bandpad", 0.80, 0.035, 2.8, M["foam"], keep_x=0.5); adopt(PAD, BAND)
    # yokes (cup hangers)
    YOKES = []
    for s in (1, -1):
        y = cyl_z("yoke", (s * CX, 0, 0.30), 0.045, 0.62, M["alu"]); adopt(y, BAND); YOKES.append(y)

    # ---- right cup (full detail) ----
    RG = empty("RIGHT_CUP", (CX, 0, 0), RIG)
    PARTS = {}

    def part(name, o, base_lx, final_lx):
        adopt(o, RG)
        PARTS[name] = dict(obj=o, base=base_lx, final=final_lx, y=o.location.y, z=o.location.z)
        return o

    def rx(lx): return CX + lx        # world x of a local x on the right cup

    plate = cyl_x("plate", (rx(0.30), 0, 0), 0.46, 0.05, M["white"])
    part("plate", plate, 0.30, 1.70)
    dot = cyl_x("reddot", (rx(0.33), 0.22, 0.20), 0.025, 0.012, M["red"], 24); adopt(dot, plate)
    roller = cyl_z("roller", (rx(0.345), -0.10, 0.27), 0.055, 0.10, M["alu"], 32); roller.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.view_layer.objects.active = roller; T(rotation=True); adopt(roller, plate)
    paddle = box("paddle", (rx(0.345), 0.10, -0.20), (0.035, 0.09, 0.22), M["alu"], 0.012); adopt(paddle, plate)
    button = cyl_x("button", (rx(0.34), -0.28, -0.10), 0.04, 0.03, M["red"], 24); adopt(button, plate)

    housing = cyl_x("housing", (rx(0.17), 0, 0), 0.46, 0.20, M["white"], 64, "NOTHING", solid=0.02)
    part("housing", housing, 0.17, 1.25)
    for i, (my, mz) in enumerate(((0.38, 0.22), (-0.38, -0.24))):
        mic = cyl_x(f"mic{i}", (rx(0.17), my, mz), 0.022, 0.03, M["gold"], 24); adopt(mic, housing)
    usb = box("usb", (rx(0.17), 0.0, -0.46), (0.07, 0.11, 0.05), M["alu"], 0.01); adopt(usb, housing)

    board = cyl_x("mainboard", (rx(0.12), 0, 0), 0.34, 0.018, M["pcb"])
    part("mainboard", board, 0.12, 0.85)
    for nm, (cy, cz), sz in (("soc", (0.05, 0.06), (0.14, 0.14)), ("flash", (-0.12, 0.10), (0.07, 0.05)), ("pmic", (-0.10, -0.12), (0.08, 0.08)), ("ant", (0.18, -0.14), (0.10, 0.04))):
        c = box(nm, (rx(0.139), cy, cz), (0.012, *sz), M["chip"], 0.004); adopt(c, board)
    for k in range(7):
        pad = box("pad", (rx(0.139), -0.22 + k * 0.05, -0.27), (0.004, 0.025, 0.018), M["gold"]); adopt(pad, board)

    battery = box("battery", (rx(0.085), 0.0, -0.14), (0.045, 0.36, 0.22), M["batt"], 0.012)
    part("battery", battery, 0.085, 0.45)

    magnet = cyl_x("magnet", (rx(0.035), 0, 0), 0.15, 0.07, M["magnet"], 48)
    part("magnet", magnet, 0.035, 0.10)
    frame = cyl_x("driverframe", (rx(-0.005), 0, 0), 0.22, 0.03, M["alu"], 64)
    part("driver", frame, -0.005, -0.20)
    dia = cyl_x("diaphragm", (rx(-0.032), 0, 0), 0.20, 0.012, M["nickel"], 64); adopt(dia, frame)
    dome = cyl_x("dome", (rx(-0.040), 0, 0), 0.08, 0.02, M["nickel"], 32); adopt(dome, frame)
    baffle = cyl_x("baffle", (rx(-0.08), 0, 0), 0.42, 0.022, M["mesh"], 64)
    part("baffle", baffle, -0.08, -0.55)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.32, minor_radius=0.115, major_segments=64, minor_segments=24, location=(rx(-0.20), 0, 0))
    cush = bpy.context.object; cush.name = "cushion"; cush.scale = (1, 1, 0.65)
    cush.rotation_euler = (0, math.pi / 2, 0); T(scale=True, rotation=True); bpy.ops.object.shade_smooth()
    cush.data.materials.append(M["foam"])
    part("cushion", cush, -0.20, -1.05)

    # ---- left cup (simple, flies away as one piece) ----
    LG = empty("LEFT_CUP", (-CX, 0, 0), RIG)
    for nm, lx, r, d, m_ in (("L_plate", 0.30, 0.46, 0.05, M["white"]), ("L_housing", 0.17, 0.46, 0.2, M["white"]), ("L_driver", 0.0, 0.22, 0.03, M["alu"]), ("L_baffle", -0.08, 0.42, 0.02, M["mesh"])):
        o = cyl_x(nm, (-CX - lx, 0, 0), r, d, m_); adopt(o, LG)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.32, minor_radius=0.115, major_segments=64, minor_segments=24, location=(-CX + 0.20, 0, 0))
    lc = bpy.context.object; lc.scale = (1, 1, 0.65); lc.rotation_euler = (0, math.pi / 2, 0)
    T(scale=True, rotation=True); bpy.ops.object.shade_smooth(); lc.data.materials.append(M["foam"]); adopt(lc, LG)

    # labelled anchors: rim point on the +screen-x side of each part (local z = -r after rotation)
    ANCH.update({"plate": (plate, (0, 0, -0.44)), "housing": (housing, (0, 0, 0.44)), "mainboard": (board, (0, 0, -0.33)),
                 "battery": (battery, (0, 0, -0.11)), "driver": (frame, (0, 0, 0.21)), "cushion": (cush, (0, 0, -0.43))})

    # ---------- timeline ----------
    def sm(u): u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)
    def lerp(a, b, u): return a + (b - a) * u

    T_SEP0, T_SEP1 = 3.0, 4.6        # band + left cup fly off, right cup stands up
    T_EXP0, T_EXP1 = 4.7, 6.4        # explode
    T_COL0, T_COL1 = 12.6, 13.7      # collapse
    T_RES0, T_RES1 = 13.5, 14.9      # cup lies back down, band + cup return
    ORDER = ["plate", "housing", "mainboard", "battery", "magnet", "driver", "baffle", "cushion"]

    def pose(t):
        sep = sm((t - T_SEP0) / (T_SEP1 - T_SEP0)) * (1 - sm((t - T_RES0) / (T_RES1 - T_RES0)))
        return sep

    def explode_amount(name, t):
        i = ORDER.index(name)
        a = sm((t - T_EXP0 - 0.06 * i) / (T_EXP1 - T_EXP0 - 0.4))
        b = sm((t - T_COL0 - 0.04 * (len(ORDER) - i)) / (T_COL1 - T_COL0 - 0.3))
        return a * (1 - b)

    def apply(t):
        sep = pose(t)
        # slow turntable while assembled, straightens out as the cup separates
        RIG.rotation_euler[2] = math.radians(lerp(-34, 14, sm(t / T_SEP0)) * (1 - sep))
        RG.location = (lerp(CX, 0.0, sep), 0, lerp(0, -0.35, sep))
        RG.rotation_euler[1] = math.radians(-90 * sep)
        LG.location = (lerp(-CX, -3.8, sep), 0, lerp(0, -0.6, sep))
        BAND.location = (0, 0, lerp(0, 3.8, sep))
        for nm, p in PARTS.items():
            e = explode_amount(nm, t)
            lx = lerp(p["base"], p["final"], e)
            p["obj"].location = (CX + lx, p["y"], p["z"])

    # camera: (t, distance, azimuth deg, elevation deg, target z)
    CAMK = [(0.0, 6.4, -6, 6, 0.25), (3.0, 5.6, 6, 8, 0.2), (4.7, 5.3, 0, 14, 0.0), (6.4, 4.9, 0, 16, 0.05),
            (8.5, 4.7, -12, 18, 0.05), (10.5, 4.5, 10, 20, 0.05), (12.4, 4.9, 0, 16, 0.05), (13.6, 5.2, 0, 11, 0.0),
            (14.9, 5.9, -6, 7, 0.25)]
else:
    # =====================================================================
    # TV (lying flat; layers fan upward along Z)
    # =====================================================================
    RIG = empty("RIG")
    PARTS = {}
    TW, TD = 3.2, 1.8   # width (x), depth (y); thickness along z

    def layer(name, objs, base_z, final_z, shift=(0, 0)):
        root = empty(name, (0, 0, base_z), RIG)
        for o in objs:
            adopt(o, root)
        PARTS[name] = dict(obj=root, base=base_z, final=final_z, shift=shift)
        return root

    back = box("back", (0, 0, 0), (TW, TD, 0.05), M["cover"], 0.02)
    ribs = [box("rib", (x, 0, 0.04), (0.03, TD * 0.9, 0.03), M["cover"]) for x in (-1.0, -0.3, 0.4, 1.1)]
    vesa = [box("vesa", (x, 0, 0.04), (0.06, 0.06, 0.03), M["alu"]) for x in (-0.2, 0.2)]
    layer("back", [back] + ribs + vesa, 0.0, 0.0)

    mainb = box("mainboard", (-0.65, 0.05, 0), (0.8, 0.55, 0.02), M["pcb"])
    soc = box("soc", (-0.78, 0.10, 0.03), (0.16, 0.16, 0.035), M["chip"], 0.005)
    ram = [box("ram", (-0.55 + k * 0.12, 0.12, 0.025), (0.09, 0.07, 0.025), M["chip"]) for k in range(3)]
    tuner = box("tuner", (-0.40, -0.12, 0.04), (0.18, 0.12, 0.06), M["alu"])
    wifi = box("wifi", (-0.88, -0.14, 0.03), (0.13, 0.09, 0.02), M["chip"])
    psu = box("psu", (0.75, 0.0, 0), (1.0, 0.55, 0.02), M["pcb"])
    caps = [cyl_z("cap", (0.45 + k * 0.17, 0.12, 0.05), 0.055, 0.09, M["alu"], 24) for k in range(4)]
    xf = box("xfmr", (1.05, -0.08, 0.05), (0.22, 0.2, 0.1), M["chip"], 0.01)
    tcon = box("tcon", (0.0, -0.45, 0), (0.45, 0.16, 0.02), M["pcb"])
    spk = [cyl_z("speaker", (s * 1.2, -0.68, 0.04), 0.14, 0.09, M["speaker"], 32) for s in (-1, 1)]
    for s_ in spk: s_.scale = (1.5, 0.9, 1)
    layer("boards", [mainb, soc, *ram, tuner, wifi, psu, *caps, xf, tcon, *spk], 0.0, 0.85)

    led = box("ledstrip", (0, -0.86, 0), (TW * 0.96, 0.05, 0.05), M["led"])
    lgp = box("lgp", (0, 0, 0), (TW * 0.97, TD * 0.96, 0.03), M["film"])
    layer("backlight", [led, lgp], 0.0, 1.70, (0.0, 0.0))

    films = box("films", (0, 0, 0), (TW * 0.97, TD * 0.96, 0.012), M["film"])
    layer("films", [films], 0.0, 2.25)

    panel = box("panel", (0, 0, 0), (TW, TD, 0.035), M["glass"], 0.008)
    layer("panel", [panel], 0.0, 3.0)

    bz = []
    for nm, loc, sz in (("bz_t", (0, TD / 2 - 0.04, 0), (TW + 0.06, 0.1, 0.07)), ("bz_b", (0, -TD / 2 + 0.04, 0), (TW + 0.06, 0.1, 0.07)),
                        ("bz_l", (-TW / 2 + 0.03, 0, 0), (0.08, TD, 0.07)), ("bz_r", (TW / 2 - 0.03, 0, 0), (0.08, TD, 0.07))):
        bz.append(box(nm, loc, sz, M["shell"], 0.012))
    logo = box("logo", (0, -TD / 2 + 0.04, 0.04), (0.13, 0.03, 0.005), M["alu"])
    layer("bezel", [*bz, logo], 0.0, 3.85)

    ANCH.update({"panel": (PARTS["panel"]["obj"], (TW / 2 - 0.05, 0.0, 0.0)), "backlight": (PARTS["backlight"]["obj"], (TW / 2 - 0.1, -0.4, 0.0)),
                 "boards_main": (PARTS["boards"]["obj"], (-0.65, 0.05, 0.05)), "boards_psu": (PARTS["boards"]["obj"], (1.15, 0.0, 0.05)),
                 "boards_spk": (PARTS["boards"]["obj"], (1.2, -0.68, 0.05)), "back": (PARTS["back"]["obj"], (TW / 2 - 0.2, 0.3, 0.0))})

    def sm(u): u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)
    def lerp(a, b, u): return a + (b - a) * u
    T_EXP0, T_EXP1, T_COL0, T_COL1 = 1.0, 2.5, 6.8, 8.1
    ORDER = ["back", "boards", "backlight", "films", "panel", "bezel"]

    def apply(t):
        for i, nm in enumerate(ORDER):
            p = PARTS[nm]
            a = sm((t - T_EXP0 - 0.09 * i) / (T_EXP1 - T_EXP0 - 0.5))
            b = sm((t - T_COL0 - 0.05 * (len(ORDER) - i)) / (T_COL1 - T_COL0 - 0.3))
            e = a * (1 - b)
            p["obj"].location = (lerp(0, 0.0, e), lerp(0, 0.0, e), lerp(p["base"], p["final"], e))
        RIG.rotation_euler[2] = math.radians(lerp(-12, 6, sm(t / DUR)))

    CAMK = [(0.0, 8.0, -28, 24, 0.2), (1.0, 7.6, -22, 25, 0.5), (2.5, 8.2, -14, 26, 1.8), (4.5, 7.4, -4, 27, 1.9),
            (6.8, 7.8, 6, 27, 1.9), (8.2, 9.2, 10, 24, 0.4)]


# ---------- camera ----------
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 24; cam.data.lens = 40
cam.data.dof.use_dof = False


def cam_at(t):
    ks = CAMK
    if t <= ks[0][0]: k = ks[0][1:]
    elif t >= ks[-1][0]: k = ks[-1][1:]
    else:
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t <= b[0]:
                u = sm((t - a[0]) / (b[0] - a[0])); k = tuple(lerp(x, y, u) for x, y in zip(a[1:], b[1:])); break
    D, az, el, tz = k
    az, el = math.radians(az), math.radians(el)
    tgt = Vector((0, 0, tz))
    cam.location = tgt + Vector((D * math.sin(az) * math.cos(el), -D * math.cos(az) * math.cos(el), D * math.sin(el)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()


TRACK = {}


def screen_points():
    out = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for nm, (ob, off) in ANCH.items():
        p = ob.evaluated_get(dg).matrix_world @ Vector(off)
        v = world_to_camera_view(sc, cam, p)
        out[nm] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
    return out


def setup(t):
    apply(t); cam_at(t)
    bpy.context.view_layer.update()


if TEST_T is not None:
    setup(TEST_T)
    if os.environ.get("DEBUGPOS") and WHAT == "hp":
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in (RIG, RG, LG, plate, housing, cush, bpy.data.objects["L_plate"], BAND):
            print("DEBUGPOS", ob.name, [round(v, 3) for v in ob.evaluated_get(dg).matrix_world.translation], "loc", [round(v, 3) for v in ob.location], "par", ob.parent.name if ob.parent else None, "inv", [round(v, 3) for v in ob.matrix_parent_inverse.translation], flush=True)
    sc.render.filepath = os.path.join(HERE, f"test_{WHAT}_{TEST_T}.png")
    bpy.ops.render.render(write_still=True)
    print("TEST", screen_points(), flush=True)
    sys.exit()

import time
T0 = time.time()
for f in range(1, NF + 1):
    t = (f - 1) / FPS
    setup(t)
    TRACK[f] = screen_points()
    sc.render.filepath = os.path.join(OUT, f"{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f}/{NF} {time.time() - T0:.0f}s", flush=True)
json.dump({"fps": FPS, "n": NF, "pts": TRACK}, open(os.path.join(OUT, "track.json"), "w"))
print("ALL DONE", flush=True)

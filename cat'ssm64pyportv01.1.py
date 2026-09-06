#!/usr/bin/env python3
"""cat'ssm64pyportv01.1.py — cat's SM64 PC-port style Python engine (FILES_OFF).

Clean-room FOSS tribute: pygame-ce + import math reimplementation of SM64 PC-port systems
(not a C decomp dump). Inspired by sm64-port / Super Mario 64 structure
(not affiliated with Nintendo). Castle Grounds hub + Courses 1–15
(Bob-omb Battlefield … Rainbow Ride).

FILES_OFF: no ROM, no ripped textures/models/audio — procedural geometry +
custom math 3D engine (matrices, lighting, fog, materials) + software polys +
synth OST (in-game only) + quiet SFX. No ROM/.seq/.wav/.mp3. No OpenGL Nintendo asset loading.

Install:  python -m pip install pygame-ce
Run:      python "cat'ssm64pyportv01.1.py"

Controls (sm64-port style):
  WASD / Arrows   move (camera-relative)
  Space           jump (chain = double / triple)
  Shift+Space     long jump (while running)
  Shift (air)     ground pound
  Ctrl / Z (air)  dive
  Ctrl / Z (gnd)  punch / crouch slide
  A / Enter / Z   enter door / painting / pipe (primary: A)
  Walk into       painting & pipe warps (auto)
  Q / E / Mouse   Lakitu camera
  M               toggle music
  Esc             course select
"""

FILES_OFF = True
PRODUCT_NAME = "cat's sm64 pyport v01.1"

# Course unlock gates (session stars) — PC-port hub pacing
STAR_GATES = {
    "Castle Grounds": 0,
    "Castle Lobby": 0,
    "Castle Basement": 1,
    "Castle Upstairs": 3,
    "Bob-omb Battlefield": 0,
    "Whomp's Fortress": 1,
    "Jolly Roger Bay": 3,
    "Cool, Cool Mountain": 3,
    "Big Boo's Haunt": 12,
    "Hazy Maze Cave": 3,
    "Lethal Lava Land": 8,
    "Shifting Sand Land": 8,
    "Dire, Dire Docks": 30,
    "Snowman's Land": 10,
    "Wet-Dry World": 10,
    "Tall, Tall Mountain": 10,
    "Tiny-Huge Island": 10,
    "Tick Tock Clock": 15,
    "Rainbow Ride": 15,
    "Bowser in the Dark World": 8,
    "Bowser in the Fire Sea": 30,
    "Bowser in the Sky": 70,
}

# Bowser key doors (keys earned by beating simplified Bowser arenas)
KEY_GATES = {
    "Bowser in the Fire Sea": 1,
    "Bowser in the Sky": 2,
}

import sys
import json
from pathlib import Path as _Path
import math
import random

try:
    import pygame
except ImportError as exc:
    print("This game requires pygame-ce (pip install pygame-ce).", file=sys.stderr)
    print(f"Import error: {exc}", file=sys.stderr)
    raise SystemExit(1)

# pygame-ce exposes IS_CE=1; vanilla pygame does not.
PYGAME_BACKEND = "pygame-ce" if getattr(pygame, "IS_CE", 0) else "pygame"

pygame.init()
WIDTH, HEIGHT = 800, 600
HALF_W, HALF_H = WIDTH // 2, HEIGHT // 2
FOV_FACTOR = HALF_W / math.tan(math.radians(45))
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(f"{PRODUCT_NAME}  [FILES_OFF · {PYGAME_BACKEND}]")
clock = pygame.time.Clock()

# --- FILES_OFF OST / SFX: original procedural synth ONLY (no ROM/.seq/.m64/.wav/.mp3) ---
# Tribute chiptune moods inspired by SM64 PC-port style — not ripped Nintendo sequences.
import array as _arr

AUDIO_RATE = 22050
MUSIC_ENABLED = True          # toggled with M during play
SFX_VOLUME = 0.22             # muted/quiet SFX so in-game OST is the focus
MUSIC_VOLUME = 0.55
STAR_GET_MUSIC_VOLUME = 0.18  # soft bed under star fanfare overlay

def _clamp16(x):
    return max(-32767, min(32767, int(x)))

def _wave_sample(t, freq, kind="square"):
    if freq <= 0:
        return 0.0
    phase = (t * freq) % 1.0
    if kind == "square":
        return 1.0 if phase < 0.5 else -1.0
    if kind == "triangle":
        return (4.0 * phase - 1.0) if phase < 0.5 else (3.0 - 4.0 * phase)
    if kind == "saw":
        return 2.0 * phase - 1.0
    return ((int(t * 1315423911) ^ int(freq * 97)) & 255) / 127.5 - 1.0

def _synth_buf(freq, ms, vol=0.12, kind="square", sweep_to=None, noise_mix=0.0):
    n = max(1, int(AUDIO_RATE * ms / 1000.0))
    buf = _arr.array("h")
    for i in range(n):
        t = i / AUDIO_RATE
        env = 1.0
        if i < n * 0.05:
            env = i / max(1, n * 0.05)
        elif i > n * 0.7:
            env = max(0.0, (n - i) / max(1, n * 0.3))
        f = freq if sweep_to is None else freq + (sweep_to - freq) * (i / max(1, n - 1))
        s = _wave_sample(t, f, kind)
        if noise_mix:
            s = s * (1.0 - noise_mix) + _wave_sample(t, f * 0.5, "noise") * noise_mix
        buf.append(_clamp16(s * env * vol * 32767))
    return pygame.mixer.Sound(buffer=buf)

def _build_theme_loop(theme="grass", seconds=4.0):
    """Original FILES_OFF chiptune beds (hub/course moods). Not SM64 ripped audio."""
    specs = {
        # bright marchy field — overworld-ish tribute
        "grass": dict(bpm=132, melody=[262,330,392,523,392,330,294,349,440,349,330,392,523,440,392,330],
                      bass=[131,131,165,165,196,196,147,147], lead="square", lead_v=0.17, tri_v=0.11, bass_v=0.15, hat=0.05),
        "hub": dict(bpm=118, melody=[294,370,440,494,440,370,330,392,440,392,349,440,523,440,392,330],
                    bass=[147,147,185,185,220,220,165,165], lead="triangle", lead_v=0.14, tri_v=0.10, bass_v=0.14, hat=0.03),
        "water": dict(bpm=96, melody=[220,247,294,330,294,247,208,247,277,330,277,247,220,262,294,262],
                      bass=[110,110,123,123,147,147,131,131], lead="triangle", lead_v=0.13, tri_v=0.14, bass_v=0.12, hat=0.02),
        "snow": dict(bpm=108, melody=[349,392,440,523,440,392,330,370,415,370,349,415,494,415,392,349],
                     bass=[175,175,196,196,220,220,185,185], lead="triangle", lead_v=0.12, tri_v=0.13, bass_v=0.11, hat=0.025),
        "fire": dict(bpm=140, melody=[196,233,262,311,262,233,208,247,294,247,220,262,311,262,233,196],
                     bass=[98,98,116,116,131,131,110,110], lead="saw", lead_v=0.14, tri_v=0.08, bass_v=0.14, hat=0.06),
        "desert": dict(bpm=120, melody=[233,277,311,370,311,277,262,311,349,311,277,330,392,330,311,277],
                       bass=[116,116,139,139,155,155,131,131], lead="square", lead_v=0.14, tri_v=0.09, bass_v=0.13, hat=0.04),
        "cave": dict(bpm=100, melody=[196,220,247,262,247,220,185,208,233,208,196,233,277,233,220,196],
                     bass=[98,98,110,110,123,123,104,104], lead="triangle", lead_v=0.11, tri_v=0.12, bass_v=0.13, hat=0.035),
        "ghost": dict(bpm=88, melody=[185,208,233,277,233,208,175,196,220,196,185,220,262,220,208,185],
                      bass=[92,92,104,104,116,116,98,98], lead="triangle", lead_v=0.10, tri_v=0.12, bass_v=0.12, hat=0.02),
        "metal": dict(bpm=124, melody=[330,330,392,392,440,392,349,349,415,415,494,415,392,370,330,294],
                      bass=[165,165,196,196,220,220,175,175], lead="square", lead_v=0.15, tri_v=0.07, bass_v=0.14, hat=0.055),
        "sky": dict(bpm=128, melody=[392,440,494,587,494,440,370,415,466,415,392,466,554,466,440,392],
                    bass=[196,196,220,220,247,247,208,208], lead="square", lead_v=0.15, tri_v=0.12, bass_v=0.12, hat=0.04),
        "sand": dict(bpm=120, melody=[233,277,311,370,311,277,262,311,349,311,277,330,392,330,311,277],
                     bass=[116,116,139,139,155,155,131,131], lead="square", lead_v=0.14, tri_v=0.09, bass_v=0.13, hat=0.04),
    }
    sp = specs.get(theme, specs["grass"])
    n = int(AUDIO_RATE * seconds)
    buf = _arr.array("h")
    beat = 60.0 / sp["bpm"]
    melody, bass = sp["melody"], sp["bass"]
    for i in range(n):
        t = i / AUDIO_RATE
        step = int(t / (beat * 0.5)) % len(melody)
        bstep = int(t / beat) % len(bass)
        lead = _wave_sample(t, melody[step], sp["lead"]) * sp["lead_v"]
        tri = _wave_sample(t, melody[step] * 0.5, "triangle") * sp["tri_v"]
        bas = _wave_sample(t, bass[bstep], "triangle") * sp["bass_v"]
        hat = _wave_sample(t, 7500, "noise") * sp["hat"] if (t % beat) < 0.035 else 0.0
        if theme == "water" and (int(t * 3) % 5 == 0):
            tri += _wave_sample(t, 180 + 40 * ((int(t * 8) % 3)), "triangle") * 0.04
        if theme == "fire" and (t % (beat * 0.5)) < 0.02:
            hat += _wave_sample(t, 400, "noise") * 0.04
        if theme == "sky":
            lead += _wave_sample(t, melody[step] * 2, "triangle") * 0.04
        buf.append(_clamp16((lead + tri + bas + hat) * 32767))
    return pygame.mixer.Sound(buffer=buf)

# Course / hub → synth mood (original patterns only)
COURSE_OST_THEME = {
    "Castle Grounds": "hub",
    "Peach's Castle": "hub",
    "Castle Lobby": "hub",
    "Castle Basement": "cave",
    "Castle Upstairs": "hub",
    "Bob-omb Battlefield": "grass",
    "Whomp's Fortress": "grass",
    "Jolly Roger Bay": "water",
    "Cool, Cool Mountain": "snow",
    "Big Boo's Haunt": "ghost",
    "Hazy Maze Cave": "cave",
    "Lethal Lava Land": "fire",
    "Shifting Sand Land": "desert",
    "Dire, Dire Docks": "water",
    "Snowman's Land": "snow",
    "Wet-Dry World": "water",
    "Tall, Tall Mountain": "grass",
    "Tiny-Huge Island": "grass",
    "Tick Tock Clock": "metal",
    "Rainbow Ride": "sky",
    "Bowser in the Dark World": "ghost",
    "Bowser in the Fire Sea": "fire",
    "Bowser in the Sky": "sky",
}

SFX = {}
OST_BANK = {}
_music_channel = None
_current_ost_theme = None

try:
    pygame.mixer.init(AUDIO_RATE, -16, 1, 512)
    # Quiet SFX — game is "muted" relative to OST
    SFX = {
        "jump": _synth_buf(420, 90, 0.35, "square", sweep_to=560),
        "coin": _synth_buf(988, 90, 0.35, "square", sweep_to=1319),
        "star": _synth_buf(523, 280, 0.40, "triangle", sweep_to=1047),
        "hurt": _synth_buf(160, 140, 0.38, "saw", sweep_to=90, noise_mix=0.35),
        "pound": _synth_buf(70, 120, 0.40, "noise", noise_mix=1.0),
        "1up": _synth_buf(523, 220, 0.35, "triangle", sweep_to=784),
        "swim": _synth_buf(280, 60, 0.25, "triangle"),
        "cap": _synth_buf(660, 160, 0.32, "square", sweep_to=880),
    }
    for th in ("hub", "grass", "water", "snow", "fire", "desert", "cave", "ghost", "metal", "sky"):
        OST_BANK[th] = _build_theme_loop(th)
except Exception:
    SFX = {}
    OST_BANK = {}

def play_sfx(name):
    s = SFX.get(name)
    if not s:
        return
    try:
        ch = s.play()
        if ch is not None:
            ch.set_volume(SFX_VOLUME)
    except Exception:
        pass

def music_stop():
    global _music_channel, _current_ost_theme
    try:
        if _music_channel is not None:
            _music_channel.stop()
    except Exception:
        pass
    _current_ost_theme = None

def music_set_volume(vol):
    try:
        if _music_channel is not None:
            _music_channel.set_volume(max(0.0, min(1.0, vol)))
    except Exception:
        pass

def music_play_theme(theme, force=False):
    """Start/switch in-game OST. Menus must call music_stop() instead."""
    global _music_channel, _current_ost_theme, MUSIC_ENABLED
    if not MUSIC_ENABLED:
        music_stop()
        return
    snd = OST_BANK.get(theme) or OST_BANK.get("grass")
    if not snd:
        return
    try:
        if _music_channel is None:
            _music_channel = pygame.mixer.Channel(0)
        if force or _current_ost_theme != theme or not _music_channel.get_busy():
            _music_channel.play(snd, loops=-1)
            _music_channel.set_volume(MUSIC_VOLUME)
            _current_ost_theme = theme
        else:
            _music_channel.set_volume(MUSIC_VOLUME)
    except Exception:
        pass

def music_for_world(world):
    name = getattr(world, "name", "") if world else ""
    theme = getattr(world, "ost_theme", None) or COURSE_OST_THEME.get(name, "grass")
    music_play_theme(theme)

def music_toggle():
    global MUSIC_ENABLED
    MUSIC_ENABLED = not MUSIC_ENABLED
    if not MUSIC_ENABLED:
        music_stop()
    return MUSIC_ENABLED

# --- FILES_OFF progress save (local JSON only; no ROM/assets) ---
_SAVE_DIR = _Path(__file__).resolve().parent / "out"
_SAVE_PATH = _SAVE_DIR / "cats_sm64pyport_save.json"

def default_save():
    return {
        "stars": 0,
        "keys": 0,
        "coins": 0,
        "lives": 4,
        "course_stars": {},  # course name -> count collected this session/file
        "red_coins": {},
        "missions": {},
    }

def load_save():
    if not FILES_OFF:
        return default_save()
    try:
        if _SAVE_PATH.is_file():
            data = json.loads(_SAVE_PATH.read_text(encoding="utf-8"))
            base = default_save()
            base.update({k: data.get(k, base[k]) for k in base})
            return base
    except Exception:
        pass
    return default_save()

def write_save(data):
    if not FILES_OFF:
        return
    try:
        _SAVE_DIR.mkdir(parents=True, exist_ok=True)
        _SAVE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass



SKY_BLUE       = (100, 149, 237)
GRASS_GREEN    = (50, 160, 60)
DARK_GREEN     = (30, 120, 30)
STONE_GRAY     = (220, 220, 220)
DARK_GRAY      = (140, 140, 140)
ROOF_RED       = (180, 40, 40)
BLACK          = (20, 20, 20)
WHITE          = (255, 255, 255)
YELLOW         = (255, 230, 0)
MARIO_RED      = (255, 50, 50)
MARIO_BLUE     = (0, 70, 180)
WOOD_BROWN     = (140, 100, 60)
TRUNK_BROWN    = (120, 80, 40)
TREE_GREEN     = (40, 140, 40)
SAND_YELLOW    = (210, 180, 100)
LAVA_RED       = (220, 60, 20)
LAVA_ORANGE    = (255, 120, 30)
SNOW_WHITE     = (240, 245, 255)
ICE_BLUE       = (180, 210, 240)
WATER_BLUE     = (50, 120, 210)
DEEP_WATER     = (20, 60, 150)
PURPLE         = (120, 40, 160)
CAVE_BROWN     = (100, 80, 55)
CAVE_DARK      = (70, 55, 40)
METAL_GRAY     = (170, 175, 180)
GOLD           = (230, 190, 40)
CLOCK_BEIGE    = (220, 200, 160)
RAINBOW_PINK   = (255, 150, 200)
RAINBOW_CYAN   = (100, 240, 255)
RAINBOW_LIME   = (150, 255, 100)
MANSION_PURPLE = (90, 70, 110)
MANSION_GREEN  = (60, 90, 60)
DOCK_BLUE      = (30, 80, 160)
VOLCANO_GRAY   = (90, 80, 75)
VOLCANO_RED    = (170, 50, 30)
PYRAMID_TAN    = (200, 170, 110)
PYRAMID_DARK   = (160, 130, 80)
CANNON_BLACK   = (40, 40, 40)
NES_BLUE       = (92, 148, 252)
STAR_YELLOW    = (255, 255, 100)
PARCHMENT      = (250, 240, 200)
INK_COLOR      = (50, 40, 100)
STONE_PATH     = (200, 200, 200)
BRICK_RED      = (160, 60, 50)
DARK_BROWN     = (80, 50, 25)
FENCE_BROWN    = (110, 75, 40)
MOAT_BLUE      = (40, 100, 200)
SKY_SNOW       = (180, 200, 230)
SKY_LAVA       = (60, 20, 10)
SKY_CAVE       = (40, 35, 30)
SKY_UNDERWATER = (20, 50, 100)
SKY_DESERT     = (220, 180, 120)
SKY_MANSION    = (30, 20, 40)
SKY_RAINBOW    = (140, 160, 255)
CHAIN_GRAY     = (80, 80, 80)
LIGHT_DIR      = (0.577, 0.577, 0.577)
BOX_FACE_INDICES = [[0,1,2,3],[4,5,6,7],[0,4,7,3],[1,5,6,2],[3,2,6,7],[0,1,5,4]]
FACE_NORMALS_BOX = [(0,0,-1),(0,0,1),(-1,0,0),(1,0,0),(0,1,0),(0,-1,0)]

try:
    title_font  = pygame.font.SysFont("Arial Black", 55, bold=True)
    letter_font = pygame.font.SysFont("Georgia", 30, italic=True)
    menu_font   = pygame.font.SysFont("Arial", 28, bold=True)
    hud_font    = pygame.font.SysFont("Courier New", 18, bold=True)
    select_font = pygame.font.SysFont("Arial", 22, bold=True)
    star_font   = pygame.font.SysFont("Arial Black", 36, bold=True)
    small_font  = pygame.font.SysFont("Arial", 16)
except:
    title_font  = pygame.font.Font(None, 70)
    letter_font = pygame.font.Font(None, 36)
    menu_font   = pygame.font.Font(None, 40)
    hud_font    = pygame.font.Font(None, 22)
    select_font = pygame.font.Font(None, 28)
    star_font   = pygame.font.Font(None, 44)
    small_font  = pygame.font.Font(None, 20)

# ============================================================
# SM64 Behavior Script System (ported from sm64-port)
# Opcodes match behavior_script.h / behavior_script.c
# ============================================================

# --- Behavior Opcodes ---
BHV_BEGIN                    = 0x00
BHV_DELAY                    = 0x01
BHV_CALL                     = 0x02
BHV_RETURN                   = 0x03
BHV_GOTO                     = 0x04
BHV_BEGIN_REPEAT             = 0x05
BHV_END_REPEAT               = 0x06
BHV_END_REPEAT_CONTINUE      = 0x07
BHV_BEGIN_LOOP               = 0x08
BHV_END_LOOP                 = 0x09
BHV_BREAK                    = 0x0A
BHV_BREAK_UNUSED             = 0x0B
BHV_CALL_NATIVE              = 0x0C
BHV_ADD_FLOAT                = 0x0D
BHV_SET_FLOAT                = 0x0E
BHV_ADD_INT                  = 0x0F
BHV_SET_INT                  = 0x10
BHV_OR_INT                   = 0x11
BHV_BIT_CLEAR                = 0x12
BHV_SET_INT_RAND_RSHIFT      = 0x13
BHV_SET_RANDOM_FLOAT         = 0x14
BHV_SET_RANDOM_INT           = 0x15
BHV_ADD_RANDOM_FLOAT         = 0x16
BHV_ADD_INT_RAND_RSHIFT      = 0x17
BHV_CMD_NOP_1                = 0x18
BHV_CMD_NOP_2                = 0x19
BHV_CMD_NOP_3                = 0x1A
BHV_SET_MODEL                = 0x1B
BHV_SPAWN_CHILD              = 0x1C
BHV_DEACTIVATE               = 0x1D
BHV_DROP_TO_FLOOR            = 0x1E
BHV_SUM_FLOAT                = 0x1F
BHV_SUM_INT                  = 0x20
BHV_BILLBOARD                = 0x21
BHV_HIDE                     = 0x22
BHV_SET_HITBOX               = 0x23
BHV_CMD_NOP_4                = 0x24
BHV_DELAY_VAR                = 0x25
BHV_BEGIN_REPEAT_UNUSED      = 0x26
BHV_LOAD_ANIMATIONS          = 0x27
BHV_ANIMATE                  = 0x28
BHV_SPAWN_CHILD_WITH_PARAM   = 0x29
BHV_LOAD_COLLISION_DATA      = 0x2A
BHV_SET_HITBOX_WITH_OFFSET   = 0x2B
BHV_SPAWN_OBJ                = 0x2C
BHV_SET_HOME                 = 0x2D
BHV_SET_HURTBOX              = 0x2E
BHV_SET_INTERACT_TYPE        = 0x2F
BHV_SET_OBJ_PHYSICS          = 0x30
BHV_SET_INTERACT_SUBTYPE     = 0x31
BHV_SCALE                    = 0x32
BHV_PARENT_BIT_CLEAR         = 0x33
BHV_ANIMATE_TEXTURE          = 0x34
BHV_DISABLE_RENDERING        = 0x35
BHV_SET_INT_UNUSED           = 0x36
BHV_SPAWN_WATER_DROPLET      = 0x37

BHV_PROC_CONTINUE = 0
BHV_PROC_BREAK = 1

# --- Object List IDs ---
OBJ_LIST_DEFAULT      = 0
OBJ_LIST_SURFACE      = 1
OBJ_LIST_POLELIKE     = 2
OBJ_LIST_SPAWNER      = 3
OBJ_LIST_UNIMPORTANT  = 4
OBJ_LIST_LEVEL        = 5
OBJ_LIST_GENACTOR     = 6

# --- Object Field Indices --- (matching object_fields.h)
O_FIELD_START = 0x00
OFFLAGS = 0x01
ODIALOGRESPONSE = 0x02
ODIALOGSTATE = 0x02
OUNK94 = 0x03
OINTANGIBLETIMER = 0x05
OPOSX = 0x06
OPOSY = 0x07
OPOSZ = 0x08
OVELX = 0x09
OVELY = 0x0A
OVELZ = 0x0B
OFORWARDVEL = 0x0C
OLEFTVEL = 0x0D
OUPVEL = 0x0E
OMOVEANGLEPITCH = 0x0F
OMOVEANGLEYAW = 0x10
OMOVEANGLEROLL = 0x11
OFACEANGLEPITCH = 0x12
OFACEANGLEYAW = 0x13
OFACEANGLEROLL = 0x14
OGRAPHYOFFSET = 0x15
OACTIVEPARTICLEFLAGS = 0x16
OGRAVITY = 0x17
OFLOORHEIGHT = 0x18
OMOVEFLAGS = 0x19
OANIMSTATE = 0x1A
OANGLEVELPITCH = 0x23
OANGLEVELYAW = 0x24
OANGLEVELROLL = 0x25
OANIMATIONS = 0x26
OHELDSTATE = 0x27
OWALLHITBOXRADIUS = 0x28
ODRAGSTRENGTH = 0x29
OINTERACTTYPE = 0x2A
OINTERACTSTATUS = 0x2B
OPARENTRELATIVEPOSX = 0x2C
OPARENTRELATIVEPOSY = 0x2D
OPARENTRELATIVEPOSZ = 0x2E
OBHVPARAMS2NDBYTE = 0x2F
OACTION = 0x31
OSUBACTION = 0x32
OTIMER = 0x33
OBOUNCINESS = 0x34
ODISTANCETOMARIO = 0x35
OANGLETOMARIO = 0x36
OHOMEX = 0x37
OHOMEY = 0x38
OHOMEZ = 0x39
OFRICTION = 0x3A
OBUOYANCY = 0x3B
OSOUNDSTATEID = 0x3C
OOPACITY = 0x3D
ODAMAGEORCOINVALUE = 0x3E
OHEALTH = 0x3F
OBHVPARAMS = 0x40
OPREVACTION = 0x41
OINTERACTIONSUBTYPE = 0x42
OCOLLISIONDISTANCE = 0x43
ONUMLOOTCOINS = 0x44
ODRAWINGDISTANCE = 0x45
OROOM = 0x46
OUNUSEDBHVPARAMS = 0x48
OWALLANGLE = 0x4B
OFLOORTYPE = 0x4C
OFLOORROOM = 0x4C
OANGLETOHOME = 0x4D
OFLOOR = 0x4E
ODEATHSOUND = 0x4F

# --- Object Flags ---
OBJ_FLAG_UPDATE_GFX_POS_AND_ANGLE        = 1 << 0
OBJ_FLAG_MOVE_XZ_USING_FVEL              = 1 << 1
OBJ_FLAG_MOVE_Y_WITH_TERMINAL_VEL        = 1 << 2
OBJ_FLAG_SET_FACE_YAW_TO_MOVE_YAW        = 1 << 3
OBJ_FLAG_SET_FACE_ANGLE_TO_MOVE_ANGLE    = 1 << 4
OBJ_FLAG_COMPUTE_DIST_TO_MARIO           = 1 << 6
OBJ_FLAG_ACTIVE_FROM_AFAR                = 1 << 7
OBJ_FLAG_TRANSFORM_RELATIVE_TO_PARENT    = 1 << 9
OBJ_FLAG_HOLDABLE                        = 1 << 10
OBJ_FLAG_SET_THROW_MATRIX_FROM_TRANSFORM = 1 << 11
OBJ_FLAG_COMPUTE_ANGLE_TO_MARIO          = 1 << 13
OBJ_FLAG_PERSISTENT_RESPAWN              = 1 << 14

# --- Active Flags ---
ACTIVE_FLAG_ACTIVE          = 1 << 0
ACTIVE_FLAG_FAR_AWAY        = 1 << 1
ACTIVE_FLAG_DEACTIVATED     = 0

# --- Behavior script macro helpers (matching behavior_data.c) ---
def _BC_B(op):
    return (op << 24) & 0xFF000000

def _BC_BB(op, a):
    return ((op << 24) & 0xFF000000) | ((a << 16) & 0x00FF0000)

def _BC_B0H(op, h):
    return ((op << 24) & 0xFF000000) | (h & 0x0000FFFF)

def _BC_BBH(op, b, h):
    return ((op << 24) & 0xFF000000) | ((b << 16) & 0x00FF0000) | (h & 0x0000FFFF)

def _BC_BBBB(op, a, b, c):
    return ((op << 24) & 0xFF000000) | ((a << 16) & 0x00FF0000) | ((b << 8) & 0x0000FF00) | (c & 0x000000FF)

def _BC_H(val):
    return val & 0x0000FFFF

def _BC_HH(a, b):
    return ((a << 16) & 0xFFFF0000) | (b & 0x0000FFFF)

def _BC_W(val):
    return val & 0xFFFFFFFF

# Behavior macro builders - return list of 32-bit command words
def bhv_begin(obj_list):
    return [_BC_BB(BHV_BEGIN, obj_list)]

def bhv_delay(num):
    return [_BC_B0H(BHV_DELAY, num)]

def bhv_call(addr):
    return [_BC_B(BHV_CALL), _BC_W(id(addr))]

def bhv_return():
    return [_BC_B(BHV_RETURN)]

def bhv_goto(addr):
    return [_BC_B(BHV_GOTO), _BC_W(id(addr))]

def bhv_begin_repeat(count):
    return [_BC_B0H(BHV_BEGIN_REPEAT, count)]

def bhv_end_repeat():
    return [_BC_B(BHV_END_REPEAT)]

def bhv_end_repeat_continue():
    return [_BC_B(BHV_END_REPEAT_CONTINUE)]

def bhv_begin_loop():
    return [_BC_B(BHV_BEGIN_LOOP)]

def bhv_end_loop():
    return [_BC_B(BHV_END_LOOP)]

def bhv_break():
    return [_BC_B(BHV_BREAK)]

def bhv_call_native(func):
    return [_BC_B(BHV_CALL_NATIVE), _BC_W(id(func))]

def bhv_set_float(field, value):
    return [_BC_BBH(BHV_SET_FLOAT, field, value)]

def bhv_set_int(field, value):
    return [_BC_BBH(BHV_SET_INT, field, value)]

def bhv_add_float(field, value):
    return [_BC_BBH(BHV_ADD_FLOAT, field, value)]

def bhv_add_int(field, value):
    return [_BC_BBH(BHV_ADD_INT, field, value)]

def bhv_or_int(field, value):
    return [_BC_BBH(BHV_OR_INT, field, value)]

def bhv_set_model(modelID):
    return [_BC_B0H(BHV_SET_MODEL, modelID)]

def bhv_deactivate():
    return [_BC_B(BHV_DEACTIVATE)]

def bhv_drop_to_floor():
    return [_BC_B(BHV_DROP_TO_FLOOR)]

def bhv_set_home():
    return [_BC_B(BHV_SET_HOME)]

def bhv_billboard():
    return [_BC_B(BHV_BILLBOARD)]

def bhv_hide():
    return [_BC_B(BHV_HIDE)]

def bhv_set_hitbox(radius, height):
    return [_BC_B(BHV_SET_HITBOX), _BC_HH(radius, height)]

def bhv_set_hurtbox(radius, height):
    return [_BC_B(BHV_SET_HURTBOX), _BC_HH(radius, height)]

def bhv_disable_rendering():
    return [_BC_B(BHV_DISABLE_RENDERING)]

def bhv_scale(unused_field, percent):
    return [_BC_BBH(BHV_SCALE, unused_field, percent)]

def bhv_set_interact_type(itype):
    return [_BC_B(BHV_SET_INTERACT_TYPE), _BC_W(itype)]

def bhv_spawn_child(modelID, behavior):
    return [_BC_B(BHV_SPAWN_CHILD), _BC_W(modelID), _BC_W(id(behavior))]

def bhv_spawn_obj(modelID, behavior):
    return [_BC_B(BHV_SPAWN_OBJ), _BC_W(modelID), _BC_W(id(behavior))]

def bhv_set_random_float(field, min_val, range_val):
    return [_BC_BBH(BHV_SET_RANDOM_FLOAT, field, min_val), _BC_H(range_val)]

def bhv_set_random_int(field, min_val, range_val):
    return [_BC_BBH(BHV_SET_RANDOM_INT, field, min_val), _BC_H(range_val)]

def bhv_set_obj_physics(wall_hitbox, gravity, bounciness, drag, friction, buoyancy):
    return [_BC_B(BHV_SET_OBJ_PHYSICS),
            _BC_HH(wall_hitbox, gravity),
            _BC_HH(bounciness, drag),
            _BC_HH(friction, buoyancy),
            _BC_HH(0, 0)]

def bhv_delay_var(field):
    return [_BC_BB(BHV_DELAY_VAR, field)]

def bhv_load_collision_data(data):
    return [_BC_B(BHV_LOAD_COLLISION_DATA), _BC_W(id(data))]

def bhv_set_hitbox_with_offset(radius, height, down_offset):
    return [_BC_B(BHV_SET_HITBOX_WITH_OFFSET), _BC_HH(radius, height), _BC_H(down_offset)]

def bhv_spawn_child_with_param(bhv_param, modelID, behavior):
    return [_BC_B0H(BHV_SPAWN_CHILD_WITH_PARAM, bhv_param), _BC_W(modelID), _BC_W(id(behavior))]

def bhv_animate_texture(field, rate):
    return [_BC_BBH(BHV_ANIMATE_TEXTURE, field, rate)]

def bhv_parent_bit_clear(field, flags):
    return [_BC_BB(BHV_PARENT_BIT_CLEAR, field), _BC_W(flags)]

# --- Behavior Object ---
class BhvObject:
    _id_counter = 0

    def __init__(self, bhv_script, model_id=0, obj_list=OBJ_LIST_DEFAULT):
        BhvObject._id_counter += 1
        self.uid = BhvObject._id_counter
        self.behavior = bhv_script
        self.cur_bhv_command = 0
        self.bhv_stack = []
        self.bhv_delay_timer = 0
        self.bhv_stack_index = 0

        self.active_flags = ACTIVE_FLAG_ACTIVE
        self.parent_obj = None
        self.prev_obj = None
        self.collided_obj_interact_types = 0
        self.num_collided_objs = 0
        self.collided_objs = []

        self.oFlags = 0
        self.oDialogResponse = 0
        self.oIntangibleTimer = -1
        self.oPosX = 0.0
        self.oPosY = 0.0
        self.oPosZ = 0.0
        self.oVelX = 0.0
        self.oVelY = 0.0
        self.oVelZ = 0.0
        self.oForwardVel = 0.0
        self.oLeftVel = 0.0
        self.oUpVel = 0.0
        self.oActiveParticleFlags = 0
        self.oSoundStateID = 0
        self.oMoveAnglePitch = 0
        self.oMoveAngleYaw = 0
        self.oMoveAngleRoll = 0
        self.oFaceAnglePitch = 0
        self.oFaceAngleYaw = 0
        self.oFaceAngleRoll = 0
        self.oGraphYOffset = 0.0
        self.oGravity = -400.0
        self.oFloorHeight = 0.0
        self.oMoveFlags = 0
        self.oAnimState = 0
        self.oAngleVelPitch = 0
        self.oAngleVelYaw = 0
        self.oAngleVelRoll = 0
        self.oAnimations = None
        self.oHeldState = 0
        self.oWallHitboxRadius = 30.0
        self.oDragStrength = 1000.0
        self.oInteractType = 0
        self.oInteractStatus = 0
        self.oParentRelativePosX = 0.0
        self.oParentRelativePosY = 0.0
        self.oParentRelativePosZ = 0.0
        self.oBhvParams2ndByte = 0
        self.oAction = 0
        self.oSubAction = 0
        self.oTimer = 0
        self.oPrevAction = 0
        self.oBounciness = -50.0
        self.oDistanceToMario = 0.0
        self.oAngleToMario = 0
        self.oHomeX = 0.0
        self.oHomeY = 0.0
        self.oHomeZ = 0.0
        self.oFriction = 1000.0
        self.oBuoyancy = 200.0
        self.oOpacity = 255
        self.oDamageOrCoinValue = 0
        self.oHealth = 0
        self.oBhvParams = 0
        self.oInteractionSubtype = 0
        self.oCollisionDistance = 0.0
        self.oNumLootCoins = 0
        self.oDrawingDistance = 10000.0
        self.oRoom = -1
        self.oUnusedBhvParams = 0
        self.oWallAngle = 0
        self.oAngleToHome = 0
        self.oDeathSound = 0

        self.hitboxRadius = 0.0
        self.hitboxHeight = 0.0
        self.hurtboxRadius = 0.0
        self.hurtboxHeight = 0.0
        self.hitboxDownOffset = 0.0
        self.collisionData = None
        self.respawnInfoType = 0
        self.respawnInfo = None

        self.obj_list = obj_list
        self.model_id = model_id
        self.render_enabled = True

        # For rendering
        self.mesh_verts = []
        self.mesh_faces = []
        self.color = WHITE
        self.billboard = False

    def get_field_f32(self, index):
        mapping = {
            OPOSX: 'oPosX', OPOSY: 'oPosY', OPOSZ: 'oPosZ',
            OVELX: 'oVelX', OVELY: 'oVelY', OVELZ: 'oVelZ',
            OFORWARDVEL: 'oForwardVel', OLEFTVEL: 'oLeftVel', OUPVEL: 'oUpVel',
            OGRAPHYOFFSET: 'oGraphYOffset', OGRAVITY: 'oGravity',
            OFLOORHEIGHT: 'oFloorHeight', OBOUNCINESS: 'oBounciness',
            ODISTANCETOMARIO: 'oDistanceToMario', OHOMEX: 'oHomeX',
            OHOMEY: 'oHomeY', OHOMEZ: 'oHomeZ', OFRICTION: 'oFriction',
            OBUOYANCY: 'oBuoyancy', OCOLLISIONDISTANCE: 'oCollisionDistance',
            ODRAWINGDISTANCE: 'oDrawingDistance',
            OPARENTRELATIVEPOSX: 'oParentRelativePosX',
            OPARENTRELATIVEPOSY: 'oParentRelativePosY',
            OPARENTRELATIVEPOSZ: 'oParentRelativePosZ',
            ODRAGSTRENGTH: 'oDragStrength',
            OWALLHITBOXRADIUS: 'oWallHitboxRadius',
        }
        attr = mapping.get(index)
        if attr and hasattr(self, attr):
            return getattr(self, attr)
        return 0.0

    def set_field_f32(self, index, value):
        mapping = {
            OPOSX: 'oPosX', OPOSY: 'oPosY', OPOSZ: 'oPosZ',
            OVELX: 'oVelX', OVELY: 'oVelY', OVELZ: 'oVelZ',
            OFORWARDVEL: 'oForwardVel', OLEFTVEL: 'oLeftVel', OUPVEL: 'oUpVel',
            OGRAPHYOFFSET: 'oGraphYOffset', OGRAVITY: 'oGravity',
            OFLOORHEIGHT: 'oFloorHeight', OBOUNCINESS: 'oBounciness',
            ODISTANCETOMARIO: 'oDistanceToMario', OHOMEX: 'oHomeX',
            OHOMEY: 'oHomeY', OHOMEZ: 'oHomeZ', OFRICTION: 'oFriction',
            OBUOYANCY: 'oBuoyancy', OCOLLISIONDISTANCE: 'oCollisionDistance',
            ODRAWINGDISTANCE: 'oDrawingDistance',
            OPARENTRELATIVEPOSX: 'oParentRelativePosX',
            OPARENTRELATIVEPOSY: 'oParentRelativePosY',
            OPARENTRELATIVEPOSZ: 'oParentRelativePosZ',
            ODRAGSTRENGTH: 'oDragStrength',
            OWALLHITBOXRADIUS: 'oWallHitboxRadius',
        }
        attr = mapping.get(index)
        if attr and hasattr(self, attr):
            setattr(self, attr, value)

    def get_field_s32(self, index):
        mapping = {
            OFFLAGS: 'oFlags', OINTANGIBLETIMER: 'oIntangibleTimer',
            OMOVEANGLEPITCH: 'oMoveAnglePitch', OMOVEANGLEYAW: 'oMoveAngleYaw',
            OMOVEANGLEROLL: 'oMoveAngleRoll',
            OFACEANGLEPITCH: 'oFaceAnglePitch', OFACEANGLEYAW: 'oFaceAngleYaw',
            OFACEANGLEROLL: 'oFaceAngleRoll',
            OACTIVEPARTICLEFLAGS: 'oActiveParticleFlags',
            OMOVEFLAGS: 'oMoveFlags', OANIMSTATE: 'oAnimState',
            OANGLEVELPITCH: 'oAngleVelPitch', OANGLEVELYAW: 'oAngleVelYaw',
            OANGLEVELROLL: 'oAngleVelRoll',
            OHELDSTATE: 'oHeldState', OINTERACTTYPE: 'oInteractType',
            OINTERACTSTATUS: 'oInteractStatus',
            OBHVPARAMS2NDBYTE: 'oBhvParams2ndByte',
            OACTION: 'oAction', OSUBACTION: 'oSubAction', OTIMER: 'oTimer',
            OPREVACTION: 'oPrevAction', OINTERACTIONSUBTYPE: 'oInteractionSubtype',
            ONUMLOOTCOINS: 'oNumLootCoins', OROOM: 'oRoom',
            OOPACITY: 'oOpacity', ODAMAGEORCOINVALUE: 'oDamageOrCoinValue',
            OHEALTH: 'oHealth', OBHVPARAMS: 'oBhvParams',
            OWALLANGLE: 'oWallAngle', OANGLETOMARIO: 'oAngleToMario',
            OANGLETOHOME: 'oAngleToHome', ODEATHSOUND: 'oDeathSound',
            OUNUSEDBHVPARAMS: 'oUnusedBhvParams',
            OSOUNDSTATEID: 'oSoundStateID',
        }
        attr = mapping.get(index)
        if attr and hasattr(self, attr):
            return getattr(self, attr)
        return 0

    def set_field_s32(self, index, value):
        mapping = {
            OFFLAGS: 'oFlags', OINTANGIBLETIMER: 'oIntangibleTimer',
            OMOVEANGLEPITCH: 'oMoveAnglePitch', OMOVEANGLEYAW: 'oMoveAngleYaw',
            OMOVEANGLEROLL: 'oMoveAngleRoll',
            OFACEANGLEPITCH: 'oFaceAnglePitch', OFACEANGLEYAW: 'oFaceAngleYaw',
            OFACEANGLEROLL: 'oFaceAngleRoll',
            OACTIVEPARTICLEFLAGS: 'oActiveParticleFlags',
            OMOVEFLAGS: 'oMoveFlags', OANIMSTATE: 'oAnimState',
            OANGLEVELPITCH: 'oAngleVelPitch', OANGLEVELYAW: 'oAngleVelYaw',
            OANGLEVELROLL: 'oAngleVelRoll',
            OHELDSTATE: 'oHeldState', OINTERACTTYPE: 'oInteractType',
            OINTERACTSTATUS: 'oInteractStatus',
            OBHVPARAMS2NDBYTE: 'oBhvParams2ndByte',
            OACTION: 'oAction', OSUBACTION: 'oSubAction', OTIMER: 'oTimer',
            OPREVACTION: 'oPrevAction', OINTERACTIONSUBTYPE: 'oInteractionSubtype',
            ONUMLOOTCOINS: 'oNumLootCoins', OROOM: 'oRoom',
            OOPACITY: 'oOpacity', ODAMAGEORCOINVALUE: 'oDamageOrCoinValue',
            OHEALTH: 'oHealth', OBHVPARAMS: 'oBhvParams',
            OWALLANGLE: 'oWallAngle', OANGLETOMARIO: 'oAngleToMario',
            OANGLETOHOME: 'oAngleToHome', ODEATHSOUND: 'oDeathSound',
            OUNUSEDBHVPARAMS: 'oUnusedBhvParams',
            OSOUNDSTATEID: 'oSoundStateID',
        }
        attr = mapping.get(index)
        if attr and hasattr(self, attr):
            setattr(self, attr, int(value))

# --- Behavior Script Interpreter ---
class BhvInterpreter:
    def __init__(self):
        self.objects = []
        self.global_timer = 0
        self.native_funcs = {}

    def register_native(self, name, func):
        self.native_funcs[name] = func

    def add_object(self, obj):
        self.objects.append(obj)
        return obj

    def remove_object(self, obj):
        if obj in self.objects:
            self.objects.remove(obj)

    def get_field_ptr_f32(self, obj, index):
        if index in (OANIMATIONS,):
            return None
        return None

    def resolve_script(self, data):
        """Convert a list of word values or a list-of-lists script into a flat word array."""
        words = []
        for item in data:
            if isinstance(item, list):
                words.extend(item)
            else:
                words.append(item)
        if not hasattr(self, '_script_addr_map'):
            self._script_addr_map = {}
        self._script_addr_map[id(words)] = 0
        return words

    def _bhv_cmd_begin(self, obj, cmd, idx):
        obj_list = (cmd >> 16) & 0xFF
        obj.obj_list = obj_list
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_delay(self, obj, cmd, idx):
        num = cmd & 0xFFFF
        if obj.bhv_delay_timer < num - 1:
            obj.bhv_delay_timer += 1
        else:
            obj.bhv_delay_timer = 0
            return idx + 1, BHV_PROC_CONTINUE
        return idx, BHV_PROC_BREAK

    def _bhv_cmd_call(self, obj, cmds, idx):
        addr = cmds[idx + 1]
        obj.bhv_stack.append(idx + 2)
        return self._find_script_idx_by_addr(obj.behavior, addr), BHV_PROC_CONTINUE

    def _bhv_cmd_return(self, obj, cmds, idx):
        if obj.bhv_stack:
            return obj.bhv_stack.pop(), BHV_PROC_CONTINUE
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_goto(self, obj, cmds, idx):
        addr = cmds[idx + 1]
        return self._find_script_idx_by_addr(obj.behavior, addr), BHV_PROC_CONTINUE

    def _bhv_cmd_begin_repeat(self, obj, cmds, idx):
        count = cmds[idx] & 0xFFFF
        obj.bhv_stack.append(idx + 1)
        obj.bhv_stack.append(count)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_end_repeat(self, obj, cmds, idx):
        count = obj.bhv_stack.pop()
        count -= 1
        if count != 0:
            addr = obj.bhv_stack.pop()
            obj.bhv_stack.append(addr)
            obj.bhv_stack.append(count)
            return addr, BHV_PROC_CONTINUE
        else:
            obj.bhv_stack.pop()
            return idx + 1, BHV_PROC_BREAK

    def _bhv_cmd_end_repeat_continue(self, obj, cmds, idx):
        count = obj.bhv_stack.pop()
        count -= 1
        if count != 0:
            addr = obj.bhv_stack.pop()
            obj.bhv_stack.append(addr)
            obj.bhv_stack.append(count)
            return addr, BHV_PROC_CONTINUE
        else:
            obj.bhv_stack.pop()
            return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_begin_loop(self, obj, cmds, idx):
        obj.bhv_stack.append(idx + 1)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_end_loop(self, obj, cmds, idx):
        addr = obj.bhv_stack.pop()
        obj.bhv_stack.append(idx)
        return addr, BHV_PROC_BREAK

    def _bhv_cmd_break(self, obj, cmds, idx):
        return idx, BHV_PROC_BREAK

    def _bhv_cmd_break_unused(self, obj, cmds, idx):
        return idx, BHV_PROC_BREAK

    def _bhv_cmd_call_native(self, obj, cmds, idx):
        func_addr = cmds[idx + 1]
        func = self.native_funcs.get(func_addr)
        if func:
            func(obj)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_set_float(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = cmd & 0xFFFF
        obj.set_field_f32(field, float(value))
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_int(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = (cmd & 0xFFFF)
        if value & 0x8000:
            value -= 0x10000
        obj.set_field_s32(field, value)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_add_float(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = cmd & 0xFFFF
        obj.set_field_f32(field, obj.get_field_f32(field) + float(value))
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_add_int(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = cmd & 0xFFFF
        if value & 0x8000:
            value -= 0x10000
        obj.set_field_s32(field, obj.get_field_s32(field) + value)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_or_int(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = cmd & 0xFFFF
        obj.set_field_s32(field, obj.get_field_s32(field) | value)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_bit_clear(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        value = cmd & 0xFFFF
        obj.set_field_s32(field, obj.get_field_s32(field) & ~value)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_model(self, obj, cmds, idx):
        model_id = cmds[idx] & 0xFFFF
        obj.model_id = model_id
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_spawn_child(self, obj, cmds, idx):
        model = cmds[idx + 1]
        behavior_addr = cmds[idx + 2]
        # Find behavior script by address
        child_script = None
        for name, script in self.native_funcs.items():
            if id(script) == behavior_addr:
                child_script = script
                break
        if child_script is None:
            child_script = obj.behavior
        child = BhvObject(child_script, model)
        child.parent_obj = obj
        child.oPosX = obj.oPosX
        child.oPosY = obj.oPosY
        child.oPosZ = obj.oPosZ
        self.add_object(child)
        return idx + 3, BHV_PROC_CONTINUE

    def _bhv_cmd_deactivate(self, obj, cmds, idx):
        obj.active_flags = ACTIVE_FLAG_DEACTIVATED
        return idx, BHV_PROC_BREAK

    def _bhv_cmd_drop_to_floor(self, obj, cmds, idx):
        # Simple floor drop
        obj.oPosY = 0.0
        obj.oMoveFlags |= 1 << 1
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_billboard(self, obj, cmds, idx):
        obj.billboard = True
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_hide(self, obj, cmds, idx):
        obj.render_enabled = False
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_hitbox(self, obj, cmds, idx):
        radius = (cmds[idx + 1] >> 16) & 0xFFFF
        height = cmds[idx + 1] & 0xFFFF
        if radius & 0x8000: radius -= 0x10000
        if height & 0x8000: height -= 0x10000
        obj.hitboxRadius = float(radius)
        obj.hitboxHeight = float(height)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_set_hurtbox(self, obj, cmds, idx):
        radius = (cmds[idx + 1] >> 16) & 0xFFFF
        height = cmds[idx + 1] & 0xFFFF
        if radius & 0x8000: radius -= 0x10000
        if height & 0x8000: height -= 0x10000
        obj.hurtboxRadius = float(radius)
        obj.hurtboxHeight = float(height)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_set_home(self, obj, cmds, idx):
        obj.oHomeX = obj.oPosX
        obj.oHomeY = obj.oPosY
        obj.oHomeZ = obj.oPosZ
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_interact_type(self, obj, cmds, idx):
        obj.oInteractType = cmds[idx + 1]
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_disable_rendering(self, obj, cmds, idx):
        obj.render_enabled = False
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_scale(self, obj, cmds, idx):
        percent = cmds[idx] & 0xFFFF
        # Store scale for rendering
        obj.scale_percent = percent
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_obj_physics(self, obj, cmds, idx):
        wall_hitbox = (cmds[idx + 1] >> 16) & 0xFFFF
        gravity = cmds[idx + 1] & 0xFFFF
        bounciness = (cmds[idx + 2] >> 16) & 0xFFFF
        drag = cmds[idx + 2] & 0xFFFF
        friction = (cmds[idx + 3] >> 16) & 0xFFFF
        buoyancy = cmds[idx + 3] & 0xFFFF
        if wall_hitbox & 0x8000: wall_hitbox -= 0x10000
        if gravity & 0x8000: gravity -= 0x10000
        if bounciness & 0x8000: bounciness -= 0x10000
        if drag & 0x8000: drag -= 0x10000
        if friction & 0x8000: friction -= 0x10000
        if buoyancy & 0x8000: buoyancy -= 0x10000
        obj.oWallHitboxRadius = float(wall_hitbox)
        obj.oGravity = float(gravity) / 100.0
        obj.oBounciness = float(bounciness) / 100.0
        obj.oDragStrength = float(drag) / 100.0
        obj.oFriction = float(friction) / 100.0
        obj.oBuoyancy = float(buoyancy) / 100.0
        return idx + 5, BHV_PROC_CONTINUE

    def _bhv_cmd_animate_texture(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        rate = cmd & 0xFFFF
        if self.global_timer % rate == 0:
            obj.set_field_s32(field, obj.get_field_s32(field) + 1)
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_set_interact_subtype(self, obj, cmds, idx):
        obj.oInteractionSubtype = cmds[idx + 1]
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_set_hitbox_with_offset(self, obj, cmds, idx):
        radius = (cmds[idx + 1] >> 16) & 0xFFFF
        height = cmds[idx + 1] & 0xFFFF
        down_offset = cmds[idx + 2] & 0xFFFF
        if radius & 0x8000: radius -= 0x10000
        if height & 0x8000: height -= 0x10000
        if down_offset & 0x8000: down_offset -= 0x10000
        obj.hitboxRadius = float(radius)
        obj.hitboxHeight = float(height)
        obj.hitboxDownOffset = float(down_offset)
        return idx + 3, BHV_PROC_CONTINUE

    def _bhv_cmd_delay_var(self, obj, cmds, idx):
        field = (cmds[idx] >> 16) & 0xFF
        num = obj.get_field_s32(field)
        if obj.bhv_delay_timer < num - 1:
            obj.bhv_delay_timer += 1
        else:
            obj.bhv_delay_timer = 0
            return idx + 1, BHV_PROC_CONTINUE
        return idx, BHV_PROC_BREAK

    def _bhv_cmd_set_random_float(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        min_val = float(cmd & 0xFFFF)
        range_val = float(cmds[idx + 1] & 0xFFFF)
        obj.set_field_f32(field, range_val * random.random() + min_val)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_set_random_int(self, obj, cmds, idx):
        cmd = cmds[idx]
        field = (cmd >> 16) & 0xFF
        min_val = cmd & 0xFFFF
        range_val = cmds[idx + 1] & 0xFFFF
        obj.set_field_s32(field, int(range_val * random.random()) + min_val)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_sum_float(self, obj, cmds, idx):
        cmd = cmds[idx]
        dst = (cmd >> 16) & 0xFF
        src1 = (cmd >> 8) & 0xFF
        src2 = cmd & 0xFF
        obj.set_field_f32(dst, obj.get_field_f32(src1) + obj.get_field_f32(src2))
        return idx + 1, BHV_PROC_CONTINUE

    def _bhv_cmd_spawn_child_with_param(self, obj, cmds, idx):
        bhv_param = cmds[idx] & 0xFFFF
        model = cmds[idx + 1]
        behavior_addr = cmds[idx + 2]
        child_script = None
        for name, script in self.native_funcs.items():
            if id(script) == behavior_addr:
                child_script = script
                break
        if child_script is None:
            child_script = obj.behavior
        child = BhvObject(child_script, model)
        child.parent_obj = obj
        child.oBhvParams2ndByte = bhv_param
        child.oPosX = obj.oPosX
        child.oPosY = obj.oPosY
        child.oPosZ = obj.oPosZ
        self.add_object(child)
        return idx + 3, BHV_PROC_CONTINUE

    def _bhv_cmd_load_collision_data(self, obj, cmds, idx):
        obj.collisionData = cmds[idx + 1]
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_spawn_obj(self, obj, cmds, idx):
        model = cmds[idx + 1]
        behavior_addr = cmds[idx + 2]
        child_script = None
        for name, script in self.native_funcs.items():
            if id(script) == behavior_addr:
                child_script = script
                break
        if child_script is None:
            child_script = obj.behavior
        spawned = BhvObject(child_script, model)
        spawned.parent_obj = obj
        spawned.oPosX = obj.oPosX
        spawned.oPosY = obj.oPosY
        spawned.oPosZ = obj.oPosZ
        obj.prev_obj = spawned
        self.add_object(spawned)
        return idx + 3, BHV_PROC_CONTINUE

    def _bhv_cmd_parent_bit_clear(self, obj, cmds, idx):
        field = (cmds[idx] >> 16) & 0xFF
        value = cmds[idx + 1]
        if obj.parent_obj:
            obj.parent_obj.set_field_s32(field, obj.parent_obj.get_field_s32(field) & ~value)
        return idx + 2, BHV_PROC_CONTINUE

    def _bhv_cmd_nop(self, obj, cmds, idx):
        return idx + 1, BHV_PROC_CONTINUE

    def _find_script_idx_by_addr(self, script_words, addr):
        return self._script_addr_map.get(addr, 0) if hasattr(self, '_script_addr_map') else 0

    def _get_opcode(self, cmd):
        return (cmd >> 24) & 0xFF

    def update_object(self, obj):
        if obj.active_flags == ACTIVE_FLAG_DEACTIVATED:
            return

        script = obj.behavior
        idx = obj.cur_bhv_command

        if idx >= len(script):
            return

        if obj.oAction != obj.oPrevAction:
            obj.oTimer = 0
            obj.oSubAction = 0
            obj.oPrevAction = obj.oAction

        # Execute behavior script
        while idx < len(script):
            cmd = script[idx]
            opcode = self._get_opcode(cmd)

            if opcode == BHV_BEGIN:
                idx, result = self._bhv_cmd_begin(obj, cmd, idx)
            elif opcode == BHV_DELAY:
                idx, result = self._bhv_cmd_delay(obj, cmd, idx)
            elif opcode == BHV_CALL:
                idx, result = self._bhv_cmd_call(obj, script, idx)
            elif opcode == BHV_RETURN:
                idx, result = self._bhv_cmd_return(obj, script, idx)
            elif opcode == BHV_GOTO:
                idx, result = self._bhv_cmd_goto(obj, script, idx)
            elif opcode == BHV_BEGIN_REPEAT:
                idx, result = self._bhv_cmd_begin_repeat(obj, script, idx)
            elif opcode == BHV_END_REPEAT:
                idx, result = self._bhv_cmd_end_repeat(obj, script, idx)
            elif opcode == BHV_END_REPEAT_CONTINUE:
                idx, result = self._bhv_cmd_end_repeat_continue(obj, script, idx)
            elif opcode == BHV_BEGIN_LOOP:
                idx, result = self._bhv_cmd_begin_loop(obj, script, idx)
            elif opcode == BHV_END_LOOP:
                idx, result = self._bhv_cmd_end_loop(obj, script, idx)
            elif opcode == BHV_BREAK:
                idx, result = self._bhv_cmd_break(obj, script, idx)
            elif opcode == BHV_BREAK_UNUSED:
                idx, result = self._bhv_cmd_break_unused(obj, script, idx)
            elif opcode == BHV_CALL_NATIVE:
                idx, result = self._bhv_cmd_call_native(obj, script, idx)
            elif opcode == BHV_SET_FLOAT:
                idx, result = self._bhv_cmd_set_float(obj, script, idx)
            elif opcode == BHV_SET_INT:
                idx, result = self._bhv_cmd_set_int(obj, script, idx)
            elif opcode == BHV_ADD_FLOAT:
                idx, result = self._bhv_cmd_add_float(obj, script, idx)
            elif opcode == BHV_ADD_INT:
                idx, result = self._bhv_cmd_add_int(obj, script, idx)
            elif opcode == BHV_OR_INT:
                idx, result = self._bhv_cmd_or_int(obj, script, idx)
            elif opcode == BHV_BIT_CLEAR:
                idx, result = self._bhv_cmd_bit_clear(obj, script, idx)
            elif opcode == BHV_SET_MODEL:
                idx, result = self._bhv_cmd_set_model(obj, script, idx)
            elif opcode == BHV_SPAWN_CHILD:
                idx, result = self._bhv_cmd_spawn_child(obj, script, idx)
            elif opcode == BHV_DEACTIVATE:
                idx, result = self._bhv_cmd_deactivate(obj, script, idx)
            elif opcode == BHV_DROP_TO_FLOOR:
                idx, result = self._bhv_cmd_drop_to_floor(obj, script, idx)
            elif opcode == BHV_BILLBOARD:
                idx, result = self._bhv_cmd_billboard(obj, script, idx)
            elif opcode == BHV_HIDE:
                idx, result = self._bhv_cmd_hide(obj, script, idx)
            elif opcode == BHV_SET_HITBOX:
                idx, result = self._bhv_cmd_set_hitbox(obj, script, idx)
            elif opcode == BHV_SET_HURTBOX:
                idx, result = self._bhv_cmd_set_hurtbox(obj, script, idx)
            elif opcode == BHV_SET_HOME:
                idx, result = self._bhv_cmd_set_home(obj, script, idx)
            elif opcode == BHV_SET_INTERACT_TYPE:
                idx, result = self._bhv_cmd_set_interact_type(obj, script, idx)
            elif opcode == BHV_DISABLE_RENDERING:
                idx, result = self._bhv_cmd_disable_rendering(obj, script, idx)
            elif opcode == BHV_SCALE:
                idx, result = self._bhv_cmd_scale(obj, script, idx)
            elif opcode == BHV_SET_OBJ_PHYSICS:
                idx, result = self._bhv_cmd_set_obj_physics(obj, script, idx)
            elif opcode == BHV_ANIMATE_TEXTURE:
                idx, result = self._bhv_cmd_animate_texture(obj, script, idx)
            elif opcode == BHV_SET_INTERACT_SUBTYPE:
                idx, result = self._bhv_cmd_set_interact_subtype(obj, script, idx)
            elif opcode == BHV_SET_HITBOX_WITH_OFFSET:
                idx, result = self._bhv_cmd_set_hitbox_with_offset(obj, script, idx)
            elif opcode == BHV_DELAY_VAR:
                idx, result = self._bhv_cmd_delay_var(obj, script, idx)
            elif opcode == BHV_SET_RANDOM_FLOAT:
                idx, result = self._bhv_cmd_set_random_float(obj, script, idx)
            elif opcode == BHV_SET_RANDOM_INT:
                idx, result = self._bhv_cmd_set_random_int(obj, script, idx)
            elif opcode == BHV_SUM_FLOAT:
                idx, result = self._bhv_cmd_sum_float(obj, script, idx)
            elif opcode == BHV_SPAWN_CHILD_WITH_PARAM:
                idx, result = self._bhv_cmd_spawn_child_with_param(obj, script, idx)
            elif opcode == BHV_LOAD_COLLISION_DATA:
                idx, result = self._bhv_cmd_load_collision_data(obj, script, idx)
            elif opcode == BHV_SPAWN_OBJ:
                idx, result = self._bhv_cmd_spawn_obj(obj, script, idx)
            elif opcode == BHV_PARENT_BIT_CLEAR:
                idx, result = self._bhv_cmd_parent_bit_clear(obj, script, idx)
            elif opcode in (BHV_CMD_NOP_1, BHV_CMD_NOP_2, BHV_CMD_NOP_3, BHV_CMD_NOP_4, BHV_SET_INT_UNUSED, BHV_BEGIN_REPEAT_UNUSED):
                idx, result = self._bhv_cmd_nop(obj, script, idx)
            else:
                idx += 1
                result = BHV_PROC_CONTINUE

            if result == BHV_PROC_BREAK:
                break

        obj.cur_bhv_command = idx

        if obj.oTimer < 0x3FFFFFFF:
            obj.oTimer += 1

        if obj.oAction != obj.oPrevAction:
            obj.oTimer = 0
            obj.oSubAction = 0
            obj.oPrevAction = obj.oAction

        # Object flag processing
        flags = obj.oFlags
        if flags & OBJ_FLAG_MOVE_XZ_USING_FVEL:
            yaw_rad = math.radians((obj.oMoveAngleYaw % 65536) / 65536.0 * 360.0)
            obj.oPosX += math.sin(yaw_rad) * obj.oForwardVel * 0.05
            obj.oPosZ += math.cos(yaw_rad) * obj.oForwardVel * 0.05
        if flags & OBJ_FLAG_MOVE_Y_WITH_TERMINAL_VEL:
            obj.oVelY += obj.oGravity * 0.05
            obj.oPosY += obj.oVelY * 0.05
        if flags & OBJ_FLAG_SET_FACE_YAW_TO_MOVE_YAW:
            obj.oFaceAngleYaw = obj.oMoveAngleYaw
        if flags & OBJ_FLAG_UPDATE_GFX_POS_AND_ANGLE:
            pass

    def update_all(self):
        self.global_timer += 1
        # Update in reverse to handle removals
        for obj in self.objects[:]:
            self.update_object(obj)
        # Cleanup deactivated objects
        self.objects[:] = [o for o in self.objects if o.active_flags != ACTIVE_FLAG_DEACTIVATED]

# --- Object Manager ---
class ObjectManager:
    def __init__(self):
        self.interpreter = BhvInterpreter()
        self.models = {}  # model_id -> (verts, faces, color)

    def register_model(self, model_id, verts, faces, color=WHITE):
        self.models[model_id] = (verts, faces, color)

    def spawn(self, bhv_script, model_id=0, x=0, y=0, z=0, obj_list=OBJ_LIST_DEFAULT):
        script = self.interpreter.resolve_script(bhv_script)
        obj = BhvObject(script, model_id, obj_list)
        obj.oPosX = x
        obj.oPosY = y
        obj.oPosZ = z
        self.interpreter.add_object(obj)
        return obj

    def update_all(self):
        self.interpreter.update_all()

    def get_renderable_objects(self):
        renderable = []
        for obj in self.interpreter.objects:
            if not obj.render_enabled:
                continue
            if obj.active_flags == ACTIVE_FLAG_DEACTIVATED:
                continue
            model = self.models.get(obj.model_id)
            if model:
                verts, faces, color = model
                # Transform vertices
                if obj.billboard:
                    # Billboard objects face the camera - handled in render
                    pass
                renderable.append((obj, verts, faces, color))
        return renderable

STATE_MENU, STATE_LETTER, STATE_CASTLE, STATE_LEVEL_SEL, STATE_PLAYING, STATE_STAR_GET = range(6)

# ============================================================
# MATH ENGINE — pygame-ce + import math (FILES_OFF, no numpy)
# Vec3 / Mat4 / transforms / perspective / lighting / fog
# Tribute reimplementation — not sm64-port C decomp
# ============================================================

FOG_START = 420.0
FOG_END = 2400.0
AMBIENT = 0.32
DIFFUSE = 0.78
NEAR_CLIP = 8.0

class Vec3:
    __slots__ = ("x", "y", "z")
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)
    def __add__(self, o): return Vec3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o): return Vec3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, s): return Vec3(self.x*s, self.y*s, self.z*s)
    def __rmul__(self, s): return self.__mul__(s)
    def __truediv__(self, s): return Vec3(self.x/s, self.y/s, self.z/s)
    def dot(self, o): return self.x*o.x + self.y*o.y + self.z*o.z
    def cross(self, o):
        return Vec3(self.y*o.z-self.z*o.y, self.z*o.x-self.x*o.z, self.x*o.y-self.y*o.x)
    def length(self): return math.sqrt(self.x*self.x + self.y*self.y + self.z*self.z)
    def length_xz(self): return math.hypot(self.x, self.z)
    def normalized(self):
        L = self.length()
        return Vec3() if L < 1e-9 else self * (1.0 / L)
    def tuple(self): return (self.x, self.y, self.z)
    def copy(self): return Vec3(self.x, self.y, self.z)

def v3_add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def v3_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def v3_scale(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def v3_dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def v3_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def v3_len(a):
    return math.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])
def v3_norm(a):
    L = v3_len(a)
    return (0.0, 0.0, 0.0) if L < 1e-9 else (a[0]/L, a[1]/L, a[2]/L)

class Mat4:
    """Column-major 4x4 as 16 floats — stdlib math only."""
    __slots__ = ("m",)
    def __init__(self, m=None):
        self.m = list(m) if m is not None else [
            1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1
        ]
    @staticmethod
    def identity():
        return Mat4()
    @staticmethod
    def translate(x, y, z):
        M = Mat4.identity()
        M.m[12], M.m[13], M.m[14] = x, y, z
        return M
    @staticmethod
    def scale(sx, sy=None, sz=None):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        M = Mat4.identity()
        M.m[0], M.m[5], M.m[10] = sx, sy, sz
        return M
    @staticmethod
    def rotate_x(a):
        c, s = math.cos(a), math.sin(a)
        M = Mat4.identity()
        M.m[5], M.m[6], M.m[9], M.m[10] = c, s, -s, c
        return M
    @staticmethod
    def rotate_y(a):
        c, s = math.cos(a), math.sin(a)
        M = Mat4.identity()
        M.m[0], M.m[2], M.m[8], M.m[10] = c, -s, s, c
        return M
    @staticmethod
    def rotate_z(a):
        c, s = math.cos(a), math.sin(a)
        M = Mat4.identity()
        M.m[0], M.m[1], M.m[4], M.m[5] = c, s, -s, c
        return M
    @staticmethod
    def perspective(fov_deg, aspect, near, far):
        f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
        M = Mat4([0]*16)
        M.m[0] = f / aspect
        M.m[5] = f
        M.m[10] = (far + near) / (near - far)
        M.m[11] = -1.0
        M.m[14] = (2 * far * near) / (near - far)
        return M
    @staticmethod
    def look_at(eye, target, up=(0, 1, 0)):
        eye = Vec3(*eye) if not isinstance(eye, Vec3) else eye
        target = Vec3(*target) if not isinstance(target, Vec3) else target
        up = Vec3(*up) if not isinstance(up, Vec3) else up
        f = (target - eye).normalized()
        s = f.cross(up).normalized()
        u = s.cross(f)
        M = Mat4.identity()
        M.m[0], M.m[4], M.m[8] = s.x, s.y, s.z
        M.m[1], M.m[5], M.m[9] = u.x, u.y, u.z
        M.m[2], M.m[6], M.m[10] = -f.x, -f.y, -f.z
        M.m[12] = -s.dot(eye)
        M.m[13] = -u.dot(eye)
        M.m[14] = f.dot(eye)
        return M
    def mul(self, o):
        a, b = self.m, o.m
        out = [0.0]*16
        for col in range(4):
            for row in range(4):
                out[col*4+row] = (
                    a[0*4+row]*b[col*4+0] + a[1*4+row]*b[col*4+1] +
                    a[2*4+row]*b[col*4+2] + a[3*4+row]*b[col*4+3]
                )
        return Mat4(out)
    def transform_point(self, x, y, z, w=1.0):
        m = self.m
        X = m[0]*x + m[4]*y + m[8]*z + m[12]*w
        Y = m[1]*x + m[5]*y + m[9]*z + m[13]*w
        Z = m[2]*x + m[6]*y + m[10]*z + m[14]*w
        W = m[3]*x + m[7]*y + m[11]*z + m[15]*w
        return X, Y, Z, W

class Transform:
    """Simple transform hierarchy node (local TRS → world Mat4)."""
    def __init__(self, pos=(0,0,0), yaw=0.0, pitch=0.0, roll=0.0, scale=(1,1,1), parent=None):
        self.pos = Vec3(*pos)
        self.yaw, self.pitch, self.roll = yaw, pitch, roll
        self.scale = scale if len(scale)==3 else (scale, scale, scale)
        self.parent = parent
    def local_matrix(self):
        T = Mat4.translate(self.pos.x, self.pos.y, self.pos.z)
        Ry = Mat4.rotate_y(self.yaw)
        Rx = Mat4.rotate_x(self.pitch)
        Rz = Mat4.rotate_z(self.roll)
        S = Mat4.scale(*self.scale)
        return T.mul(Ry).mul(Rx).mul(Rz).mul(S)
    def world_matrix(self):
        M = self.local_matrix()
        if self.parent is not None:
            return self.parent.world_matrix().mul(M)
        return M

def mat3_mul_vec(m, v):
    return (
        m[0][0]*v[0] + m[0][1]*v[1] + m[0][2]*v[2],
        m[1][0]*v[0] + m[1][1]*v[1] + m[1][2]*v[2],
        m[2][0]*v[0] + m[2][1]*v[1] + m[2][2]*v[2],
    )

def mat_vec(m, v):
    return mat3_mul_vec(m, v)

def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))

def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))

def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))

def mat3_mul(a, b):
    out = [[0.0]*3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            out[i][j] = a[i][0]*b[0][j] + a[i][1]*b[1][j] + a[i][2]*b[2][j]
    return tuple(tuple(r) for r in out)

def view_basis(cam):
    return mat3_mul(rot_x(cam.pitch), rot_y(cam.yaw))

def world_to_view(x, y, z, cam):
    v = (x - cam.x, y - cam.y, z - cam.z)
    return mat3_mul_vec(view_basis(cam), v)

def camera_view_proj(cam):
    """Build view Mat4 from Lakitu cam + perspective (import math)."""
    # Forward from yaw/pitch
    cy, sy = math.cos(cam.yaw), math.sin(cam.yaw)
    cp, sp = math.cos(cam.pitch), math.sin(cam.pitch)
    # Eye looks toward target-ish direction
    fx, fy, fz = sy * cp, -sp, cy * cp
    eye = (cam.x, cam.y, cam.z)
    target = (cam.x + fx, cam.y + fy, cam.z + fz)
    view = Mat4.look_at(eye, target, (0, 1, 0))
    # Note: look_at uses -Z forward; our legacy pipeline uses +Z depth in view
    aspect = WIDTH / float(HEIGHT)
    proj = Mat4.perspective(50.0, aspect, 5.0, 4000.0)
    return view, proj

def project_point(x, y, z, cam):
    """Perspective project via math (compat: returns screen x,y + depth)."""
    # Fast path matching historical +Z view depth used by the rest of the engine
    v = world_to_view(x, y, z, cam)
    if v[2] <= NEAR_CLIP:
        return None
    return (v[0] * FOV_FACTOR / v[2] + HALF_W, -v[1] * FOV_FACTOR / v[2] + HALF_H, v[2])

def transform_mesh(verts, mat4):
    """Apply Mat4 to a list of (x,y,z) verts."""
    out = []
    for vx, vy, vz in verts:
        X, Y, Z, W = mat4.transform_point(vx, vy, vz)
        if abs(W) > 1e-8:
            out.append((X/W, Y/W, Z/W))
        else:
            out.append((X, Y, Z))
    return out

def face_normal(verts, indices):
    if len(indices) < 3:
        return (0.0, 1.0, 0.0)
    a, b, c = verts[indices[0]], verts[indices[1]], verts[indices[2]]
    return v3_norm(v3_cross(v3_sub(b, a), v3_sub(c, a)))

def shade_color(color, normal, light_dir=None):
    L = light_dir or LIGHT_DIR
    nd = max(0.0, v3_dot(v3_norm(normal), v3_norm(L)))
    # two-sided soft fill so silhouette faces stay readable
    s = AMBIENT + DIFFUSE * (0.55 * nd + 0.45 * abs(nd))
    s = max(0.22, min(1.15, s))
    return (min(255, int(color[0]*s)), min(255, int(color[1]*s)), min(255, int(color[2]*s)))

def material_kind(color):
    r, g, b = color
    if g > r + 25 and g > b + 15:
        return "grass"
    if abs(r - g) < 18 and abs(g - b) < 18 and r > 150:
        return "stone"
    if r > 120 and g > 70 and b < 90 and r > b + 40:
        return "wood"
    if b > r + 30 and b > g:
        return "water"
    if abs(r - g) < 12 and abs(g - b) < 12 and 90 <= r <= 190:
        return "metal"
    if r > 200 and g > 180 and b < 120:
        return "sand"
    return "default"

def procedural_material(color, wx, wy, wz, normal=(0, 1, 0)):
    """Math-only 'textured look': checker / gradient UV from world space."""
    kind = material_kind(color)
    u = wx * 0.035 + wz * 0.02
    v = wy * 0.05 + wx * 0.01
    checker = 1.0 if (int(math.floor(u)) + int(math.floor(v))) & 1 else 0.0
    if kind == "grass":
        mix = 0.82 + 0.18 * checker
        return (min(255, int(color[0] * mix)), min(255, int(color[1] * (0.9 + 0.15 * checker))), min(255, int(color[2] * mix)))
    if kind == "stone":
        mix = 0.78 + 0.22 * checker
        return tuple(min(255, int(c * mix)) for c in color)
    if kind == "wood":
        stripe = 0.85 + 0.15 * (1.0 if int(math.floor(wz * 0.08 + wy * 0.04)) & 1 else 0)
        return (min(255, int(color[0]*stripe)), min(255, int(color[1]*stripe)), min(255, int(color[2]*stripe)))
    if kind == "water":
        wave = 0.75 + 0.25 * (0.5 + 0.5 * math.sin(wx * 0.04 + wz * 0.05 + wy * 0.02))
        return (min(255, int(color[0]*wave)), min(255, int(color[1]*wave)), min(255, int(color[2]*(0.85+0.2*wave))))
    if kind == "metal":
        sheen = 0.7 + 0.3 * abs(normal[1])
        return tuple(min(255, int(c * sheen + 20 * abs(normal[0]))) for c in color)
    if kind == "sand":
        grain = 0.88 + 0.12 * checker
        return tuple(min(255, int(c * grain)) for c in color)
    # soft vertical gradient
    g = 0.9 + 0.1 * math.sin(wy * 0.03)
    return tuple(min(255, int(c * g)) for c in color)

def apply_fog(color, depth, fog_rgb):
    if depth <= FOG_START:
        return color
    t = min(1.0, (depth - FOG_START) / max(1.0, FOG_END - FOG_START))
    t = t * t * (3 - 2 * t)
    return (
        int(color[0] * (1 - t) + fog_rgb[0] * t),
        int(color[1] * (1 - t) + fog_rgb[1] * t),
        int(color[2] * (1 - t) + fog_rgb[2] * t),
    )

def submit_poly(rlist, verts, indices, base_color, cam, fog_rgb, normal=None):
    pts = []
    zs = 0.0
    wx = wy = wz = 0.0
    for i in indices:
        x, y, z = verts[i]
        r = project_point(x, y, z, cam)
        if not r:
            return
        pts.append((r[0], r[1]))
        zs += r[2]
        wx += x; wy += y; wz += z
    if len(pts) < 3:
        return
    n = len(indices)
    depth = zs / n
    cx, cy, cz = wx / n, wy / n, wz / n
    nrm = normal if normal is not None else face_normal(verts, indices)
    col = procedural_material(base_color, cx, cy, cz, nrm)
    col = shade_color(col, nrm)
    col = apply_fog(col, depth, fog_rgb)
    rlist.append((depth, pts, col))

def draw_sorted(surf, rlist):
    rlist.sort(key=lambda x: -x[0])
    for _, pts, color in rlist:
        pygame.draw.polygon(surf, color, pts)
        # hairline for N64-ish silhouette readability
        edge = (max(0, color[0]//3), max(0, color[1]//3), max(0, color[2]//3))
        pygame.draw.polygon(surf, edge, pts, 1)

# ============================================================
# PHYSICS — Mario moveset / collisions (FILES_OFF tribute)
# ============================================================

class Mario:
    """SM64 / sm64-port style moveset (FILES_OFF tribute physics)."""

    def __init__(self, x, z, y=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vx = self.vy = self.vz = 0.0
        self.ground_accel, self.air_accel = 1.35, 0.45
        self.max_speed, self.friction = 24.0, 0.84
        self.run_speed = 30.0
        self.gravity, self.jump_force = 1.35, 24.0
        self.double_jump_force = 28.5
        self.triple_jump_force = 35.0
        self.long_jump_force = 22.0
        self.long_jump_boost = 18.0
        self.terminal_vel = -48.0
        self.grounded = True
        self.yaw = 0.0
        self.size = 25
        self.stars_collected = 0
        self.coins = 0
        self.lives = 4
        self.health = 8
        self.floor_y = 0.0
        self.jump_combo = 0
        self.combo_timer = 0
        self.space_held = False
        self.b_held = False
        self.dive = False
        self.sliding = False
        self.pounding = False
        self.swim = False
        self.wall_kick_t = 0
        self.punch_t = 0
        self.invuln = 0
        self.cap = None  # None | "wing" | "metal" | "vanish"
        self.cap_timer = 0
        self.water_y = None  # set by world if swimming course
        self.last_vy = 0.0

    def respawn(self, x, z, y=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vx = self.vy = self.vz = 0.0
        self.grounded = True
        self.floor_y = float(y)
        self.dive = self.sliding = self.pounding = self.swim = False
        self.jump_combo = 0
        self.health = 8
        self.invuln = 60

    def hurt(self, amount=1, knock=8):
        if self.invuln > 0 or self.cap == "metal":
            return
        self.health -= amount
        self.invuln = 70
        self.vx = -math.sin(self.yaw) * knock
        self.vz = -math.cos(self.yaw) * knock
        self.vy = 12
        self.grounded = False
        play_sfx("hurt")
        if self.health <= 0:
            self.lives -= 1
            return "death"
        return None

    def give_coin(self, n=1):
        self.coins += n
        play_sfx("coin")
        while self.coins >= 100:
            self.coins -= 100
            self.lives += 1
            play_sfx("1up")

    def floor_under(self, platforms, max_top=None):
        """Highest solid top under feet; optional max_top ignores ceilings above spawn."""
        best = None
        for px, py, pz, pw, ph, pd in platforms or []:
            hw, hd = pw / 2, pd / 2
            if px - hw <= self.x <= px + hw and pz - hd <= self.z <= pz + hd:
                top = py + ph / 2
                if max_top is not None and top > max_top:
                    continue
                if best is None or top > best:
                    best = top
        return best

    def snap_to_floor(self, platforms):
        """Place Mario on the highest solid under his feet (spawn / respawn)."""
        # Prefer floors near/below current Y so ceilings are not chosen at spawn.
        best = self.floor_under(platforms, max_top=self.y + 80.0)
        if best is None:
            best = self.floor_under(platforms)
        if best is not None:
            self.y = best
            self.floor_y = best
            self.vy = 0.0
            self.grounded = True
        return best

    def update(self, keys, cam_yaw, platforms=None, walls=None):
        if self.invuln > 0:
            self.invuln -= 1
        if self.cap_timer > 0:
            self.cap_timer -= 1
            if self.cap_timer <= 0:
                self.cap = None
        if self.punch_t > 0:
            self.punch_t -= 1
        if self.wall_kick_t > 0:
            self.wall_kick_t -= 1

        mx = mz = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            mx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            mx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            mz += 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            mz -= 1

        crouch = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        b_btn = keys[pygame.K_LCTRL] or keys[pygame.K_z] or keys[pygame.K_b]
        space = keys[pygame.K_SPACE]

        # Swimming — submerged and not standing on a solid top
        land = self.floor_under(platforms)
        on_solid = land is not None and self.y >= land - 4 and self.y <= land + 24
        if self.water_y is not None and self.y < self.water_y - 10 and not on_solid:
            self.swim = True
            self.dive = self.pounding = False
            self.vy *= 0.92
            self.vy -= 0.15  # buoyant sink
            if space:
                self.vy += 1.1
            if crouch:
                self.vy -= 0.8
            accel = 0.55
            if mx or mz:
                ia = math.atan2(mx, mz)
                self.yaw = cam_yaw + ia
                self.vx += math.sin(self.yaw) * accel
                self.vz += math.cos(self.yaw) * accel
            self.vx *= 0.92
            self.vz *= 0.92
            speed = math.hypot(self.vx, self.vz)
            if speed > 14:
                self.vx *= 14 / speed
                self.vz *= 14 / speed
            self.x += self.vx
            self.y += self.vy
            self.z += self.vz
            if self.y >= self.water_y - 8:
                self.y = self.water_y - 8
                self.swim = False
            if self.y < -800:
                self.lives -= 1
                return "death"
            self.space_held = space
            self.b_held = b_btn
            return None
        else:
            self.swim = False

        # Wing cap flight
        flying = self.cap == "wing" and not self.grounded

        if mx or mz:
            ia = math.atan2(mx, mz)
            ta = cam_yaw + ia
            diff = (ta - self.yaw + math.pi) % (2 * math.pi) - math.pi
            self.yaw += diff * (0.35 if self.sliding else 0.25)
            accel = self.ground_accel if self.grounded else self.air_accel
            if flying:
                accel = 0.7
            if self.sliding:
                accel *= 0.3
            self.vx += math.sin(self.yaw) * accel
            self.vz += math.cos(self.yaw) * accel

        max_spd = self.run_speed if (not crouch and self.grounded and (mx or mz)) else self.max_speed
        if self.dive:
            max_spd = 34
        if self.cap == "metal":
            max_spd *= 0.85
        speed = math.hypot(self.vx, self.vz)
        if speed > max_spd:
            s = max_spd / speed
            self.vx *= s
            self.vz *= s

        if self.grounded and not self.sliding:
            self.vx *= self.friction
            self.vz *= self.friction
        elif self.sliding:
            self.vx *= 0.97
            self.vz *= 0.97
            if speed < 4:
                self.sliding = False

        # Gravity
        g = self.gravity
        if flying:
            g *= 0.35
            if space:
                self.vy += 0.55
        if self.cap == "metal":
            g *= 1.4
        if self.pounding:
            self.vy = min(self.vy, -42)

        self.last_vy = self.vy
        self.vy -= g
        if self.vy < self.terminal_vel:
            self.vy = self.terminal_vel

        # Wall kick detect (simple: blocked horizontal move)
        old_x, old_z = self.x, self.z
        self.x += self.vx
        self.z += self.vz
        hit_wall = False
        if platforms:
            for px, py, pz, pw, ph, pd in platforms:
                hw, hh, hd = pw / 2, ph / 2, pd / 2
                # side collision when overlapping vertically
                if abs(self.y + self.size - py) < hh + self.size:
                    if abs(self.x - px) < hw + self.size * 0.6 and abs(self.z - pz) < hd + self.size * 0.6:
                        # if we were outside on XZ before, treat as wall
                        if abs(old_x - px) >= hw + self.size * 0.55 or abs(old_z - pz) >= hd + self.size * 0.55:
                            if self.y < py + hh - 5:  # not landing on top
                                hit_wall = True
                                self.x, self.z = old_x, old_z
                                self.vx *= -0.3
                                self.vz *= -0.3
                                if not self.grounded and self.last_vy > -5:
                                    self.wall_kick_t = 12
                                break

        self.y += self.vy
        prev_y = self.y - self.vy  # position before vertical step

        self.floor_y = -9999.0
        if platforms:
            for px, py, pz, pw, ph, pd in platforms:
                hw, hd = pw / 2, pd / 2
                if px - hw <= self.x <= px + hw and pz - hd <= self.z <= pz + hd:
                    top = py + ph / 2
                    # Continuous collision: catch fast falls that would tunnel past the slab.
                    tunnel = max(24.0, abs(self.vy) + 12.0)
                    crossed = prev_y >= top - 2.0 and self.y <= top + tunnel
                    near = abs(self.y - top) <= tunnel and self.y <= top + 8
                    if self.vy <= 0.5 and (crossed or near):
                        if self.floor_y < top:
                            self.floor_y = top

        if self.floor_y > -9000 and self.y <= self.floor_y + 1.0:
            was_air = not self.grounded
            self.y = self.floor_y
            if self.pounding:
                play_sfx("pound")
                self.pounding = False
            self.vy = 0
            self.grounded = True
            self.dive = False
            if was_air and self.jump_combo > 0:
                self.combo_timer = 20
        else:
            self.grounded = False
            if self.floor_y <= -9000:
                self.floor_y = 0.0

        if self.combo_timer > 0:
            self.combo_timer -= 1
        else:
            if self.grounded:
                self.jump_combo = 0

        # Jump / long jump / wall kick
        if space and not self.space_held:
            if self.wall_kick_t > 0 and not self.grounded:
                self.vy = 26
                self.vx = math.sin(self.yaw) * 16
                self.vz = math.cos(self.yaw) * 16
                self.wall_kick_t = 0
                self.dive = False
                play_sfx("jump")
            elif self.grounded:
                speed = math.hypot(self.vx, self.vz)
                if crouch and speed > 10:
                    # long jump
                    self.vy = self.long_jump_force
                    self.vx += math.sin(self.yaw) * self.long_jump_boost
                    self.vz += math.cos(self.yaw) * self.long_jump_boost
                    self.jump_combo = 0
                    self.sliding = False
                    play_sfx("jump")
                elif self.combo_timer > 0 and self.jump_combo == 1:
                    self.vy = self.double_jump_force
                    self.jump_combo = 2
                    play_sfx("jump")
                elif self.combo_timer > 0 and self.jump_combo == 2:
                    self.vy = self.triple_jump_force
                    self.jump_combo = 3
                    self.vx *= 1.2
                    self.vz *= 1.2
                    play_sfx("jump")
                else:
                    self.vy = self.jump_force
                    self.jump_combo = 1
                    play_sfx("jump")
                self.grounded = False
                self.combo_timer = 20
                self.dive = False
                self.pounding = False
        self.space_held = space

        # B: punch / dive / slide
        if b_btn and not self.b_held:
            if self.grounded:
                if crouch or math.hypot(self.vx, self.vz) > 12:
                    self.sliding = True
                    self.vx += math.sin(self.yaw) * 8
                    self.vz += math.cos(self.yaw) * 8
                else:
                    self.punch_t = 14
            elif not self.dive:
                self.dive = True
                self.vy = max(self.vy, 5)
                self.vx += math.sin(self.yaw) * 12
                self.vz += math.cos(self.yaw) * 12
        self.b_held = b_btn

        # Ground pound
        if crouch and not self.grounded and not self.dive:
            self.pounding = True

        if self.y < -600:
            self.lives -= 1
            return "death"
        return None

    def _append_obox(self, verts, faces, ox, oy, oz, sx, sy, sz, color, yaw=None):
        """Oriented box limb in Mario local space, then yaw into world."""
        yaw = self.yaw if yaw is None else yaw
        cy, syaw = math.cos(yaw), math.sin(yaw)
        idx = len(verts)
        corners = [
            (-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
            (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz),
        ]
        for lx, ly, lz in corners:
            # local offset then rotate around Y
            rx = ox + lx
            rz = oz + lz
            wx = self.x + rx * cy + rz * syaw
            wz = self.z - rx * syaw + rz * cy
            wy = self.y + oy + ly
            verts.append((wx, wy, wz))
        for fi, n in zip(BOX_FACE_INDICES, FACE_NORMALS_BOX):
            # rotate normal by yaw
            nx = n[0] * cy + n[2] * syaw
            nz = -n[0] * syaw + n[2] * cy
            faces.append(([j + idx for j in fi], color, (nx, n[1], nz)))

    def get_mesh(self):
        """Low-poly articulated Mario (limbs/capsule body) — not a billboard."""
        verts, faces = [], []
        crouch = 0.72 if (self.sliding or self.dive or self.pounding) else 1.0
        sc = self.size / 25.0
        # Cap / metal / vanish tints
        red, blue, skin, shoe = MARIO_RED, MARIO_BLUE, (255, 200, 160), (40, 40, 50)
        if self.cap == "wing":
            red = (255, 210, 80)
        elif self.cap == "metal":
            red = blue = skin = shoe = METAL_GRAY
        elif self.cap == "vanish":
            red = (170, 210, 255); blue = (140, 180, 230); skin = (210, 230, 255)
        if self.invuln > 0 and (self.invuln // 3) % 2 == 0:
            red = blue = skin = shoe = WHITE

        # Simple run cycle / air pose
        spd = math.hypot(self.vx, self.vz)
        phase = (pygame.time.get_ticks() * 0.012 * (0.6 + min(1.5, spd * 0.05))) if self.grounded else 0.0
        swing = math.sin(phase) * (10 if self.grounded and spd > 2 else 2)
        if not self.grounded:
            swing = 14 if not self.pounding else -6
        if self.dive:
            swing = 20

        # Shoes
        self._append_obox(verts, faces, -9*sc, 4*sc*crouch, swing*0.15, 7*sc, 4*sc, 10*sc, shoe)
        self._append_obox(verts, faces, 9*sc, 4*sc*crouch, -swing*0.15, 7*sc, 4*sc, 10*sc, shoe)
        # Legs (blue)
        self._append_obox(verts, faces, -8*sc, 16*sc*crouch, swing*0.1, 6*sc, 12*sc*crouch, 6*sc, blue)
        self._append_obox(verts, faces, 8*sc, 16*sc*crouch, -swing*0.1, 6*sc, 12*sc*crouch, 6*sc, blue)
        # Torso overalls (blue) + shirt (red)
        self._append_obox(verts, faces, 0, 34*sc*crouch, 0, 14*sc, 10*sc*crouch, 9*sc, blue)
        self._append_obox(verts, faces, 0, 48*sc*crouch, 0, 13*sc, 8*sc*crouch, 8*sc, red)
        # Arms
        self._append_obox(verts, faces, -18*sc, 46*sc*crouch, -swing*0.2, 5*sc, 12*sc, 5*sc, red)
        self._append_obox(verts, faces, 18*sc, 46*sc*crouch, swing*0.2, 5*sc, 12*sc, 5*sc, red)
        # Gloves
        self._append_obox(verts, faces, -18*sc, 34*sc*crouch - swing*0.15, -swing*0.25, 5*sc, 5*sc, 5*sc, WHITE if red != METAL_GRAY else METAL_GRAY)
        self._append_obox(verts, faces, 18*sc, 34*sc*crouch + swing*0.15, swing*0.25, 5*sc, 5*sc, 5*sc, WHITE if red != METAL_GRAY else METAL_GRAY)
        # Head + nose + hat
        self._append_obox(verts, faces, 0, 66*sc*crouch, 0, 11*sc, 11*sc, 11*sc, skin)
        self._append_obox(verts, faces, 0, 64*sc*crouch, 12*sc, 4*sc, 3*sc, 4*sc, skin)
        self._append_obox(verts, faces, 0, 78*sc*crouch, 0, 13*sc, 6*sc, 13*sc, red)
        self._append_obox(verts, faces, 0, 84*sc*crouch, -2*sc, 8*sc, 4*sc, 8*sc, red)
        # Eyes
        self._append_obox(verts, faces, -4*sc, 68*sc*crouch, 10*sc, 2.2*sc, 2.5*sc, 1.5*sc, BLACK)
        self._append_obox(verts, faces, 4*sc, 68*sc*crouch, 10*sc, 2.2*sc, 2.5*sc, 1.5*sc, BLACK)
        # Mustache
        self._append_obox(verts, faces, 0, 61*sc*crouch, 11*sc, 7*sc, 2*sc, 2*sc, (60, 30, 20) if red != METAL_GRAY else METAL_GRAY)
        # Wing flaps when wing-capped
        if self.cap == "wing":
            flap = 8 + 6 * math.sin(pygame.time.get_ticks() * 0.02)
            self._append_obox(verts, faces, -22*sc, 80*sc*crouch, -flap*0.2, 3*sc, 2*sc, 16*sc, (255, 240, 200))
            self._append_obox(verts, faces, 22*sc, 80*sc*crouch, -flap*0.2, 3*sc, 2*sc, 16*sc, (255, 240, 200))
        return verts, faces


class Camera:
    """Lakitu-style follow cam with mouse look (PC port)."""

    def __init__(self, target):
        self.target = target
        self.yaw = 0.0
        self.pitch = -0.18
        self.dist = 680.0
        self.height = 320.0
        self.x = self.y = self.z = 0.0
        self.mouse_look = True

    def update(self, keys):
        # C-left / C-right (Q/E) + optional I/K pitch (C-up/down lite)
        if keys[pygame.K_q] or keys[pygame.K_LEFTBRACKET]:
            self.yaw -= 0.05
        if keys[pygame.K_e] or keys[pygame.K_RIGHTBRACKET]:
            self.yaw += 0.05
        if keys[pygame.K_i] or keys[pygame.K_PAGEUP]:
            self.pitch = max(-1.15, self.pitch - 0.03)
        if keys[pygame.K_k] or keys[pygame.K_PAGEDOWN]:
            self.pitch = min(0.4, self.pitch + 0.03)
        if keys[pygame.K_r]:
            self.dist = max(280, self.dist - 10)
        if keys[pygame.K_f]:
            self.dist = min(1200, self.dist + 10)
        if keys[pygame.K_c]:
            # C-up style: pull in / raise slightly
            self.dist = max(300, self.dist - 6)
            self.height = min(420, self.height + 4)
        else:
            self.height += (320 - self.height) * 0.04
        # mouse Lakitu look
        if self.mouse_look and pygame.mouse.get_focused():
            rel = pygame.mouse.get_rel()
            if pygame.mouse.get_pressed()[2] or keys[pygame.K_LALT]:
                self.yaw += rel[0] * 0.0045
                self.pitch = max(-1.15, min(0.4, self.pitch - rel[1] * 0.0035))
        # follow with slightly snappier lag when moving fast
        spd = math.hypot(getattr(self.target, "vx", 0), getattr(self.target, "vz", 0))
        lag = 0.14 if spd > 12 else 0.11
        tx = self.target.x - math.sin(self.yaw) * self.dist * math.cos(self.pitch)
        tz = self.target.z - math.cos(self.yaw) * self.dist * math.cos(self.pitch)
        ty = self.target.y + self.height - math.sin(self.pitch) * self.dist * 0.55
        self.x += (tx - self.x) * lag
        self.y += (ty - self.y) * lag
        self.z += (tz - self.z) * lag


class Enemy:
    """goomba / koopa / bobomb / whomp / chuckya / cheep (water) — FILES_OFF lite AI."""

    def __init__(self, x, y, z, kind="goomba"):
        self.x, self.y, self.z = x, y, z
        self.kind = kind
        self.alive = True
        self.yaw = 0.0
        self.timer = 0
        self.hp = {"whomp": 3, "chuckya": 2, "koopa": 1}.get(kind, 1)
        self.home = (x, z)
        self.shell = False

    def update(self, mario):
        if not self.alive:
            return
        self.timer += 1
        dx, dz = mario.x - self.x, mario.z - self.z
        dist = math.hypot(dx, dz) + 0.01
        if self.kind == "bobomb":
            if dist < 350:
                self.yaw = math.atan2(dx, dz)
                self.x += math.sin(self.yaw) * 2.2
                self.z += math.cos(self.yaw) * 2.2
        elif self.kind == "goomba":
            self.yaw += 0.02
            self.x = self.home[0] + math.sin(self.timer * 0.03) * 80
            self.z = self.home[1] + math.cos(self.timer * 0.03) * 80
        elif self.kind == "koopa":
            self.yaw = self.timer * 0.04
            self.x = self.home[0] + math.sin(self.timer * 0.04) * 110
            self.z = self.home[1] + math.cos(self.timer * 0.04) * 110
        elif self.kind == "chuckya":
            if dist < 220:
                self.yaw = math.atan2(dx, dz)
                self.x += math.sin(self.yaw) * 1.6
                self.z += math.cos(self.yaw) * 1.6
                if dist < 50 and self.timer % 40 == 0:
                    return mario.hurt(1, 16)
        elif self.kind == "cheep":
            # water swimmer
            wy = getattr(mario, "water_y", None) or 40
            self.y = wy - 45 + math.sin(self.timer * 0.05) * 18
            self.x = self.home[0] + math.sin(self.timer * 0.025) * 140
            self.z = self.home[1] + math.cos(self.timer * 0.025) * 140
            if dist < 45 and abs(mario.y - self.y) < 40:
                return mario.hurt(1, 8)
        elif self.kind == "whomp":
            if dist < 280 and self.timer % 90 < 20:
                if dist < 90 and mario.y < self.y + 40:
                    return mario.hurt(2, 12)
            else:
                self.yaw = math.atan2(dx, dz)

        # stomp / pound
        if dist < 55 and (mario.last_vy < -2 or mario.pounding) and mario.y > self.y - 5:
            self.hp -= 1 if not mario.pounding else 2
            mario.vy = 16
            play_sfx("pound")
            if self.kind == "koopa" and self.hp <= 0 and not self.shell:
                self.shell = True
                self.hp = 1
                return None
            if self.hp <= 0:
                self.alive = False
                mario.give_coin(3 if self.kind != "chuckya" else 5)
            return None
        # metal cap smashes
        if dist < 45 and mario.cap == "metal" and abs(mario.y - self.y) < 55:
            self.alive = False
            mario.give_coin(2)
            return None
        if dist < 40 and abs(mario.y - self.y) < 50 and not mario.pounding:
            if mario.punch_t > 0 and self.kind not in ("whomp", "chuckya"):
                self.alive = False
                mario.give_coin(1)
            elif self.kind != "cheep":
                return mario.hurt(1, 10)
        return None

    def get_mesh(self):
        if not self.alive:
            return [], []
        s = 28 if self.kind in ("whomp", "chuckya") else (14 if self.kind == "cheep" else 18)
        h = 70 if self.kind == "whomp" else (50 if self.kind == "chuckya" else (22 if self.kind == "cheep" else 28))
        cols = {
            "bobomb": DARK_GRAY, "goomba": WOOD_BROWN, "whomp": STONE_GRAY,
            "koopa": (60, 160, 60), "chuckya": (200, 120, 40), "cheep": (220, 90, 90),
        }
        col = cols.get(self.kind, STONE_GRAY)
        if self.shell:
            col = (40, 120, 40); h = 16; s = 16
        v = [(self.x-s,self.y,self.z-s),(self.x+s,self.y,self.z-s),(self.x+s,self.y,self.z+s),(self.x-s,self.y,self.z+s),
             (self.x-s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z+s),(self.x-s,self.y+h,self.z+s)]
        f = [([0,1,2,3],col),([4,5,6,7],col),([0,4,5,1],col),([2,6,7,3],col),([1,5,6,2],col),([0,4,7,3],col)]
        return v, f


class CapBlock:
    def __init__(self, x, y, z, kind="wing"):
        self.x, self.y, self.z = x, y, z
        self.kind = kind
        self.taken = False
        self.bob = 0.0

    def update(self):
        self.bob += 0.07

    def check(self, mario):
        if self.taken:
            return
        if math.hypot(mario.x - self.x, mario.z - self.z) < 50 and abs(mario.y - self.y) < 60:
            self.taken = True
            mario.cap = self.kind
            mario.cap_timer = 60 * 12  # 12 seconds
            play_sfx("cap")

    def get_mesh(self):
        if self.taken:
            return [], []
        yb = self.y + math.sin(self.bob) * 8
        colors = {"wing": (255, 200, 60), "metal": METAL_GRAY, "vanish": (160, 210, 255)}
        c = colors.get(self.kind, YELLOW)
        s = 16
        v = [(self.x-s,yb,self.z-s),(self.x+s,yb,self.z-s),(self.x+s,yb,self.z+s),(self.x-s,yb,self.z+s),
             (self.x-s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z+s),(self.x-s,yb+s*2,self.z+s)]
        f = [([0,1,2,3],c),([4,5,6,7],c),([0,4,5,1],c),([2,6,7,3],c)]
        return v, f


class Star:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.collected = False
        self.bob = 0.0

    def update(self):
        self.bob += 0.06

    def check(self, mario):
        if self.collected: return False
        dx = mario.x - self.x
        dy = mario.y - (self.y + math.sin(self.bob)*10)
        dz = mario.z - self.z
        if math.sqrt(dx*dx+dy*dy+dz*dz) < 60:
            self.collected = True
            mario.stars_collected += 1
            return True
        return False

    def get_mesh(self):
        if self.collected: return [], []
        yb = self.y + math.sin(self.bob)*10
        s = 15
        v = [(self.x,yb+s*2,self.z),(self.x-s,yb+s*0.5,self.z-s),(self.x+s,yb+s*0.5,self.z-s),
             (self.x+s,yb+s*0.5,self.z+s),(self.x-s,yb+s*0.5,self.z+s),(self.x,yb-s,self.z)]
        f = [([0,1,2],STAR_YELLOW),([0,2,3],STAR_YELLOW),([0,3,4],STAR_YELLOW),([0,4,1],STAR_YELLOW),
             ([5,2,1],GOLD),([5,3,2],GOLD),([5,4,3],GOLD),([5,1,4],GOLD)]
        return v, f


class MissionStar(Star):
    """Named course mission star (FILES_OFF tribute to SM64 mission list)."""
    def __init__(self, mid, title, x, y, z):
        super().__init__(x, y, z)
        self.mid = mid
        self.title = title


class Coin:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.collected = False
        self.spin = 0.0

    def update(self):
        self.spin += 0.08

    def check(self, mario):
        if self.collected: return False
        if math.sqrt((mario.x-self.x)**2+(mario.y-self.y)**2+(mario.z-self.z)**2) < 45:
            self.collected = True
            return True
        return False

    def get_mesh(self):
        if self.collected: return [], []
        s, w = 8, abs(math.cos(self.spin))*8+2
        v = [(self.x-w,self.y,self.z),(self.x+w,self.y,self.z),(self.x+w,self.y+s*2,self.z),(self.x-w,self.y+s*2,self.z)]
        f = [([0,1,2,3],YELLOW)]
        return v, f


class RedCoin(Coin):
    def get_mesh(self):
        if self.collected: return [], []
        s, w = 9, abs(math.cos(self.spin))*9+2
        v = [(self.x-w,self.y,self.z),(self.x+w,self.y,self.z),(self.x+w,self.y+s*2,self.z),(self.x-w,self.y+s*2,self.z)]
        f = [([0,1,2,3],MARIO_RED)]
        return v, f


class BlueCoin(Coin):
    def get_mesh(self):
        if self.collected: return [], []
        s, w = 10, abs(math.cos(self.spin))*10+2
        v = [(self.x-w,self.y,self.z),(self.x+w,self.y,self.z),(self.x+w,self.y+s*2,self.z),(self.x-w,self.y+s*2,self.z)]
        f = [([0,1,2,3],MARIO_BLUE)]
        return v, f


class OneUp:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.collected = False
        self.bob = 0.0

    def update(self):
        self.bob += 0.07

    def check(self, mario):
        if self.collected:
            return False
        if math.hypot(mario.x - self.x, mario.z - self.z) < 40 and abs(mario.y - self.y) < 50:
            self.collected = True
            mario.lives += 1
            play_sfx("1up")
            return True
        return False

    def get_mesh(self):
        if self.collected:
            return [], []
        yb = self.y + math.sin(self.bob) * 8
        s = 12
        v = [(self.x-s,yb,self.z-s),(self.x+s,yb,self.z-s),(self.x+s,yb,self.z+s),(self.x-s,yb,self.z+s),
             (self.x-s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z+s),(self.x-s,yb+s*2,self.z+s)]
        f = [([0,1,2,3],(40,180,60)),([4,5,6,7],(40,180,60)),([0,4,5,1],WHITE),([2,6,7,3],WHITE)]
        return v, f


class ItemBox:
    """? block / brick — punch or pound to spawn coin/cap/1up."""

    def __init__(self, x, y, z, contents="coin"):
        self.x, self.y, self.z = x, y, z
        self.contents = contents  # coin | red | blue | wing | metal | vanish | 1up
        self.used = False
        self.bob = 0.0

    def update(self):
        self.bob += 0.05

    def check(self, mario):
        if self.used:
            return None
        hit = math.hypot(mario.x - self.x, mario.z - self.z) < 40 and abs(mario.y - self.y) < 70
        from_below = mario.vy > 0 and mario.y < self.y + 10
        smash = mario.pounding or mario.punch_t > 0 or from_below
        if hit and smash:
            self.used = True
            play_sfx("coin")
            return self.contents
        return None

    def get_mesh(self):
        yb = self.y + (0 if self.used else math.sin(self.bob) * 3)
        s = 18
        col = (120, 90, 50) if self.used else (230, 180, 40)
        v = [(self.x-s,yb,self.z-s),(self.x+s,yb,self.z-s),(self.x+s,yb,self.z+s),(self.x-s,yb,self.z+s),
             (self.x-s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z-s),(self.x+s,yb+s*2,self.z+s),(self.x-s,yb+s*2,self.z+s)]
        f = [([0,1,2,3],col),([4,5,6,7],col),([0,4,5,1],col),([2,6,7,3],col),([1,5,6,2],col),([0,4,7,3],col)]
        return v, f


class MovingPlatform:
    def __init__(self, x, y, z, w=120, h=16, d=120, amp=120, axis="x", speed=0.03, color=None):
        self.home = (x, y, z)
        self.w, self.h, self.d = w, h, d
        self.amp, self.axis, self.speed = amp, axis, speed
        self.t = 0.0
        self.color = color or METAL_GRAY
        self.x, self.y, self.z = x, y, z

    def update(self):
        self.t += self.speed
        x, y, z = self.home
        off = math.sin(self.t) * self.amp
        if self.axis == "x":
            self.x = x + off
        elif self.axis == "y":
            self.y = y + off
        else:
            self.z = z + off

    def as_platform(self):
        return (self.x, self.y, self.z, self.w, self.h, self.d)

    def get_mesh(self):
        hw, hh, hd = self.w/2, self.h/2, self.d/2
        x, y, z = self.x, self.y, self.z
        v = [(x-hw,y-hh,z-hd),(x+hw,y-hh,z-hd),(x+hw,y+hh,z-hd),(x-hw,y+hh,z-hd),
             (x-hw,y-hh,z+hd),(x+hw,y-hh,z+hd),(x+hw,y+hh,z+hd),(x-hw,y+hh,z+hd)]
        c = self.color
        f = [([0,1,2,3],c),([4,5,6,7],c),([0,4,7,3],c),([1,5,6,2],c),([3,2,6,7],c),([0,1,5,4],c)]
        return v, f


class Cannon:
    def __init__(self, x, y, z, yaw=0.0, power=42):
        self.x, self.y, self.z = x, y, z
        self.yaw = yaw
        self.power = power
        self.cool = 0

    def update(self):
        if self.cool > 0:
            self.cool -= 1

    def try_launch(self, mario):
        if self.cool > 0:
            return False
        if math.hypot(mario.x - self.x, mario.z - self.z) < 45 and abs(mario.y - self.y) < 50 and mario.grounded:
            mario.grounded = False
            mario.vy = self.power * 0.85
            mario.vx = math.sin(self.yaw) * self.power
            mario.vz = math.cos(self.yaw) * self.power
            mario.yaw = self.yaw
            self.cool = 40
            play_sfx("pound")
            return True
        return False

    def get_mesh(self):
        s, h = 28, 36
        v = [(self.x-s,self.y,self.z-s),(self.x+s,self.y,self.z-s),(self.x+s,self.y,self.z+s),(self.x-s,self.y,self.z+s),
             (self.x-s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z+s),(self.x-s,self.y+h,self.z+s)]
        f = [([0,1,2,3],CANNON_BLACK),([4,5,6,7],CANNON_BLACK),([0,4,5,1],DARK_GRAY),([2,6,7,3],DARK_GRAY)]
        return v, f


class ClimbPole:
    def __init__(self, x, y, z, height=180):
        self.x, self.y, self.z = x, y, z
        self.height = height

    def try_climb(self, mario, keys):
        if math.hypot(mario.x - self.x, mario.z - self.z) > 28:
            return False
        if mario.y < self.y - 10 or mario.y > self.y + self.height + 20:
            return False
        # stick to pole
        mario.x += (self.x - mario.x) * 0.35
        mario.z += (self.z - mario.z) * 0.35
        mario.vx *= 0.5
        mario.vz *= 0.5
        if keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]:
            mario.vy = max(mario.vy, 6)
            mario.y = min(self.y + self.height, mario.y + 4)
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            mario.vy = min(mario.vy, -4)
        else:
            mario.vy *= 0.7
        mario.grounded = False
        return True

    def get_mesh(self):
        s = 8
        h = self.height
        v = [(self.x-s,self.y,self.z-s),(self.x+s,self.y,self.z-s),(self.x+s,self.y,self.z+s),(self.x-s,self.y,self.z+s),
             (self.x-s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z+s),(self.x-s,self.y+h,self.z+s)]
        f = [([0,1,2,3],METAL_GRAY),([4,5,6,7],METAL_GRAY),([0,4,5,1],CHAIN_GRAY),([2,6,7,3],CHAIN_GRAY)]
        return v, f


class BowserBomb:
    """Bowser's black bomb — fuse then explode (math timing)."""
    def __init__(self, x, y, z, vx=0, vz=0):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, 8.0, vz
        self.timer = 0
        self.alive = True
        self.exploded = False

    def update(self, mario):
        if not self.alive:
            return None
        self.timer += 1
        self.vy -= 0.9
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        if self.y < 0:
            self.y = 0
            self.vy *= -0.35
            self.vx *= 0.85
            self.vz *= 0.85
        # grab bomb (punch / dive near)
        dist = math.hypot(mario.x - self.x, mario.z - self.z)
        if dist < 40 and abs(mario.y - self.y) < 50 and (mario.punch_t > 0 or mario.dive):
            # Mario picks up — mark as held on mario
            mario._held_bomb = self
            self.alive = False
            play_sfx("cap")
            return "picked"
        if self.timer > 180:
            self.exploded = True
            self.alive = False
            if dist < 120:
                return mario.hurt(2, 20)
            return "boom"
        return None

    def get_mesh(self):
        if not self.alive:
            return [], []
        s = 14
        col = BLACK if self.timer < 140 or (self.timer // 4) % 2 == 0 else MARIO_RED
        v = [(self.x-s,self.y,self.z-s),(self.x+s,self.y,self.z-s),(self.x+s,self.y,self.z+s),(self.x-s,self.y,self.z+s),
             (self.x-s,self.y+s*2,self.z-s),(self.x+s,self.y+s*2,self.z-s),(self.x+s,self.y+s*2,self.z+s),(self.x-s,self.y+s*2,self.z+s)]
        f = [([0,1,2,3],col),([4,5,6,7],col),([0,4,5,1],col),([2,6,7,3],col)]
        return v, f


class BowserBoss:
    """Bowser fight closer to SM64: charge, spawn bombs, grab+spin+throw."""

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.hp = 3
        self.alive = True
        self.yaw = 0.0
        self.timer = 0
        self.home = (x, z)
        self.bombs = []
        self.grabbed = False
        self.spin = 0.0
        self.stun = 0
        self.state = "roam"  # roam | charge | stun | thrown

    def update(self, mario):
        if not self.alive:
            return None
        if not hasattr(mario, "_held_bomb"):
            mario._held_bomb = None
        self.timer += 1
        if self.stun > 0:
            self.stun -= 1

        # update bombs
        for b in list(self.bombs):
            r = b.update(mario)
            if not b.alive:
                self.bombs.remove(b)
            if r == "death":
                return "death"

        # throw held bomb at Bowser
        if mario._held_bomb is not None and (mario.punch_t == 1 or (mario.grounded and mario.b_held)):
            bomb = mario._held_bomb
            mario._held_bomb = None
            # throw along Mario yaw
            bx = mario.x + math.sin(mario.yaw) * 40
            bz = mario.z + math.cos(mario.yaw) * 40
            thrown = BowserBomb(bx, mario.y + 30, bz, math.sin(mario.yaw)*18, math.cos(mario.yaw)*18)
            thrown.timer = 100  # short fuse after throw
            self.bombs.append(thrown)
            play_sfx("pound")

        dx, dz = mario.x - self.x, mario.z - self.z
        dist = math.hypot(dx, dz) + 0.01
        self.yaw = math.atan2(dx, dz)

        # spawn bomb periodically
        if self.timer % 160 == 40 and len(self.bombs) < 3:
            ang = self.yaw + math.pi
            self.bombs.append(BowserBomb(
                self.x, self.y + 40, self.z,
                math.sin(ang) * 6, math.cos(ang) * 6
            ))

        # bomb hits Bowser → stun (grab window)
        for b in list(self.bombs):
            if b.alive and math.hypot(b.x - self.x, b.z - self.z) < 55 and b.timer > 30:
                b.alive = False
                self.stun = 90
                self.state = "stun"
                play_sfx("hurt")
                if b in self.bombs:
                    self.bombs.remove(b)

        # grab Bowser while stunned — spin with yaw, throw with punch/B
        if self.stun > 0 and dist < 65 and abs(mario.y - self.y) < 55:
            if mario.punch_t > 0 or keys_held_grab(mario):
                self.grabbed = True
                self.spin += 0.35
                # circle Mario
                self.x = mario.x + math.sin(self.spin) * 55
                self.z = mario.z + math.cos(self.spin) * 55
                self.y = mario.y + 10
                if abs(self.spin) > math.tau * 1.2 and (mario.punch_t > 0 or getattr(mario, "dive", False)):
                    # throw Bowser
                    self.grabbed = False
                    self.stun = 0
                    self.state = "thrown"
                    self.x += math.sin(mario.yaw) * 200
                    self.z += math.cos(mario.yaw) * 200
                    self.hp -= 1
                    play_sfx("pound")
                    if self.hp <= 0:
                        self.alive = False
                        play_sfx("star")
                        return "win"
                    return None

        if self.grabbed:
            return None

        if self.stun <= 0:
            self.state = "charge" if self.timer % 120 < 55 else "roam"
            if self.state == "charge":
                self.x += math.sin(self.yaw) * 3.4
                self.z += math.cos(self.yaw) * 3.4
            else:
                self.x += (self.home[0] - self.x) * 0.02
                self.z += (self.home[1] - self.z) * 0.02

        # contact
        if dist < 70 and abs(mario.y - self.y) < 60 and self.stun <= 0:
            if mario.pounding or (mario.cap == "metal" and mario.punch_t > 0):
                self.hp -= 1
                mario.vy = 20
                self.stun = 40
                play_sfx("pound")
                if self.hp <= 0:
                    self.alive = False
                    play_sfx("star")
                    return "win"
            elif mario.last_vy < -5 and mario.y > self.y + 25:
                self.stun = 50
                mario.vy = 18
                play_sfx("pound")
            else:
                return mario.hurt(2, 18)
        return None

    def get_mesh(self):
        meshes = []
        if self.alive:
            s, h = 40, 70
            col = (220, 120, 40) if self.stun > 0 else (180, 80, 30)
            v = [(self.x-s,self.y,self.z-s),(self.x+s,self.y,self.z-s),(self.x+s,self.y,self.z+s),(self.x-s,self.y,self.z+s),
                 (self.x-s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z-s),(self.x+s,self.y+h,self.z+s),(self.x-s,self.y+h,self.z+s)]
            f = [([0,1,2,3],col),([4,5,6,7],col),([0,4,5,1],(220,160,40)),([2,6,7,3],col)]
            meshes.append((v, f))
        for b in self.bombs:
            bv, bf = b.get_mesh()
            if bv:
                meshes.append((bv, bf))
        # flatten for single get_mesh API — concatenate
        if not meshes:
            return [], []
        verts, faces = [], []
        for v, f in meshes:
            base = len(verts)
            verts.extend(v)
            for indices, col in f:
                faces.append(([i+base for i in indices], col))
        return verts, faces


def keys_held_grab(mario):
    """True when Mario is trying to grab (B/Z already tracked via punch)."""
    return mario.punch_t > 0 or mario.sliding


class Enterable:
    """SM64 PC-port style door / painting / pipe / warp (FILES_OFF)."""

    def __init__(self, x, y, z, kind="door", target=None, stars_needed=0, label="",
                 radius=78, auto=False, color=None, teleport=None, keys_needed=0):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.kind = kind  # door | painting | pipe | warp | star_door | key_door
        self.target = target  # COURSE_LIST name, or None if teleport-only
        self.teleport = teleport  # optional (x, y, z) same-world warp
        self.stars_needed = int(stars_needed)
        self.keys_needed = int(keys_needed)
        self.label = label or (target or kind.title())
        self.radius = float(radius)
        self.auto = bool(auto)  # walk-into like painting/pipe
        self.color = color or DARK_BROWN
        self.pulse = 0.0

    def dist_xz(self, mario):
        return math.hypot(mario.x - self.x, mario.z - self.z)

    def in_range(self, mario):
        return self.dist_xz(mario) <= self.radius and abs(mario.y - self.y) < 140

    def in_trigger(self, mario):
        """Tighter volume for walk-into painting/pipe."""
        return self.dist_xz(mario) <= self.radius * 0.52 and abs(mario.y - self.y) < 110

    def unlocked(self, total_stars, total_keys=0):
        return total_stars >= self.stars_needed and total_keys >= self.keys_needed

    def prompt(self, total_stars, total_keys=0):
        if total_keys < self.keys_needed:
            return f"Need {self.keys_needed} Bowser key(s) — {self.label}"
        if total_stars < self.stars_needed:
            return f"Need {self.stars_needed}★ to enter — {self.label}"
        if self.kind == "painting":
            return f"Press A / walk in — {self.label}"
        if self.kind == "pipe":
            return f"Press A / enter pipe — {self.label}"
        return f"Press A to enter — {self.label}"

    def get_mesh(self, highlight=False):
        """Simple procedural marker mesh (glow when in range)."""
        pulse = 0.55 + 0.45 * abs(math.sin(self.pulse))
        base = self.color
        if highlight:
            base = (
                min(255, int(base[0] * 0.35 + 255 * 0.65 * pulse)),
                min(255, int(base[1] * 0.35 + 230 * 0.65 * pulse)),
                min(255, int(base[2] * 0.35 + 80 * 0.45 * pulse)),
            )
        verts, faces = [], []
        def box(ox, oy, oz, sx, sy, sz, col):
            idx = len(verts)
            corners = [
                (-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
                (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz),
            ]
            for lx, ly, lz in corners:
                verts.append((self.x + ox + lx, self.y + oy + ly, self.z + oz + lz))
            for fi, n in zip(BOX_FACE_INDICES, FACE_NORMALS_BOX):
                faces.append(([j + idx for j in fi], col, n))
        if self.kind == "pipe":
            box(0, 40, 0, 24, 40, 24, base if highlight else (40, 170, 70))
            box(0, 82, 0, 30, 10, 30, (30, 130, 55))
            box(0, 88, 0, 18, 4, 18, BLACK)
        elif self.kind == "painting":
            box(0, 55, 0, 42, 50, 4, base)
            box(0, 55, -8, 48, 56, 3, WOOD_BROWN)
        else:  # door / warp
            box(0, 55, 0, 32, 55, 6, base if highlight else DARK_BROWN)
            box(0, 55, 4, 28, 50, 2, (90, 60, 30))
            box(18, 50, 8, 3, 3, 3, GOLD)
        return verts, faces


class WorldBase:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.platforms = []
        self.stars = []
        self.coins = []
        self.enemies = []
        self.caps = []
        self.enterables = []
        self.red_coins = []
        self.blue_coins = []
        self.oneups = []
        self.boxes = []
        self.movers = []
        self.cannons = []
        self.poles = []
        self.bosses = []
        self.missions = []  # MissionStar named goals
        self.red_coin_star_spawned = False
        self.spawn = (0, -400)
        self.sky_color = SKY_BLUE
        self.name = "Unknown"
        self.star_count = 0
        self.water_y = None

    def add_box(self, x, y, z, w, h, d, color, collide=None):
        # Thin walkable slabs collide by default; fluids stay pass-through.
        if collide is None:
            fluids = {WATER_BLUE, DEEP_WATER, MOAT_BLUE, LAVA_RED, LAVA_ORANGE, DOCK_BLUE}
            collide = h <= 24 and min(w, d) >= 80 and color not in fluids
        idx = len(self.verts)
        hw, hh, hd = w/2, h/2, d/2
        self.verts += [(x-hw,y-hh,z-hd),(x+hw,y-hh,z-hd),(x+hw,y+hh,z-hd),(x-hw,y+hh,z-hd),
                       (x-hw,y-hh,z+hd),(x+hw,y-hh,z+hd),(x+hw,y+hh,z+hd),(x-hw,y+hh,z+hd)]
        for i, fi in enumerate(BOX_FACE_INDICES):
            self.faces.append(([j+idx for j in fi], color, FACE_NORMALS_BOX[i]))
        if collide:
            self.platforms.append((x, y, z, w, h, d))

    def add_roof(self, x, y, z, w, h, d, color):
        idx = len(self.verts)
        hw, hd = w/2, d/2
        self.verts += [(x-hw,y,z-hd),(x+hw,y,z-hd),(x+hw,y,z+hd),(x-hw,y,z+hd),(x,y+h,z)]
        for fi in [[0,1,4],[1,2,4],[2,3,4],[3,0,4]]:
            self.faces.append(([i+idx for i in fi], color, (0,1,0)))
        self.faces.append(([idx,idx+1,idx+2,idx+3], color, (0,-1,0)))

    def add_slope(self, x, y, z, w, h, d, color):
        idx = len(self.verts)
        hw, hd = w/2, d/2
        self.verts += [(x-hw,y,z-hd),(x+hw,y,z-hd),(x+hw,y,z+hd),(x-hw,y,z+hd),(x-hw,y+h,z+hd),(x+hw,y+h,z+hd)]
        for fi in [[0,1,2,3],[2,5,4,3],[0,1,5,4],[0,3,4],[1,2,5]]:
            n = (0,1,0) if fi in ([0,1,2,3],[2,5,4,3]) else (0,0,1)
            self.faces.append(([i+idx for i in fi], color, n))

    def add_star(self, x, y, z):
        self.stars.append(Star(x, y, z))
        self.star_count += 1

    def add_coins_line(self, x1, y1, z1, x2, y2, z2, count=5):
        for i in range(count):
            t = i/max(count-1,1)
            self.coins.append(Coin(x1+(x2-x1)*t, y1+(y2-y1)*t+30, z1+(z2-z1)*t))

    def add_enemy(self, x, y, z, kind="goomba"):
        self.enemies.append(Enemy(x, y, z, kind))

    def add_cap(self, x, y, z, kind="wing"):
        self.caps.append(CapBlock(x, y, z, kind))

    def add_coins_ring(self, cx, y, cz, r, count=8):
        for i in range(count):
            a = (2*math.pi*i)/count
            self.coins.append(Coin(cx+r*math.cos(a), y+30, cz+r*math.sin(a)))

    def add_tree(self, x, z, trunk_h=90, canopy_w=110, canopy_h=90):
        self.add_box(x, 30, z, 35, trunk_h, 35, TRUNK_BROWN)
        self.add_roof(x, trunk_h+20, z, canopy_w, canopy_h, canopy_w, TREE_GREEN)
        self.add_roof(x, trunk_h+60, z, canopy_w*0.7, canopy_h*0.6, canopy_w*0.7, TREE_GREEN)

    def add_enterable(self, x, y, z, kind="door", target=None, stars_needed=0, label="",
                      radius=78, auto=False, color=None, teleport=None, keys_needed=0):
        ent = Enterable(x, y, z, kind, target, stars_needed, label, radius, auto, color, teleport, keys_needed)
        self.enterables.append(ent)
        return ent

    def add_door(self, x, y, z, target=None, label="", stars_needed=None, teleport=None, color=None):
        need = STAR_GATES.get(target, 0) if stars_needed is None and target else (stars_needed or 0)
        # visual frame in world geo
        self.add_box(x, y + 55, z, 70, 110, 14, color or DARK_BROWN, collide=False)
        self.add_box(x, y + 55, z + 6, 60, 100, 4, (100, 70, 35), collide=False)
        return self.add_enterable(x, y, z, "door", target, need, label or (target or "Door"),
                                  radius=72, auto=False, color=color or DARK_BROWN, teleport=teleport)

    def add_painting(self, x, y, z, target, color=None, label="", stars_needed=None):
        need = STAR_GATES.get(target, 0) if stars_needed is None else stars_needed
        col = color or GRASS_GREEN
        self.add_box(x, y + 55, z, 88, 100, 10, col, collide=False)
        self.add_box(x, y + 55, z - 8, 100, 112, 8, WOOD_BROWN, collide=False)
        return self.add_enterable(x, y, z, "painting", target, need, label or target,
                                  radius=80, auto=True, color=col)

    def add_pipe(self, x, y, z, target=None, label="", stars_needed=0, auto=True, teleport=None):
        self.add_box(x, y + 40, z, 50, 80, 50, (40, 170, 70), collide=False)
        self.add_box(x, y + 82, z, 62, 16, 62, (30, 130, 55), collide=False)
        return self.add_enterable(x, y, z, "pipe", target, stars_needed, label or (target or "Pipe"),
                                  radius=60, auto=auto, color=(40, 170, 70), teleport=teleport)

    def add_hub_exit(self, offset_z=150):
        """Yellow-green pipe back to Castle Grounds near spawn."""
        sx, sz = self.spawn[0], self.spawn[1]
        return self.add_pipe(sx, 0, sz + offset_z, target="Castle Grounds",
                             label="Exit to Castle", stars_needed=0, auto=True)

    def add_red_coin(self, x, y, z):
        self.red_coins.append(RedCoin(x, y, z))

    def add_blue_coin(self, x, y, z):
        self.blue_coins.append(BlueCoin(x, y, z))

    def add_1up(self, x, y, z):
        self.oneups.append(OneUp(x, y, z))

    def add_item_box(self, x, y, z, contents="coin"):
        self.boxes.append(ItemBox(x, y, z, contents))

    def add_mover(self, x, y, z, w=140, h=14, d=140, amp=100, axis="x", speed=0.03, color=None):
        self.movers.append(MovingPlatform(x, y, z, w, h, d, amp, axis, speed, color))

    def add_cannon(self, x, y, z, yaw=0.0, power=42):
        self.cannons.append(Cannon(x, y, z, yaw, power))

    def add_pole(self, x, y, z, height=180):
        self.poles.append(ClimbPole(x, y, z, height))

    def add_boss(self, x, y, z):
        self.bosses.append(BowserBoss(x, y, z))

    def add_mission(self, mid, title, x, y, z):
        """Named mission star (3–6 per course)."""
        self.missions.append(MissionStar(mid, title, x, y, z))
        self.stars.append(self.missions[-1])  # also in stars list for pickup/render

    def check_red_coin_star(self):
        if self.red_coin_star_spawned:
            return
        if not self.red_coins:
            return
        if all(getattr(c, "collected", False) for c in self.red_coins):
            self.red_coin_star_spawned = True
            # spawn at centroid of red coins
            cx = sum(c.x for c in self.red_coins) / len(self.red_coins)
            cy = max(c.y for c in self.red_coins) + 60
            cz = sum(c.z for c in self.red_coins) / len(self.red_coins)
            self.add_mission("red", "8 Red Coins", cx, cy, cz)
            play_sfx("star")

    def add_star_door(self, x, y, z, target, stars_needed, label=None):
        self.add_box(x, y + 55, z, 80, 120, 18, (200, 180, 60), collide=False)
        return self.add_enterable(x, y, z, "star_door", target, stars_needed,
                                  label or f"★{stars_needed} Door", radius=75, auto=False,
                                  color=(220, 190, 50))

    def add_key_door(self, x, y, z, target, keys_needed, stars_needed=0, label=None):
        self.add_box(x, y + 55, z, 80, 120, 18, (80, 80, 100), collide=False)
        return self.add_enterable(x, y, z, "key_door", target, stars_needed,
                                  label or f"Key×{keys_needed} Door", radius=75, auto=False,
                                  color=(90, 90, 120), keys_needed=keys_needed)

    def dynamic_platforms(self):
        plats = list(self.platforms)
        for m in self.movers:
            plats.append(m.as_platform())
        return plats

    def build(self):
        pass

# ============================================================
# COURSES / HUB — castle rooms + course worlds (FILES_OFF)
# ============================================================

class CastleGrounds(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Peach's Castle"; self.sky_color = SKY_BLUE; self.spawn = (0, -720)
        self.build()
    def build(self):
        self.add_box(0,0,0,2000,10,2000,GRASS_GREEN)
        self.add_box(0,5,150,180,10,900,STONE_PATH)
        self.add_box(-1000,100,0,40,200,2000,STONE_GRAY)
        self.add_box(1000,100,0,40,200,2000,STONE_GRAY)
        self.add_box(0,100,1000,2000,200,40,STONE_GRAY)
        self.add_box(0,150,750,550,300,450,STONE_GRAY)
        self.add_box(0,350,750,160,220,160,STONE_GRAY)
        self.add_roof(0,470,750,200,160,200,ROOF_RED)
        self.add_box(-240,200,750,110,350,110,STONE_GRAY)
        self.add_roof(-240,420,750,130,110,130,ROOF_RED)
        self.add_box(240,200,750,110,350,110,STONE_GRAY)
        self.add_roof(240,420,750,130,110,130,ROOF_RED)
        self.add_box(0,-5,450,700,8,100,MOAT_BLUE)
        self.add_box(-350,-5,600,100,8,400,MOAT_BLUE)
        self.add_box(350,-5,600,100,8,400,MOAT_BLUE)
        self.add_box(0,5,450,180,14,110,WOOD_BROWN,collide=True)
        self.add_tree(-550,-450); self.add_tree(-700,300)
        self.add_tree(550,-450); self.add_tree(700,300)
        self.add_tree(-300,-600); self.add_tree(300,-600)
        self.add_coins_line(-400,0,-200,400,0,-200,8)
        self.add_coins_ring(0,0,-400,120,8)
        # Main castle door — walk/A enters courtyard (teleport closer to paintings)
        self.add_door(0, 0, 520, target=None, label="Castle Door",
                      teleport=(0, 0, 640), color=DARK_BROWN)
        # Course paintings / portals (star-gated) — walk in or Press A
        # COURSE_LIST not fully needed here; names match STAR_GATES keys
        _hub_courses = [
            ("Bob-omb Battlefield", GRASS_GREEN),
            ("Whomp's Fortress", STONE_GRAY),
            ("Jolly Roger Bay", WATER_BLUE),
            ("Cool, Cool Mountain", SNOW_WHITE),
            ("Big Boo's Haunt", MANSION_PURPLE),
            ("Hazy Maze Cave", CAVE_BROWN),
            ("Lethal Lava Land", LAVA_RED),
            ("Shifting Sand Land", SAND_YELLOW),
            ("Dire, Dire Docks", DOCK_BLUE),
            ("Snowman's Land", ICE_BLUE),
            ("Wet-Dry World", WATER_BLUE),
            ("Tall, Tall Mountain", DARK_GREEN),
            ("Tiny-Huge Island", TREE_GREEN),
            ("Tick Tock Clock", CLOCK_BEIGE),
            ("Rainbow Ride", RAINBOW_PINK),
        ]
        n = len(_hub_courses)
        for i, (cname, col) in enumerate(_hub_courses):
            t = i / max(1, n - 1)
            ang = -1.05 + 2.10 * t
            x = math.sin(ang) * 560
            z = 280 + math.cos(ang) * 120
            self.add_painting(x, 0, z, cname, color=col, label=cname)
        # Bonus warp pipe near path start
        self.add_pipe(0, 0, -500, target="Bob-omb Battlefield", label="Pipe to BoB",
                      stars_needed=0, auto=True)
        # Interior-ish lobby (teleport via castle door puts you near here)
        self.add_box(0, 5, 780, 420, 12, 320, STONE_PATH, collide=True)
        self.add_box(-220, 80, 780, 20, 160, 320, STONE_GRAY, collide=False)
        self.add_box(220, 80, 780, 20, 160, 320, STONE_GRAY, collide=False)
        self.add_box(0, 160, 940, 440, 20, 20, STONE_GRAY, collide=False)
        self.add_box(0, 90, 780, 60, 120, 10, DARK_BROWN, collide=False)
        self.add_item_box(-120, 30, 760, "wing")
        self.add_item_box(120, 30, 760, "1up")
        self.add_1up(0, 30, 860)
        self.add_red_coin(-150, 40, 820); self.add_red_coin(150, 40, 820)
        self.add_pole(-180, 5, 700, 160)
        # Star door / Bowser key doors (hub progression)
        self.add_star_door(-350, 0, 650, "Bowser in the Dark World", 8, "Dark World ★8")
        self.add_key_door(350, 0, 650, "Bowser in the Fire Sea", 1, stars_needed=30, label="Fire Sea Key×1")
        self.add_key_door(0, 0, 980, "Bowser in the Sky", 2, stars_needed=70, label="Sky Key×2")
        self.add_cannon(200, 0, -200, yaw=0.4, power=48)
        # Multi-area castle warps (rooms)
        self.add_door(-180, 0, 780, target="Castle Lobby", label="To Lobby", stars_needed=0)
        self.add_door(180, 0, 780, target="Castle Basement", label="To Basement", stars_needed=1)
        self.add_pipe(400, 0, 850, target="Castle Upstairs", label="Upstairs Pipe",
                      stars_needed=3, auto=True)

class CastleLobby(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Castle Lobby"; self.sky_color = (40, 45, 70); self.spawn = (0, -200)
        self.build()
    def build(self):
        self.add_box(0,0,0,900,10,900,STONE_PATH)
        self.add_box(0,120,0,900,20,900,STONE_GRAY,collide=False)  # ceiling visual
        for wall in [(-450,100,0,20,200,900),(450,100,0,20,200,900),(0,100,-450,900,200,20),(0,100,450,900,200,20)]:
            self.add_box(*wall, STONE_GRAY, collide=False)
        self.add_box(0,5,0,200,10,200,PARCHMENT,collide=True)
        self.add_item_box(-100,30,0,"coin"); self.add_item_box(100,30,0,"1up")
        self.add_mission("lobby1", "Lobby Treasure", 0, 80, 0)
        self.add_door(0,0,-400, target="Castle Grounds", label="Exit Grounds")
        self.add_door(0,0,400, target="Castle Basement", label="Basement Stairs", stars_needed=1)
        self.add_painting(-300,0,0,"Bob-omb Battlefield",GRASS_GREEN)
        self.add_painting(300,0,0,"Whomp's Fortress",STONE_GRAY)

class CastleBasement(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Castle Basement"; self.sky_color = SKY_CAVE; self.spawn = (0, -300)
        self.build()
    def build(self):
        self.add_box(0,0,0,1100,10,1100,CAVE_BROWN)
        self.add_box(0,-5,200,400,8,400,DEEP_WATER)
        self.add_box(-300,40,0,200,80,200,CAVE_DARK,collide=True)
        self.add_box(300,60,-100,180,40,180,STONE_GRAY,collide=True)
        self.add_mover(0,30,300, amp=100, axis="x", color=METAL_GRAY)
        self.add_enemy(-200,0,-200,"goomba"); self.add_enemy(200,0,100,"bobomb")
        self.add_mission("base1", "Basement Shine", 300, 100, -100)
        self.add_mission("base2", "Mirror Pool", 0, 40, 200)
        for i in range(8):
            a = i*0.785
            self.add_red_coin(math.cos(a)*150, 30, 200+math.sin(a)*150)
        self.add_star_door(0,0,500,"Bowser in the Dark World",8,"Dark World Gate")
        self.add_door(0,0,-450,target="Castle Lobby",label="Back to Lobby")
        self.add_hub_exit(offset_z=120)

class CastleUpstairs(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Castle Upstairs"; self.sky_color = (70, 90, 140); self.spawn = (0, -250)
        self.build()
    def build(self):
        self.add_box(0,0,0,1000,10,800,STONE_PATH)
        self.add_box(0,5,200,600,10,200,WOOD_BROWN,collide=True)
        cols = [GRASS_GREEN, WATER_BLUE, SNOW_WHITE, LAVA_RED, SAND_YELLOW, MANSION_PURPLE]
        names = ["Jolly Roger Bay","Cool, Cool Mountain","Lethal Lava Land",
                 "Shifting Sand Land","Big Boo's Haunt","Hazy Maze Cave"]
        for i,(nm,col) in enumerate(zip(names, cols)):
            x = -350 + (i%3)*350
            z = -50 + (i//3)*250
            self.add_painting(x, 0, z, nm, col)
        self.add_mission("up1", "Clock Tower Peek", 0, 80, 200)
        self.add_key_door(0,0,350,"Bowser in the Fire Sea",1,30,"Fire Sea Gate")
        self.add_door(0,0,-350,target="Castle Grounds",label="Balcony Exit")
        self.add_pole(200,0,100,200)
        self.add_item_box(-200,30,100,"wing")

class BobOmbBattlefield(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Bob-omb Battlefield"; self.sky_color = SKY_BLUE; self.spawn = (0, -800)
        self.build()
    def build(self):
        self.add_box(0,0,0,2400,10,2400,GRASS_GREEN)
        self.add_box(0,100,400,600,200,600,DARK_GREEN,collide=True)
        self.add_box(0,250,400,400,100,400,GRASS_GREEN,collide=True)
        self.add_box(0,350,400,200,100,200,DARK_GREEN,collide=True)
        self.add_roof(0,420,400,240,120,240,GRASS_GREEN)
        self.add_slope(200,5,200,150,100,300,STONE_PATH)
        self.add_box(-500,15,-300,40,80,40,WOOD_BROWN)
        self.add_box(-500,5,-300,120,12,120,DARK_GREEN)
        self.add_box(-500,80,-300,80,80,80,CHAIN_GRAY)
        self.add_box(600,0,-500,60,40,60,CANNON_BLACK)
        self.add_box(-600,0,600,60,40,60,CANNON_BLACK)
        for i in range(-6,7): self.add_box(i*80,15,-200,10,40,10,FENCE_BROWN)
        self.add_box(0,80,-100,200,12,60,WOOD_BROWN,collide=True)
        self.add_tree(-800,-600); self.add_tree(800,-600)
        self.add_tree(-700,800); self.add_tree(700,800)
        self.add_tree(-300,-700); self.add_tree(400,-500)
        self.add_box(-200,15,600,60,40,60,DARK_GRAY)
        self.add_box(300,15,700,50,35,50,DARK_GRAY)
        self.add_mission("bob1", "Big Bob-omb Battle", 0, 450, 400)
        self.add_mission("bob2", "Footrace with Koopa", -500, 100, -300)
        self.add_mission("bob3", "Cannon to the Sky", 600, 80, -500)
        self.add_mission("bob4", "Climb the Mountain", 0, 280, 400)
        self.add_mission("bob5", "Behind Chain Chomp", -200, 50, 600)
        self.add_coins_line(-300,0,-500,300,0,-500,8)
        self.add_coins_ring(0,200,400,100,8)
        self.add_coins_line(-700,0,0,-700,0,600,5)
        self.add_enemy(-200,0,200,"bobomb"); self.add_enemy(250,0,-100,"bobomb")
        self.add_enemy(-400,0,-400,"goomba"); self.add_enemy(100,0,500,"goomba")
        self.add_enemy(450,0,200,"koopa"); self.add_enemy(-550,0,100,"chuckya")
        self.add_cap(0,280,400,"wing")
        # denser BoB: ramps, movers, boxes, red coins, cannon, pole
        self.add_box(400,40,-200,200,80,200,DARK_GREEN,collide=True)
        self.add_box(-700,20,200,180,40,180,GRASS_GREEN,collide=True)
        self.add_mover(200, 60, 100, amp=160, axis="x", speed=0.035)
        self.add_mover(-100, 120, 500, amp=80, axis="y", speed=0.04, color=STONE_PATH)
        self.add_item_box(50, 40, -50, "coin")
        self.add_item_box(-250, 40, 300, "metal")
        self.add_item_box(300, 40, 400, "1up")
        for i in range(8):
            a = i * 0.785
            self.add_red_coin(math.cos(a)*220, 40, 200+math.sin(a)*220)
        self.add_blue_coin(0, 220, 400)
        self.add_cannon(600, 0, -500, yaw=-2.2, power=50)
        self.add_pole(-500, 0, -300, 200)
        self.add_1up(700, 40, 700)

class WhompsFortress(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Whomp's Fortress"; self.sky_color = SKY_BLUE; self.spawn = (0, -500)
        self.build()
    def build(self):
        self.add_box(0,0,0,1400,10,1400,STONE_GRAY)
        self.add_box(0,60,200,600,120,600,STONE_GRAY,collide=True)
        self.add_box(50,180,250,400,120,400,DARK_GRAY,collide=True)
        self.add_box(0,300,300,250,120,250,STONE_GRAY,collide=True)
        self.add_box(0,420,300,200,30,200,STONE_PATH,collide=True)
        self.add_box(-350,60,0,100,20,200,STONE_PATH,collide=True)
        self.add_box(350,120,100,100,20,200,STONE_PATH,collide=True)
        self.add_box(-250,180,350,100,20,100,STONE_PATH,collide=True)
        self.add_box(100,200,100,80,80,80,DARK_GRAY)
        self.add_box(-100,320,250,80,80,80,DARK_GRAY)
        self.add_slope(-200,0,100,120,60,200,STONE_PATH)
        self.add_slope(150,120,200,100,60,150,STONE_PATH)
        self.add_box(0,400,350,80,200,80,STONE_GRAY)
        self.add_roof(0,550,350,100,60,100,ROOF_RED)
        self.add_box(-200,250,200,180,8,40,WOOD_BROWN,collide=True)
        self.add_box(350,140,350,40,60,40,CANNON_BLACK)
        self.add_mission("wf1", "Chip Off Whomp", 0, 460, 300)
        self.add_mission("wf2", "To the Top", 0, 580, 350)
        self.add_mission("wf3", "Shoot into the Wild", -350, 90, 0)
        self.add_mission("wf4", "Red Coins on Fortress", 100, 200, 250)
        self.add_box(200, 200, 50, 100, 20, 100, STONE_PATH, collide=True)
        self.add_mover(-50, 280, 300, amp=70, axis="y")
        self.add_coins_line(-300,0,-300,300,0,-300,6)
        self.add_coins_line(-200,260,200,100,260,200,5)
        self.add_coins_ring(0,420,300,80,8)
        self.add_enemy(0,60,200,"whomp"); self.add_enemy(100,180,250,"goomba")
        self.add_cap(-250,200,350,"metal")

class JollyRogerBay(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Jolly Roger Bay"; self.sky_color = SKY_UNDERWATER; self.spawn = (0, -600); self.water_y = 40
        self.build()
    def build(self):
        self.add_box(0,0,-400,1200,10,500,SAND_YELLOW)
        self.add_box(0,-10,300,1800,8,1400,WATER_BLUE)
        self.add_box(0,-200,300,1800,10,1400,DEEP_WATER)
        self.add_box(300,-150,500,250,60,80,WOOD_BROWN)
        self.add_box(300,-120,500,200,30,60,DARK_BROWN)
        self.add_box(300,-90,500,20,100,10,WOOD_BROWN)
        self.add_box(-400,-100,700,200,120,200,CAVE_BROWN)
        self.add_box(-400,-50,700,160,60,160,CAVE_DARK)
        self.add_box(-200,-30,200,100,30,100,DARK_GRAY,collide=True)
        self.add_box(100,-20,350,80,30,80,DARK_GRAY,collide=True)
        self.add_box(0,-40,600,120,30,120,DARK_GRAY,collide=True)
        self.add_box(0,80,-650,1200,180,40,CAVE_BROWN)
        self.add_box(500,10,-300,200,14,80,WOOD_BROWN,collide=True)
        self.add_box(-300,-180,400,40,30,30,DARK_BROWN)
        self.add_box(200,-180,600,40,30,30,DARK_BROWN)
        self.add_box(500,-160,800,150,100,150,CAVE_DARK)
        self.add_star(300,-80,500); self.add_star(-400,-40,700); self.add_star(0,-30,600)
        self.add_coins_line(-400,0,-400,400,0,-400,8)
        self.add_coins_ring(0,-150,400,150,8)
        self.add_enemy(-200,0,-400,"goomba"); self.add_enemy(100,-180,600,"bobomb")
        self.add_enemy(0,-120,400,"cheep"); self.add_enemy(200,-140,550,"cheep")
        self.add_cap(500,40,-300,"metal")
        self.add_mover(0, -30, 300, amp=90, axis="x", color=WOOD_BROWN)
        self.add_item_box(500, 20, -300, "vanish")
        self.add_red_coin(300, -80, 500); self.add_red_coin(-400, -40, 700)
        self.add_blue_coin(0, -20, 600)

class CoolCoolMountain(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Cool, Cool Mountain"; self.sky_color = SKY_SNOW; self.spawn = (0, -300)
        self.build()
    def build(self):
        self.add_box(0,0,0,2000,10,2000,SNOW_WHITE)
        self.add_box(0,80,300,900,160,900,SNOW_WHITE,collide=True)
        self.add_box(0,220,350,600,120,600,ICE_BLUE,collide=True)
        self.add_box(0,360,400,350,100,350,SNOW_WHITE,collide=True)
        self.add_box(0,470,400,180,80,180,SNOW_WHITE,collide=True)
        self.add_roof(0,540,400,220,140,220,SNOW_WHITE)
        self.add_box(60,540,400,50,80,50,BRICK_RED)
        self.add_box(-500,30,-500,150,100,120,WOOD_BROWN)
        self.add_roof(-500,100,-500,180,70,150,SNOW_WHITE)
        self.add_box(-200,150,100,250,10,60,ICE_BLUE,collide=True)
        self.add_box(400,25,-300,80,60,80,SNOW_WHITE)
        self.add_box(400,65,-300,60,50,60,SNOW_WHITE)
        self.add_box(400,100,-300,40,40,40,SNOW_WHITE)
        self.add_slope(-100,160,0,200,-100,400,ICE_BLUE)
        self.add_box(300,-5,-600,500,8,400,ICE_BLUE)
        for pos in [(-700,-700),(-600,-400),(700,-600),(600,-300),(-800,500),(800,400)]:
            self.add_box(pos[0],25,pos[1],25,80,25,TRUNK_BROWN)
            self.add_roof(pos[0],80,pos[1],80,100,80,DARK_GREEN)
            self.add_roof(pos[0],140,pos[1],60,70,60,DARK_GREEN)
        self.add_star(0,560,400); self.add_star(-500,100,-500); self.add_star(400,140,-300)
        self.add_coins_line(-400,0,-200,400,0,-200,8)
        self.add_coins_ring(0,350,400,100,8)
        self.add_enemy(-200,0,100,"goomba"); self.add_enemy(300,0,-200,"bobomb")
        self.add_enemy(100,80,300,"koopa"); self.add_enemy(-300,0,-100,"chuckya")
        self.add_cap(0,500,400,"wing")
        self.add_mover(0, 200, 200, amp=70, axis="z", color=ICE_BLUE)
        self.add_item_box(-500, 40, -500, "coin")
        self.add_pole(400, 0, -300, 140)
        self.add_red_coin(0, 560, 400)

class BigBoosHaunt(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Big Boo's Haunt"; self.sky_color = SKY_MANSION; self.spawn = (0, -500)
        self.build()
    def build(self):
        self.add_box(0,0,0,2000,10,2000,MANSION_GREEN)
        self.add_box(0,150,300,500,300,400,MANSION_PURPLE)
        self.add_roof(0,350,300,550,200,450,DARK_GRAY)
        self.add_box(0,20,50,300,40,100,STONE_GRAY,collide=True)
        self.add_box(-120,60,50,20,100,20,STONE_GRAY)
        self.add_box(120,60,50,20,100,20,STONE_GRAY)
        self.add_box(0,80,100,60,100,10,DARK_BROWN)
        self.add_box(-150,200,100,60,60,10,BLACK)
        self.add_box(150,200,100,60,60,10,BLACK)
        self.add_box(-150,350,100,50,50,10,BLACK)
        self.add_box(150,350,100,50,50,10,BLACK)
        self.add_box(-350,100,300,200,200,250,MANSION_PURPLE)
        self.add_roof(-350,230,300,230,120,280,DARK_GRAY)
        self.add_box(350,100,300,200,200,250,MANSION_PURPLE)
        self.add_roof(350,230,300,230,120,280,DARK_GRAY)
        for gx,gz in [(-600,-200),(-500,-300),(-700,-100),(-550,-400),(600,-200),(500,-300),(700,-100),(550,-400)]:
            self.add_box(gx,20,gz,30,50,10,STONE_GRAY)
        self.add_box(-800,30,-500,25,120,25,DARK_BROWN)
        self.add_box(-780,100,-500,60,8,8,DARK_BROWN)
        self.add_box(800,30,-500,25,120,25,DARK_BROWN)
        self.add_box(810,90,-500,50,8,8,DARK_BROWN)
        for i in range(-4,5): self.add_box(i*120,15,-600,8,40,8,FENCE_BROWN)
        self.add_box(0,280,100,200,10,60,STONE_GRAY,collide=True)
        self.add_star(0,400,300); self.add_star(-350,220,300); self.add_star(350,220,300)
        self.add_coins_ring(0,0,-300,200,8)
        self.add_coins_line(-400,0,-200,400,0,-200,6)
        self.add_enemy(-200,0,-200,"goomba"); self.add_enemy(200,0,100,"bobomb")
        self.add_cap(0,300,100,"vanish")

class HazyMazeCave(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Hazy Maze Cave"; self.sky_color = SKY_CAVE; self.spawn = (0, -400)
        self.build()
    def build(self):
        self.add_box(0,0,0,2400,10,2400,CAVE_BROWN)
        # Ceiling — visual only (must not become a spawn floor)
        self.add_box(0,400,0,2400,10,2400,CAVE_DARK,collide=False)
        for px,pz in [(-400,-400),(400,-400),(-400,400),(400,400),(0,0)]:
            self.add_box(px,200,pz,80,400,80,CAVE_BROWN)
        self.add_box(-600,50,0,40,100,800,CAVE_DARK)
        self.add_box(600,50,0,40,100,800,CAVE_DARK)
        self.add_box(0,50,-800,1200,100,40,CAVE_DARK)
        self.add_box(-300,50,400,600,100,40,CAVE_DARK)
        self.add_box(300,50,-400,40,100,400,CAVE_DARK)
        self.add_box(-200,50,-200,40,100,400,CAVE_DARK)
        self.add_box(-700,-10,600,600,8,600,DEEP_WATER)
        self.add_box(-700,0,600,150,20,150,CAVE_BROWN,collide=True)
        self.add_box(700,0,700,200,20,200,METAL_GRAY,collide=True)
        self.add_box(700,30,700,40,60,40,METAL_GRAY)
        self.add_box(0,50,800,100,10,100,STONE_PATH,collide=True)
        self.add_box(-400,30,-600,200,15,60,STONE_PATH,collide=True)
        self.add_box(400,60,-600,200,15,60,STONE_PATH,collide=True)
        self.add_box(0,90,-600,200,15,60,STONE_PATH,collide=True)
        self.add_box(800,20,-400,60,50,60,DARK_GRAY)
        self.add_box(850,20,-500,50,40,50,DARK_GRAY)
        self.add_star(-700,40,600); self.add_star(700,50,700); self.add_star(0,110,-600)
        self.add_coins_line(-500,0,-300,500,0,-300,8)
        self.add_coins_ring(0,0,0,200,8)
        self.add_enemy(400,0,-400,"goomba"); self.add_enemy(-400,0,200,"bobomb")
        self.add_cap(700,50,700,"metal")

class LethalLavaLand(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Lethal Lava Land"; self.sky_color = SKY_LAVA; self.spawn = (0, -600)
        self.build()
    def build(self):
        self.add_box(0,-20,0,3000,10,3000,LAVA_RED)
        self.add_box(0,-15,0,3000,6,3000,LAVA_ORANGE)
        self.add_box(0,10,-600,300,40,300,DARK_GRAY,collide=True)
        for i,(px,pz) in enumerate([(-200,-300),(0,-200),(200,-100),(300,100),(100,300)]):
            self.add_box(px,20+i*10,pz,120,30,120,STONE_GRAY,collide=True)
        self.add_box(0,80,600,500,160,500,VOLCANO_GRAY,collide=True)
        self.add_box(0,200,600,300,120,300,VOLCANO_GRAY,collide=True)
        self.add_box(0,300,600,150,80,150,VOLCANO_RED,collide=True)
        self.add_roof(0,370,600,180,100,180,VOLCANO_RED)
        self.add_box(0,310,600,100,5,100,LAVA_ORANGE)
        self.add_box(-500,30,300,200,50,200,DARK_GRAY,collide=True)
        self.add_box(500,20,-300,100,20,100,METAL_GRAY,collide=True)
        self.add_box(500,20,0,100,20,100,METAL_GRAY,collide=True)
        self.add_box(-300,15,0,200,12,40,WOOD_BROWN,collide=True)
        self.add_box(600,50,300,40,40,40,YELLOW)
        self.add_star(0,400,600); self.add_star(-500,80,300); self.add_star(100,80,300)
        self.add_coins_line(-200,30,-300,300,60,100,6)
        self.add_coins_ring(0,250,600,100,8)
        self.add_enemy(-200,20,-300,"goomba"); self.add_enemy(200,30,-100,"bobomb")
        self.add_enemy(0,30,100,"koopa")
        self.add_cap(-500,60,300,"wing")
        self.add_mover(100, 40, 200, amp=100, axis="x", color=VOLCANO_GRAY)
        self.add_item_box(-500, 50, 300, "metal")
        self.add_cannon(500, 20, 0, yaw=3.0, power=45)
        self.add_red_coin(0, 400, 600)

class ShiftingSandLand(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Shifting Sand Land"; self.sky_color = SKY_DESERT; self.spawn = (0, -700)
        self.build()
    def build(self):
        self.add_box(0,0,0,3000,10,3000,SAND_YELLOW)
        self.add_box(-400,-8,0,400,6,400,DARK_BROWN)
        self.add_box(0,40,400,500,80,500,PYRAMID_TAN,collide=True)
        self.add_box(0,100,400,380,60,380,PYRAMID_TAN,collide=True)
        self.add_roof(0,160,400,420,250,420,PYRAMID_DARK)
        self.add_box(0,50,150,80,60,10,BLACK)
        self.add_box(600,-3,-500,250,8,250,WATER_BLUE)
        self.add_tree(600,-500,60,80,60); self.add_tree(650,-450,60,80,60)
        for px,pz in [(-600,400),(-700,200),(600,400),(700,200)]:
            self.add_box(px,50,pz,50,100,50,SAND_YELLOW)
        self.add_box(-600,5,-300,600,10,80,STONE_PATH)
        self.add_box(-600,20,-300,80,80,80,METAL_GRAY)
        self.add_box(700,60,700,150,120,150,SAND_YELLOW,collide=True)
        self.add_box(-200,40,-500,30,80,30,PYRAMID_DARK)
        self.add_box(200,40,-500,30,80,30,PYRAMID_DARK)
        self.add_box(0,90,-500,440,20,30,PYRAMID_DARK)
        self.add_star(0,420,400); self.add_star(700,180,700); self.add_star(-600,30,-300)
        self.add_coins_line(-400,0,-600,400,0,-600,8)
        self.add_coins_ring(0,100,400,150,8)
        self.add_enemy(-300,0,-500,"goomba"); self.add_enemy(200,0,-400,"bobomb")
        self.add_cap(700,100,700,"vanish")

class DireDireDocks(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Dire, Dire Docks"; self.sky_color = SKY_UNDERWATER; self.spawn = (0, -400); self.water_y = 30
        self.build()
    def build(self):
        self.add_box(0,0,-400,600,10,300,STONE_GRAY)
        self.add_box(0,-15,300,2000,8,1500,DOCK_BLUE)
        self.add_box(0,-300,300,2000,10,1500,DEEP_WATER)
        self.add_box(-200,10,-200,80,14,300,WOOD_BROWN,collide=True)
        self.add_box(200,10,-200,80,14,300,WOOD_BROWN,collide=True)
        self.add_box(0,-10,500,300,60,120,METAL_GRAY)
        self.add_box(0,20,500,250,40,80,DARK_GRAY)
        self.add_box(0,50,450,30,60,10,METAL_GRAY)
        for i in range(5):
            z = 200+i*150
            self.add_box(300*(1 if i%2==0 else -1),-100,z,80,8,80,YELLOW)
        self.add_box(-600,-200,600,100,20,200,DEEP_WATER)
        self.add_box(0,-280,800,100,10,100,BLACK)
        self.add_box(500,-250,700,60,50,60,METAL_GRAY)
        self.add_box(-500,-200,800,60,60,60,DARK_GREEN)
        self.add_box(-400,-20,200,120,30,120,STONE_GRAY,collide=True)
        self.add_box(400,-30,400,100,30,100,STONE_GRAY,collide=True)
        self.add_star(0,60,500); self.add_star(-600,-160,600); self.add_star(500,-200,700)
        self.add_coins_line(-200,0,-400,200,0,-400,6)
        self.add_coins_ring(0,-100,400,200,8)
        self.add_enemy(-200,0,-300,"goomba"); self.add_enemy(150,-100,300,"bobomb")
        self.add_cap(-400,20,200,"metal")

class SnowmansLand(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Snowman's Land"; self.sky_color = SKY_SNOW; self.spawn = (0, -600)
        self.build()
    def build(self):
        self.add_box(0,0,0,2400,10,2400,SNOW_WHITE)
        self.add_box(0,60,500,300,120,300,SNOW_WHITE,collide=True)
        self.add_box(0,170,500,220,100,220,SNOW_WHITE,collide=True)
        self.add_box(0,270,500,140,80,140,SNOW_WHITE,collide=True)
        self.add_box(0,330,500,160,15,160,BLACK)
        self.add_box(0,350,500,100,40,100,BLACK)
        self.add_box(-30,290,428,20,20,5,BLACK)
        self.add_box(30,290,428,20,20,5,BLACK)
        self.add_box(0,270,425,10,10,30,LAVA_ORANGE)
        self.add_box(-500,-5,-300,500,8,500,ICE_BLUE)
        self.add_box(500,30,-400,160,80,160,SNOW_WHITE)
        self.add_roof(500,90,-400,180,60,180,SNOW_WHITE)
        self.add_box(500,30,-320,50,50,10,DARK_BROWN)
        self.add_box(-300,30,200,100,15,100,ICE_BLUE,collide=True)
        self.add_box(-500,60,300,100,15,100,ICE_BLUE,collide=True)
        self.add_box(-700,90,200,100,15,100,ICE_BLUE,collide=True)
        self.add_box(600,30,500,200,15,200,ICE_BLUE,collide=True)
        for tx,tz in [(-800,-600),(-700,700),(800,-500),(700,600),(-400,-700),(400,-600)]:
            self.add_box(tx,25,tz,22,70,22,TRUNK_BROWN)
            self.add_roof(tx,70,tz,70,90,70,SNOW_WHITE)
        self.add_star(0,380,500); self.add_star(500,80,-400); self.add_star(-700,120,200)
        self.add_coins_line(-400,0,-500,400,0,-500,8)
        self.add_coins_ring(0,100,500,120,8)
        self.add_enemy(-300,0,-200,"goomba"); self.add_enemy(250,0,100,"bobomb")
        self.add_cap(600,50,500,"wing")

class WetDryWorld(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Wet-Dry World"; self.sky_color = SKY_BLUE; self.spawn = (0, -400); self.water_y = 50
        self.build()
    def build(self):
        self.add_box(0,0,0,1800,10,1800,STONE_GRAY)
        self.add_box(0,30,0,1800,5,1800,WATER_BLUE)
        self.add_box(-400,100,300,200,200,200,STONE_GRAY,collide=True)
        self.add_box(-400,230,300,160,60,160,DARK_GRAY,collide=True)
        self.add_box(400,80,300,180,160,180,STONE_GRAY,collide=True)
        self.add_box(400,190,300,140,50,140,DARK_GRAY,collide=True)
        self.add_box(0,120,500,150,240,150,STONE_GRAY,collide=True)
        self.add_box(0,280,500,110,60,110,DARK_GRAY,collide=True)
        self.add_box(-200,40,-200,30,30,30,PURPLE)
        self.add_box(300,120,-100,30,30,30,PURPLE)
        self.add_box(0,250,500,30,30,30,PURPLE)
        self.add_box(-600,80,-300,250,160,250,METAL_GRAY)
        self.add_box(-600,170,-300,200,10,200,METAL_GRAY,collide=True)
        self.add_box(-200,60,0,150,8,60,WOOD_BROWN,collide=True)
        self.add_box(100,90,100,150,8,60,WOOD_BROWN,collide=True)
        self.add_box(-100,120,200,150,8,60,WOOD_BROWN,collide=True)
        self.add_box(600,50,0,80,8,80,YELLOW,collide=True)
        self.add_box(600,120,200,80,8,80,YELLOW,collide=True)
        self.add_box(0,50,-900,1800,100,30,STONE_GRAY)
        self.add_box(-900,50,0,30,100,1800,STONE_GRAY)
        self.add_box(900,50,0,30,100,1800,STONE_GRAY)
        self.add_star(0,340,500); self.add_star(-600,190,-300); self.add_star(600,140,200)
        self.add_coins_line(-500,0,-600,500,0,-600,8)
        self.add_coins_ring(0,60,0,150,8)
        self.add_enemy(-200,0,-200,"goomba"); self.add_enemy(200,40,0,"bobomb")
        self.add_cap(600,90,200,"metal")

class TallTallMountain(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Tall, Tall Mountain"; self.sky_color = SKY_BLUE; self.spawn = (0, -400)
        self.build()
    def build(self):
        self.add_box(0,0,0,1600,10,1600,GRASS_GREEN)
        self.add_box(0,50,300,700,100,700,DARK_GREEN,collide=True)
        self.add_box(50,140,350,550,80,550,GRASS_GREEN,collide=True)
        self.add_box(0,220,400,400,80,400,DARK_GREEN,collide=True)
        self.add_box(-30,300,400,300,60,300,GRASS_GREEN,collide=True)
        self.add_box(0,370,400,200,50,200,DARK_GREEN,collide=True)
        self.add_box(0,430,400,120,40,120,GRASS_GREEN,collide=True)
        self.add_box(0,150,700,700,300,30,CAVE_BROWN)
        self.add_box(250,200,695,60,300,10,WATER_BLUE)
        self.add_box(-300,80,-200,30,80,30,STONE_GRAY)
        self.add_box(-300,110,-200,80,10,80,MARIO_RED,collide=True)
        self.add_box(-100,130,-100,30,120,30,STONE_GRAY)
        self.add_box(-100,170,-100,80,10,80,MARIO_RED,collide=True)
        self.add_box(40,460,400,50,60,50,DARK_BROWN)
        self.add_box(200,180,200,250,8,40,WOOD_BROWN,collide=True)
        self.add_box(-200,100,200,180,12,30,WOOD_BROWN,collide=True)
        self.add_box(-400,350,0,100,15,100,WHITE,collide=True)
        self.add_box(-200,400,100,100,15,100,WHITE,collide=True)
        self.add_tree(-600,-500); self.add_tree(600,-500)
        self.add_tree(-500,-300); self.add_tree(500,-200)
        self.add_star(0,480,400); self.add_star(-200,420,100); self.add_star(-300,130,-200)
        self.add_coins_line(-400,0,-400,400,0,-400,8)
        self.add_coins_ring(0,300,400,100,8)
        self.add_enemy(-200,50,300,"goomba"); self.add_enemy(100,140,350,"bobomb")
        self.add_cap(-400,380,0,"wing")

class TinyHugeIsland(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Tiny-Huge Island"; self.sky_color = SKY_BLUE; self.spawn = (0, -600)
        self.build()
    def build(self):
        self.add_box(0,0,0,2200,10,2200,GRASS_GREEN)
        self.add_box(0,80,300,500,160,500,DARK_GREEN,collide=True)
        self.add_box(0,200,300,300,100,300,GRASS_GREEN,collide=True)
        self.add_roof(0,300,300,350,150,350,DARK_GREEN)
        self.add_box(0,-3,-700,800,8,300,SAND_YELLOW)
        self.add_box(0,-8,-900,800,6,200,WATER_BLUE)
        self.add_box(-400,10,-300,20,15,20,DARK_BROWN)
        self.add_box(-400,20,-300,25,8,25,MARIO_RED)
        self.add_box(-600,10,400,60,50,60,DARK_GREEN)
        self.add_box(600,10,-400,60,50,60,DARK_GREEN)
        self.add_box(300,150,500,120,80,120,CAVE_BROWN)
        self.add_box(300,150,500,80,60,80,CAVE_DARK)
        self.add_box(-500,5,-500,250,10,250,STONE_PATH)
        self.add_box(400,20,-200,80,40,80,STONE_GRAY)
        self.add_roof(400,50,-200,100,30,100,ROOF_RED)
        self.add_box(500,15,-100,60,30,60,STONE_GRAY)
        self.add_roof(500,35,-100,80,25,80,ROOF_RED)
        for px,pz in [(-200,200),(-100,350),(200,150)]:
            self.add_box(px,15,pz,15,40,15,DARK_GREEN)
            self.add_box(px,40,pz,30,15,30,MARIO_RED)
        self.add_box(-700,-5,700,300,6,300,WATER_BLUE)
        self.add_tree(-800,-200); self.add_tree(800,-300)
        self.add_tree(-300,700); self.add_tree(500,700)
        self.add_star(0,400,300); self.add_star(300,200,500); self.add_star(-600,60,400)
        self.add_coins_line(-600,0,-300,600,0,-300,10)
        self.add_coins_ring(0,100,300,120,8)
        self.add_enemy(-300,0,-200,"goomba"); self.add_enemy(200,0,100,"bobomb")
        self.add_cap(-400,40,-300,"vanish")

class TickTockClock(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Tick Tock Clock"; self.sky_color = SKY_CAVE; self.spawn = (0, -200)
        self.build()
    def build(self):
        self.add_box(0,0,0,600,10,600,CLOCK_BEIGE)
        self.add_box(-300,400,0,20,800,600,CLOCK_BEIGE)
        self.add_box(300,400,0,20,800,600,CLOCK_BEIGE)
        self.add_box(0,400,-300,600,800,20,CLOCK_BEIGE)
        self.add_box(0,400,300,600,800,20,CLOCK_BEIGE)
        platforms_data = [
            (0,40,0,200,12,200),(-100,100,50,150,10,60),(100,170,-50,150,10,60),
            (0,240,100,120,10,120),(-80,310,-80,100,10,100),(80,380,80,100,10,100),
            (0,450,0,150,10,80),(-100,520,100,100,10,100),(100,590,-100,100,10,100),
            (0,660,0,180,10,180),(0,740,0,250,10,250),
        ]
        for px,py,pz,pw,ph,pd in platforms_data:
            self.add_box(px,py,pz,pw,ph,pd,METAL_GRAY,collide=True)
        for gy in [150,350,550]:
            self.add_box(-280,gy,0,15,80,80,GOLD)
            self.add_box(280,gy,0,15,80,80,GOLD)
        self.add_box(0,300,-280,10,200,10,METAL_GRAY)
        self.add_box(0,200,-280,40,40,10,GOLD)
        self.add_box(0,780,0,280,10,280,WHITE)
        self.add_box(0,790,0,120,4,12,BLACK)
        self.add_box(0,790,0,8,4,80,BLACK)
        for i in range(12):
            a = (2*math.pi*i)/12
            self.add_box(math.sin(a)*120,790,math.cos(a)*120,15,6,15,BLACK)
        self.add_star(0,800,0); self.add_star(0,470,0); self.add_star(-100,530,100)
        self.add_coins_line(-100,100,0,100,100,0,4)
        self.add_coins_ring(0,450,0,60,6)
        self.add_coins_ring(0,740,0,100,8)
        self.add_enemy(0,40,0,"goomba"); self.add_enemy(80,380,80,"bobomb")
        self.add_cap(0,770,0,"metal")

class RainbowRide(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Rainbow Ride"; self.sky_color = SKY_RAINBOW; self.spawn = (0, -300)
        self.build()
    def build(self):
        self.add_box(0,0,-300,250,15,250,STONE_GRAY,collide=True)
        rcolors = [MARIO_RED,LAVA_ORANGE,YELLOW,GRASS_GREEN,SKY_BLUE,PURPLE,RAINBOW_PINK]
        for i in range(14):
            c = rcolors[i%len(rcolors)]
            self.add_box(math.sin(i*0.5)*150,i*15,i*100,80,8,80,c,collide=True)
        self.add_box(-300,200,800,250,50,100,WOOD_BROWN,collide=True)
        self.add_box(-300,230,800,200,30,70,DARK_BROWN)
        self.add_box(-300,270,800,10,100,10,WOOD_BROWN)
        self.add_box(-300,340,800,80,5,40,WHITE)
        self.add_box(400,250,600,180,120,150,STONE_GRAY,collide=True)
        self.add_roof(400,340,600,220,80,180,ROOF_RED)
        self.add_box(400,270,525,40,60,5,DARK_BROWN)
        self.add_box(-500,100,300,150,20,150,GRASS_GREEN,collide=True)
        self.add_box(500,150,400,120,20,120,GRASS_GREEN,collide=True)
        self.add_box(-200,300,1000,100,20,100,GRASS_GREEN,collide=True)
        self.add_box(200,80,200,80,8,80,RAINBOW_CYAN,collide=True)
        self.add_box(300,120,300,80,8,80,RAINBOW_LIME,collide=True)
        self.add_box(200,160,400,80,8,80,RAINBOW_PINK,collide=True)
        self.add_box(-400,150,500,100,8,60,WOOD_BROWN,collide=True)
        self.add_box(-100,200,700,100,8,60,WOOD_BROWN,collide=True)
        self.add_box(-600,80,100,50,40,50,CANNON_BLACK)
        for cx,cy,cz in [(300,400,300),(-200,350,600),(0,450,900)]:
            self.add_box(cx,cy,cz,120,20,80,WHITE)
        self.add_star(-300,320,800); self.add_star(400,380,600); self.add_star(-200,330,1000)
        for i in range(7):
            self.coins.append(Coin(math.sin(i*0.5)*150,i*15+30,i*100))
        self.add_coins_ring(-300,250,800,80,8)
        self.add_enemy(0,0,-250,"goomba"); self.add_enemy(150,30,100,"bobomb")
        self.add_cap(400,360,600,"wing")


class BowserDarkWorld(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Bowser in the Dark World"; self.sky_color = SKY_MANSION; self.spawn = (0, -500)
        self.build()
    def build(self):
        self.add_box(0,0,0,1600,10,1600,CAVE_DARK)
        self.add_box(0,20,-400,300,40,300,STONE_GRAY,collide=True)
        for i,z in enumerate(range(-200, 500, 120)):
            self.add_box((-1)**i * 150, 30+i*8, z, 140, 24, 140, STONE_PATH, collide=True)
        self.add_box(0,40,600,500,50,500,DARK_GRAY,collide=True)
        self.add_boss(0, 50, 600)
        self.add_star(0, 120, 600)
        self.add_item_box(-200, 50, 500, "metal")
        self.add_enemy(-100,0,0,"goomba"); self.add_enemy(100,0,100,"bobomb")
        self.add_mover(0, 80, 200, amp=60, axis="y")

class BowserFireSea(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Bowser in the Fire Sea"; self.sky_color = SKY_LAVA; self.spawn = (0, -550)
        self.build()
    def build(self):
        self.add_box(0,-15,0,2200,8,2200,LAVA_RED)
        self.add_box(0,10,-500,280,30,280,VOLCANO_GRAY,collide=True)
        for i,(x,z) in enumerate([(-200,-200),(0,-50),(200,100),(0,280),(-150,450)]):
            self.add_box(x, 25+i*6, z, 130, 28, 130, STONE_GRAY, collide=True)
        self.add_box(0,50,650,420,40,420,VOLCANO_GRAY,collide=True)
        self.add_boss(0, 60, 650)
        self.add_star(0, 140, 650)
        self.add_item_box(200, 40, 100, "wing")
        self.add_cannon(-200, 25, -200, yaw=0.8, power=46)
        self.add_enemy(50,30,280,"koopa")

class BowserSky(WorldBase):
    def __init__(self):
        super().__init__()
        self.name = "Bowser in the Sky"; self.sky_color = SKY_RAINBOW; self.spawn = (0, -400)
        self.build()
    def build(self):
        self.add_box(0,0,-350,260,16,260,STONE_GRAY,collide=True)
        cols = [MARIO_RED, LAVA_ORANGE, YELLOW, GRASS_GREEN, SKY_BLUE, PURPLE, RAINBOW_PINK]
        for i in range(10):
            self.add_box(math.sin(i)*180, 20+i*18, i*110, 100, 14, 100, cols[i%7], collide=True)
        self.add_box(0, 200, 900, 480, 40, 480, WHITE, collide=True)
        self.add_boss(0, 210, 900)
        self.add_star(0, 280, 900)
        self.add_mover(100, 100, 400, amp=120, axis="x", color=RAINBOW_CYAN)
        self.add_pole(-80, 0, -300, 160)
        self.add_item_box(0, 30, -300, "vanish")
        self.add_enemy(0,20,200,"chuckya")

COURSE_LIST = [
    ("Castle Grounds",CastleGrounds,"(Hub World)",STONE_GRAY),
    ("Castle Lobby",CastleLobby,"(Castle)",STONE_PATH),
    ("Castle Basement",CastleBasement,"(Castle)",CAVE_BROWN),
    ("Castle Upstairs",CastleUpstairs,"(Castle)",WOOD_BROWN),
    ("Bob-omb Battlefield",BobOmbBattlefield,"Course 1",GRASS_GREEN),
    ("Whomp's Fortress",WhompsFortress,"Course 2",STONE_GRAY),
    ("Jolly Roger Bay",JollyRogerBay,"Course 3",WATER_BLUE),
    ("Cool, Cool Mountain",CoolCoolMountain,"Course 4",SNOW_WHITE),
    ("Big Boo's Haunt",BigBoosHaunt,"Course 5",MANSION_PURPLE),
    ("Hazy Maze Cave",HazyMazeCave,"Course 6",CAVE_BROWN),
    ("Lethal Lava Land",LethalLavaLand,"Course 7",LAVA_RED),
    ("Shifting Sand Land",ShiftingSandLand,"Course 8",SAND_YELLOW),
    ("Dire, Dire Docks",DireDireDocks,"Course 9",DOCK_BLUE),
    ("Snowman's Land",SnowmansLand,"Course 10",SNOW_WHITE),
    ("Wet-Dry World",WetDryWorld,"Course 11",WATER_BLUE),
    ("Tall, Tall Mountain",TallTallMountain,"Course 12",DARK_GREEN),
    ("Tiny-Huge Island",TinyHugeIsland,"Course 13",GRASS_GREEN),
    ("Tick Tock Clock",TickTockClock,"Course 14",CLOCK_BEIGE),
    ("Rainbow Ride",RainbowRide,"Course 15",RAINBOW_PINK),
    ("Bowser in the Dark World",BowserDarkWorld,"Bowser 1",CAVE_DARK),
    ("Bowser in the Fire Sea",BowserFireSea,"Bowser 2",LAVA_RED),
    ("Bowser in the Sky",BowserSky,"Bowser 3",RAINBOW_PINK),
]

COURSE_BY_NAME = {name: cls for name, cls, _, _ in COURSE_LIST}

def _install_course_hub_exits():
    """Every course gets exit pipe + light object sprinkle if sparse."""
    for name, cls, _label, _col in COURSE_LIST:
        if name == "Castle Grounds":
            continue
        orig = cls.build
        def _make(orig_build, cname=name):
            def build(self, _orig=orig_build, _cn=cname):
                _orig(self)
                if not any(getattr(e, "target", None) == "Castle Grounds" for e in self.enterables):
                    self.add_hub_exit()
                # flavor fill so courses aren't empty plates
                if len(self.boxes) == 0:
                    sx, sz = self.spawn
                    self.add_item_box(sx + 80, 35, sz + 40, "coin")
                    self.add_item_box(sx - 90, 35, sz + 60, random.choice(["wing", "metal", "vanish", "1up"]))
                if len(self.red_coins) == 0:
                    sx, sz = self.spawn
                    for i in range(5):
                        self.add_red_coin(sx + math.cos(i)*120, 45, sz + 200 + math.sin(i)*120)
                if len(self.enemies) < 2 and "Bowser" not in _cn:
                    sx, sz = self.spawn
                    self.add_enemy(sx + 150, 0, sz + 100, random.choice(["goomba", "koopa", "bobomb"]))
                if len(self.movers) == 0 and "Bowser" not in _cn:
                    sx, sz = self.spawn
                    self.add_mover(sx, 50, sz + 250, amp=90, axis="x")
            return build
        cls.build = _make(orig)

_install_course_hub_exits()

def nearest_enterable(mario, world):
    best, best_d = None, 1e9
    for ent in getattr(world, "enterables", []):
        if not ent.in_range(mario):
            continue
        d = ent.dist_xz(mario)
        if d < best_d:
            best, best_d = ent, d
    return best

def try_use_enterable(ent, total_stars, total_keys=0):
    """Return ('course', name) | ('teleport', xyz) | ('locked', need) | None."""
    if ent is None:
        return None
    if not ent.unlocked(total_stars, total_keys):
        return ("locked", ent.stars_needed if total_stars < ent.stars_needed else ent.keys_needed)
    if ent.target:
        return ("course", ent.target)
    if ent.teleport is not None:
        return ("teleport", ent.teleport)
    return None

def spawn_world(course_name, total_stars=0, total_keys=0):
    """Build a world by COURSE_LIST / STAR_GATES / KEY_GATES name."""
    cls = COURSE_BY_NAME.get(course_name)
    if cls is None:
        return None
    if course_name in ("Castle Grounds", "Castle Lobby", "Castle Basement", "Castle Upstairs", "Peach's Castle"):
        if course_name == "Peach's Castle":
            return CastleGrounds()
        return cls()
    need = STAR_GATES.get(course_name, 0)
    if total_stars < need:
        return None
    kneed = KEY_GATES.get(course_name, 0)
    if total_keys < kneed:
        return None
    return cls()

# ============================================================
# RENDER — software raster via MATH ENGINE + pygame.draw
# ============================================================

def render_world(surf, world, mario, cam):
    """Software poly raster: depth sort, lighting, procedural materials, fog."""
    fog = world.sky_color
    # subtle sky gradient (math fill)
    for band in range(0, HEIGHT, 8):
        t = band / HEIGHT
        c = (
            max(0, min(255, int(fog[0] * (1 - 0.25 * t) + 20 * t))),
            max(0, min(255, int(fog[1] * (1 - 0.15 * t) + 30 * t))),
            max(0, min(255, int(fog[2] * (1 - 0.05 * t) + 40 * t))),
        )
        pygame.draw.rect(surf, c, (0, band, WIDTH, 8))
    rlist = []
    for face in world.faces:
        if len(face) == 3:
            indices, color, normal = face
        else:
            indices, color = face
            normal = None
        submit_poly(rlist, world.verts, indices, color, cam, fog, normal)
    for star in world.stars:
        if star.collected:
            continue
        star.update()
        sv, sf = star.get_mesh()
        for indices, color in sf:
            submit_poly(rlist, sv, indices, color, cam, fog)
    for coin in world.coins:
        if coin.collected:
            continue
        coin.update()
        cv, cf = coin.get_mesh()
        for indices, color in cf:
            submit_poly(rlist, cv, indices, color, cam, fog)
    for enemy in getattr(world, "enemies", []):
        ev, ef = enemy.get_mesh()
        for indices, color in ef:
            submit_poly(rlist, ev, indices, color, cam, fog)
    for cap in getattr(world, "caps", []):
        cv, cf = cap.get_mesh()
        for indices, color in cf:
            submit_poly(rlist, cv, indices, color, cam, fog)
    for lst_name in ("red_coins", "blue_coins", "oneups", "boxes", "movers", "cannons", "poles", "bosses"):
        for obj in getattr(world, lst_name, []):
            if hasattr(obj, "update") and lst_name in ("movers", "cannons", "boxes", "oneups", "red_coins", "blue_coins"):
                pass  # updated in sim loop
            mvmesh = obj.get_mesh()
            if not mvmesh:
                continue
            ov, ofaces = mvmesh
            for face in ofaces:
                if len(face) == 3 and isinstance(face[2], tuple):
                    indices, color, normal = face
                    submit_poly(rlist, ov, indices, color, cam, fog, normal)
                else:
                    indices, color = face[0], face[1]
                    submit_poly(rlist, ov, indices, color, cam, fog)
    near_ent = nearest_enterable(mario, world)
    for ent in getattr(world, "enterables", []):
        ent.pulse += 0.12
        ev, ef = ent.get_mesh(highlight=(ent is near_ent))
        for face in ef:
            indices, color, normal = face
            submit_poly(rlist, ev, indices, color, cam, fog, normal)
    mv, mf = mario.get_mesh()
    for face in mf:
        if len(face) == 3:
            indices, color, normal = face
        else:
            indices, color = face[0], face[1]
            normal = None
        submit_poly(rlist, mv, indices, color, cam, fog, normal)
    draw_sorted(surf, rlist)

def draw_hud(surf, mario, world_name, enter_prompt=None):
    total = getattr(draw_hud, "total_stars", 0)
    pygame.draw.rect(surf, (0, 0, 0), (0, 0, WIDTH, 48))
    keys = getattr(draw_hud, "total_keys", 0)
    line = hud_font.render(
        f"★{total}  KEY {keys}  COIN {mario.coins:03d}  ❤️{mario.lives}  HP {getattr(mario,'health',8)}/8",
        True, WHITE,
    )
    surf.blit(line, (12, 8))
    surf.blit(hud_font.render(world_name, True, YELLOW), (12, 28))
    if getattr(mario, "cap", None):
        surf.blit(
            hud_font.render(f"CAP {mario.cap.upper()} {max(0,mario.cap_timer)//60}s", True, (255, 210, 120)),
            (WIDTH - 240, 8),
        )
    if getattr(mario, "swim", False):
        surf.blit(hud_font.render("SWIM", True, WATER_BLUE), (WIDTH - 80, 28))
    if enter_prompt:
        # SM64-style interact prompt
        bg = pygame.Rect(0, 0, min(WIDTH - 40, 560), 36)
        bg.center = (WIDTH // 2, HEIGHT - 54)
        pygame.draw.rect(surf, (0, 0, 0), bg)
        pygame.draw.rect(surf, STAR_YELLOW, bg, 2)
        pr = hud_font.render(enter_prompt, True, STAR_YELLOW)
        surf.blit(pr, pr.get_rect(center=bg.center))
    tip = small_font.render(
        "WASD MOVE | SPACE JUMP | A ENTER DOOR/PAINTING/PIPE | SHIFT POUND | CTRL/Z DIVE | Q/E CAM | M MUSIC | ESC",
        True, WHITE,
    )
    surf.blit(tip, (WIDTH // 2 - tip.get_width() // 2, HEIGHT - 22))


class MenuScene:
    """Title / main menu: Play Game, Controls, Help, About, Copyright, Exit."""

    ITEMS = (
        ("Play Game", "play"),
        ("Controls", "controls"),
        ("Help", "help"),
        ("About", "about"),
        ("Copyright", "copyright"),
        ("Exit", "exit"),
    )

    PAGE_TEXT = {
        "controls": (
            "CONTROLS",
            [
                "WASD / Arrow Keys  — move (camera-relative)",
                "Space              — jump (double / triple chain)",
                "Shift + Space      — long jump (while running)",
                "Shift in air       — ground pound",
                "Ctrl / Z           — dive (air) / punch-slide (ground)",
                "A / Enter / Z      — enter door, painting, or pipe",
                "Walk into          — painting & pipe warps",
                "Q / E / Mouse      — Lakitu camera (RMB / Alt look)",
                "M                  — toggle in-game music",
                "Esc                — course select (from play)",
                "",
                "Confirm menus with A / Enter / Z / Space",
            ],
        ),
        "help": (
            "HELP",
            [
                "Explore Peach's Castle grounds, then enter courses",
                "through paintings, doors, and pipes.",
                "",
                "Collect stars and coins. Star gates unlock later",
                "courses when you have enough stars.",
                "",
                "Near an enterable, look for the yellow prompt:",
                "  Press A to enter",
                "Locked doors show how many stars you still need.",
                "",
                "Each course has an exit pipe back to the castle.",
                "Esc opens the course list if you prefer menus.",
                "",
                "FILES_OFF: no ROM or ripped Nintendo assets.",
            ],
        ),
        "about": (
            "ABOUT",
            [
                f"{PRODUCT_NAME}",
                f"Backend: {PYGAME_BACKEND}  ·  FILES_OFF = True",
                "",
                "A clean-room FOSS tribute to the SM64 PC-port style:",
                "custom math 3D, procedural materials, synth OST,",
                "and an articulated Mario mesh — all in one file.",
                "",
                "Not a decompilation. Not an emulator.",
                "No ROM, textures, models, or copyrighted audio.",
                "",
                "Made for learning / fun. Enjoy the castle!",
            ],
        ),
        "copyright": (
            "COPYRIGHT",
            [
                "© AC Kondo / cat's sm64 pyport — original FOSS code",
                "",
                "This is an independent fan tribute.",
                "Not affiliated with, endorsed by, or connected to",
                "Nintendo Co., Ltd., Nintendo of America Inc.,",
                "or any Nintendo subsidiary or licensee.",
                "",
                "Super Mario, Super Mario 64, and related names",
                "are trademarks of their respective owners.",
                "Used here only for descriptive / tribute context.",
                "",
                "No Nintendo ROM, assets, sequences, or source",
                "code are included or required (FILES_OFF).",
                "",
                "Credit style shared with the AC Kondo project family",
                "(FOSS ports / tributes). Keep it legal — create, don't rip.",
            ],
        ),
    }

    def __init__(self):
        self.ticks = 0
        self.yaw = 0.0
        self.cursor = 0
        self.page = None  # None = root menu; else controls/help/about/copyright
        self.item_rects = []

    def update(self):
        self.ticks += 1
        self.yaw += 0.03

    def _confirm_keys(self, key):
        return key in (
            pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
            pygame.K_a, pygame.K_z,
        )

    def handle(self, events):
        """Process input. Returns 'play' | 'exit' | None."""
        for e in events:
            if e.type == pygame.KEYDOWN:
                if self.page is not None:
                    if e.key == pygame.K_ESCAPE or self._confirm_keys(e.key):
                        self.page = None
                    continue
                if e.key in (pygame.K_UP, pygame.K_w):
                    self.cursor = (self.cursor - 1) % len(self.ITEMS)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    self.cursor = (self.cursor + 1) % len(self.ITEMS)
                elif self._confirm_keys(e.key):
                    return self._activate(self.ITEMS[self.cursor][1])
                elif e.key == pygame.K_ESCAPE:
                    return "exit"
            elif e.type == pygame.MOUSEMOTION and self.page is None:
                mx, my = e.pos
                for i, rect in enumerate(self.item_rects):
                    if rect.collidepoint(mx, my):
                        self.cursor = i
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.page is not None:
                    self.page = None
                    continue
                for i, rect in enumerate(self.item_rects):
                    if rect.collidepoint(mx, my):
                        self.cursor = i
                        return self._activate(self.ITEMS[i][1])
        return None

    def _activate(self, action):
        if action == "play":
            return "play"
        if action == "exit":
            return "exit"
        self.page = action
        return None

    def _draw_backdrop(self, surf):
        for band in range(0, HEIGHT, 6):
            t = band / HEIGHT
            c = (
                max(0, min(255, int(NES_BLUE[0] * (1 - 0.3 * t)))),
                max(0, min(255, int(NES_BLUE[1] * (1 - 0.2 * t)))),
                max(0, min(255, int(NES_BLUE[2] * (1 - 0.05 * t) + 20))),
            )
            pygame.draw.rect(surf, c, (0, band, WIDTH, 6))
        # spinning low-poly Mario (title mascot)
        preview = Mario(0, 0, 0)
        preview.yaw = self.yaw
        preview.vx = 8
        preview.grounded = True
        class _Cam:
            x, y, z = -90.0, 50.0, -240.0
            yaw, pitch = 0.35, -0.1
        mv, mf = preview.get_mesh()
        rlist = []
        for face in mf:
            indices, color, normal = face
            submit_poly(rlist, mv, indices, color, _Cam, NES_BLUE, normal)
        draw_sorted(surf, rlist)

    def _draw_logo(self, surf, y=72):
        logo = PRODUCT_NAME
        try:
            logo_font = pygame.font.SysFont("Arial Black", 36, bold=True)
        except Exception:
            logo_font = pygame.font.Font(None, 44)
        sh = logo_font.render(logo, True, BLACK)
        ti = logo_font.render(logo, True, YELLOW)
        sr = ti.get_rect(center=(WIDTH // 2, y))
        surf.blit(sh, (sr.x + 3, sr.y + 3))
        surf.blit(ti, sr)
        sub = small_font.render("FILES_OFF · clean-room FOSS tribute · not affiliated with Nintendo", True, (220, 220, 235))
        surf.blit(sub, sub.get_rect(center=(WIDTH // 2, y + 36)))

    def _draw_page(self, surf):
        title, lines = self.PAGE_TEXT[self.page]
        panel = pygame.Rect(70, 50, WIDTH - 140, HEIGHT - 100)
        pygame.draw.rect(surf, (12, 18, 40), panel)
        pygame.draw.rect(surf, STAR_YELLOW, panel, 3)
        th = title_font.render(title, True, STAR_YELLOW)
        surf.blit(th, th.get_rect(center=(WIDTH // 2, panel.top + 36)))
        y = panel.top + 80
        for line in lines:
            col = WHITE if line else (180, 180, 200)
            t = small_font.render(line, True, col)
            surf.blit(t, (panel.left + 28, y))
            y += 22
        hint = hud_font.render("Esc / A / Enter / click — back to menu", True, (200, 200, 220))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, panel.bottom - 28)))

    def draw(self, surf):
        self._draw_backdrop(surf)
        if self.page is not None:
            self._draw_page(surf)
            return
        self._draw_logo(surf, y=58)
        self.item_rects = []
        # menu panel on the right so Mario stays visible
        panel = pygame.Rect(WIDTH // 2 + 20, 110, WIDTH // 2 - 50, 380)
        pygame.draw.rect(surf, (10, 14, 32, 180)[:3], panel)
        pygame.draw.rect(surf, (255, 220, 80), panel, 2)
        y0 = panel.top + 28
        for i, (label, _act) in enumerate(self.ITEMS):
            y = y0 + i * 52
            rect = pygame.Rect(panel.left + 16, y, panel.width - 32, 44)
            self.item_rects.append(rect)
            selected = i == self.cursor
            if selected:
                pygame.draw.rect(surf, (50, 55, 100), rect)
                pygame.draw.rect(surf, STAR_YELLOW, rect, 2)
                marker = menu_font.render(">", True, STAR_YELLOW)
                surf.blit(marker, (rect.left + 8, rect.centery - marker.get_height() // 2))
            col = YELLOW if selected else WHITE
            t = menu_font.render(label, True, col)
            surf.blit(t, (rect.left + 36, rect.centery - t.get_height() // 2))
        foot = small_font.render("↑↓ / WASD or mouse  ·  A / Enter / Z / Space confirm  ·  Esc quit", True, (210, 210, 230))
        surf.blit(foot, foot.get_rect(center=(WIDTH // 2, HEIGHT - 28)))

class LetterScene:
    def __init__(self):
        self.lines = ["Dear Mario,","","Please come to the castle.","I've baked a cake for you.","","Yours truly,","Princess Toadstool","  ~ Peach"]
        self.timer = 0
    def update(self):
        self.timer += 1
    def draw(self, surf):
        surf.fill(BLACK)
        paper = pygame.Rect(0,0,450,400)
        paper.center = (WIDTH//2, HEIGHT//2)
        pygame.draw.rect(surf, PARCHMENT, paper)
        pygame.draw.rect(surf, INK_COLOR, paper, 4)
        y = paper.top+50
        for line in self.lines:
            t = letter_font.render(line, True, INK_COLOR)
            surf.blit(t, t.get_rect(center=(WIDTH//2, y)))
            y += 40
        if self.timer > 60:
            pr = hud_font.render("Press SPACE to Continue", True, WHITE)
            surf.blit(pr, (WIDTH-280, HEIGHT-40))

class LevelSelectScene:
    def __init__(self, total_stars=0):
        self.cursor = 0; self.scroll = 0; self.total_stars = total_stars
    def update(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w): self.cursor = max(0, self.cursor-1)
                elif e.key in (pygame.K_DOWN, pygame.K_s): self.cursor = min(len(COURSE_LIST)-1, self.cursor+1)
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN): return self.cursor
        if self.cursor < self.scroll: self.scroll = self.cursor
        if self.cursor >= self.scroll+8: self.scroll = self.cursor-7
        return None
    def draw(self, surf):
        surf.fill((20,15,40))
        ti = title_font.render("SELECT COURSE", True, STAR_YELLOW)
        surf.blit(ti, ti.get_rect(center=(WIDTH//2, 55)))
        st = menu_font.render(f"Total Stars: \u2605 {self.total_stars}", True, YELLOW)
        surf.blit(st, st.get_rect(center=(WIDTH//2, 105)))
        y0 = 145; rh = 52
        for i in range(self.scroll, min(self.scroll+8, len(COURSE_LIST))):
            name, _, label, color = COURSE_LIST[i]
            y = y0+(i-self.scroll)*rh
            if i == self.cursor:
                pygame.draw.rect(surf, (50,45,80), (60, y-4, WIDTH-120, rh-4))
                pygame.draw.rect(surf, STAR_YELLOW, (60, y-4, WIDTH-120, rh-4), 2)
            need = STAR_GATES.get(name, 0)
            locked = self.total_stars < need
            pygame.draw.rect(surf, color if not locked else DARK_GRAY, (80, y+4, 30, 30))
            pygame.draw.rect(surf, WHITE, (80, y+4, 30, 30), 1)
            lb = small_font.render(label, True, (180,180,180))
            surf.blit(lb, (125, y+2))
            lock_txt = f"  [need {need}★]" if locked else ""
            ncol = (110, 110, 110) if locked else (WHITE if i == self.cursor else (200, 200, 200))
            n = select_font.render(name + lock_txt, True, ncol)
            surf.blit(n, (125, y+18))
        if self.scroll > 0:
            a = menu_font.render("\u25b2", True, WHITE)
            surf.blit(a, a.get_rect(center=(WIDTH//2, y0-15)))
        if self.scroll+8 < len(COURSE_LIST):
            a = menu_font.render("\u25bc", True, WHITE)
            surf.blit(a, a.get_rect(center=(WIDTH//2, y0+8*rh+5)))
        cl = small_font.render("UP/DOWN: Navigate | SPACE/ENTER: Select | ESC: Menu", True, (150,150,150))
        surf.blit(cl, cl.get_rect(center=(WIDTH//2, HEIGHT-20)))

class StarGetScene:
    def __init__(self, title=None):
        self.timer = 0
        self.title = title or "You got a star!"
    def update(self):
        self.timer += 1
    def draw(self, surf, total_stars):
        o = pygame.Surface((WIDTH, HEIGHT))
        o.fill(BLACK); o.set_alpha(min(self.timer*4, 180))
        surf.blit(o, (0,0))
        if self.timer > 20:
            bob = math.sin(self.timer*0.1)*5
            for angle in range(0, 360, 72):
                a = math.radians(angle+self.timer*2)
                sx = WIDTH//2+math.cos(a)*(30*2+20)
                sy = HEIGHT//2-30+math.sin(a)*(30*2+20)+bob
                pygame.draw.circle(surf, STAR_YELLOW, (int(sx), int(sy)), max(3, 10))
            tx = star_font.render("\u2605 STAR GET! \u2605", True, STAR_YELLOW)
            surf.blit(tx, tx.get_rect(center=(WIDTH//2, HEIGHT//2-30)))
            if getattr(self, "title", None):
                mt = hud_font.render(str(self.title), True, STAR_YELLOW)
                surf.blit(mt, mt.get_rect(center=(WIDTH//2, HEIGHT//2-70)))
            c = menu_font.render(f"Total: {total_stars}", True, WHITE)
            surf.blit(c, c.get_rect(center=(WIDTH//2, HEIGHT//2+30)))
        if self.timer > 120:
            pr = small_font.render("Press SPACE to continue", True, WHITE)
            surf.blit(pr, pr.get_rect(center=(WIDTH//2, HEIGHT//2+80)))

# ============================================================
# Example Behavior Scripts
# ============================================================

obj_mgr = None

# Floating platform script: bobs up and down
def _bhv_float_platform_loop(obj):
    obj.oPosY = obj.oHomeY + math.sin(obj.oTimer * 0.03) * 50.0

script_floating_platform = [
    _BC_BB(BHV_BEGIN, OBJ_LIST_SURFACE),
] + bhv_or_int(OFFLAGS, OBJ_FLAG_UPDATE_GFX_POS_AND_ANGLE) + [
] + bhv_set_home() + [
] + bhv_set_float(OCOLLISIONDISTANCE, 500) + [
] + bhv_begin_loop() + [
] + bhv_call_native(_bhv_float_platform_loop) + [
] + bhv_end_loop()

# Rotating platform script
def _bhv_rot_platform_loop(obj):
    obj.oFaceAngleYaw = (obj.oFaceAngleYaw + 100) % 65536

script_rotating_platform = [
    _BC_BB(BHV_BEGIN, OBJ_LIST_SURFACE),
] + bhv_or_int(OFFLAGS, OBJ_FLAG_UPDATE_GFX_POS_AND_ANGLE) + [
] + bhv_set_home() + [
] + bhv_begin_loop() + [
] + bhv_call_native(_bhv_rot_platform_loop) + [
] + bhv_end_loop()

# Simple bouncing coin-like object
def _bhv_bounce_coin_loop(obj):
    obj.oPosY = obj.oHomeY + abs(math.sin(obj.oTimer * 0.08)) * 40.0
    obj.oFaceAngleYaw = (obj.oTimer * 500) % 65536

script_bouncing_coin = [
    _BC_BB(BHV_BEGIN, OBJ_LIST_LEVEL),
] + bhv_billboard() + [
] + bhv_or_int(OFFLAGS, OBJ_FLAG_UPDATE_GFX_POS_AND_ANGLE) + [
] + bhv_set_home() + [
] + bhv_set_int(OINTANGIBLETIMER, 0) + [
] + bhv_begin_loop() + [
] + bhv_call_native(_bhv_bounce_coin_loop) + [
] + bhv_end_loop()

def init_obj_manager():
    global obj_mgr
    obj_mgr = ObjectManager()

    # Register native behavior functions
    obj_mgr.interpreter.native_funcs[id(_bhv_float_platform_loop)] = _bhv_float_platform_loop
    obj_mgr.interpreter.native_funcs[id(_bhv_rot_platform_loop)] = _bhv_rot_platform_loop
    obj_mgr.interpreter.native_funcs[id(_bhv_bounce_coin_loop)] = _bhv_bounce_coin_loop

    # Register models
    # Model 1: Gold coin (a flat rectangle)
    coin_verts = [(0,0,0),(20,0,0),(20,20,0),(0,20,0)]
    coin_faces = [([0,1,2,3], GOLD)]
    obj_mgr.register_model(1, coin_verts, coin_faces, GOLD)

    # Model 2: Star-shaped indicator (small diamond)
    star_verts = [(0,15,0),(10,0,0),(0,-15,0),(-10,0,0)]
    star_faces = [([0,1,3], STAR_YELLOW), ([1,2,3], STAR_YELLOW)]
    obj_mgr.register_model(2, star_verts, star_faces, STAR_YELLOW)

    # Model 3: Floating platform
    plat_verts = [(-50,0,-50),(50,0,-50),(50,0,50),(-50,0,50),(-50,10,-50),(50,10,-50),(50,10,50),(-50,10,50)]
    plat_faces = [
        ([0,1,2,3], STONE_GRAY), ([4,5,6,7], DARK_GRAY),
        ([0,4,5,1], STONE_GRAY), ([1,5,6,2], STONE_GRAY),
        ([2,6,7,3], STONE_GRAY), ([0,4,7,3], STONE_GRAY)
    ]
    obj_mgr.register_model(3, plat_verts, plat_faces, STONE_GRAY)

    # Model 4: Box (for rotating platform demo)
    box_verts = [(-30,-30,-30),(30,-30,-30),(30,30,-30),(-30,30,-30),(-30,-30,30),(30,-30,30),(30,30,30),(-30,30,30)]
    box_faces = [
        ([0,1,2,3], MARIO_RED), ([4,5,6,7], MARIO_BLUE),
        ([0,4,5,1], MARIO_RED), ([1,5,6,2], MARIO_RED),
        ([2,6,7,3], MARIO_RED), ([0,4,7,3], MARIO_RED)
    ]
    obj_mgr.register_model(4, box_verts, box_faces, MARIO_RED)

    # Spawn demo objects (will be usable from level selector or optionally in every level)
    # These are spawned but their rendering is optional

def spawn_demo_objects(world=None):
    """Spawn behavior-driven objects in the current level."""
    global obj_mgr
    if world is None:
        return
    # Spawn floating platforms near interesting locations
    obj_mgr.spawn(script_floating_platform, 3, 300, 50, -400)
    obj_mgr.spawn(script_floating_platform, 3, -300, 50, 400)

def render_bhv_objects(surf, cam, mario, fog_rgb=None):
    """Render behavior-driven objects through the math engine."""
    global obj_mgr
    if obj_mgr is None:
        return
    fog = fog_rgb or SKY_BLUE
    rlist = []
    for obj, verts, faces, color in obj_mgr.get_renderable_objects():
        wverts = [
            (obj.oPosX + v[0], obj.oPosY + v[1] + obj.oGraphYOffset, obj.oPosZ + v[2])
            for v in verts
        ]
        for indices, face_color in faces:
            submit_poly(rlist, wverts, indices, face_color, cam, fog)
    draw_sorted(surf, rlist)

def begin_play(course_name, total_stars, obj_mgr_ref, total_keys=0):
    """Warp into a course/hub. Returns (world, mario, cam) or None if locked/missing."""
    w = spawn_world(course_name, total_stars, total_keys)
    if w is None:
        # allow hub always
        if course_name in ("Castle Grounds", "Peach's Castle"):
            w = CastleGrounds()
        else:
            return None
    m = Mario(*w.spawn)
    m.snap_to_floor(w.platforms)
    m.water_y = getattr(w, "water_y", None)
    c = Camera(m)
    pygame.mouse.get_rel()
    if obj_mgr_ref is not None:
        obj_mgr_ref.interpreter.objects.clear()
        spawn_demo_objects(w)
    music_for_world(w)
    play_sfx("cap")
    return w, m, c

def persist(save, mario=None, total_stars=None):
    if mario is not None:
        save["coins"] = mario.coins
        save["lives"] = mario.lives
    if total_stars is not None:
        save["stars"] = total_stars
    write_save(save)

def apply_box_contents(world, mario, contents):
    if contents == "coin":
        mario.give_coin(1)
    elif contents == "red":
        mario.give_coin(2)
    elif contents == "blue":
        mario.give_coin(5)
    elif contents == "1up":
        mario.lives += 1
        play_sfx("1up")
    elif contents in ("wing", "metal", "vanish"):
        world.caps.append(CapBlock(mario.x, mario.y + 40, mario.z, contents))
        play_sfx("cap")

def main():
    state = STATE_MENU
    menu_scene = MenuScene()
    letter_scene = LetterScene()
    level_sel = LevelSelectScene()
    star_scene = StarGetScene()
    mario = None
    cam = None
    world = None
    save = load_save()
    total_stars = int(save.get("stars", 0))
    total_keys = int(save.get("keys", 0))
    enter_prompt = None
    locked_flash = 0
    warp_cd = 0
    running = True

    # Initialize ObjectManager with behavior scripts
    init_obj_manager()

    while running:
        clock.tick(60)
        keys = pygame.key.get_pressed()
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                running = False

        if state == STATE_MENU:
            music_stop()  # menus silent — OST only in-game
            menu_scene.update()
            action = menu_scene.handle(events)
            menu_scene.draw(screen)
            if action == "play":
                letter_scene = LetterScene()
                state = STATE_LETTER
            elif action == "exit":
                running = False

        elif state == STATE_LETTER:
            music_stop()
            letter_scene.update()
            letter_scene.draw(screen)
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    # Drop into castle hub — use doors/paintings to enter courses
                    packed = begin_play("Castle Grounds", total_stars, obj_mgr, total_keys)
                    if packed:
                        world, mario, cam = packed
                        mario.coins = int(save.get("coins", 0))
                        mario.lives = int(save.get("lives", 4))
                        enter_prompt = None
                        state = STATE_PLAYING

        elif state == STATE_LEVEL_SEL:
            music_stop()
            level_sel.total_stars = total_stars
            choice = level_sel.update(events)
            level_sel.draw(screen)
            if choice is not None:
                cname, WorldClass, _, _ = COURSE_LIST[choice]
                need = STAR_GATES.get(cname, 0)
                kneed = KEY_GATES.get(cname, 0)
                if total_stars >= need and total_keys >= kneed:
                    packed = begin_play(cname, total_stars, obj_mgr, total_keys)
                    if packed:
                        world, mario, cam = packed
                        enter_prompt = None
                        state = STATE_PLAYING
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    state = STATE_MENU

        elif state == STATE_PLAYING:
            music_for_world(world)
            mario.water_y = getattr(world, "water_y", None)
            if locked_flash > 0:
                locked_flash -= 1

            if warp_cd > 0:
                warp_cd -= 1

            near = nearest_enterable(mario, world)
            enter_prompt = near.prompt(total_stars, total_keys) if near else None
            if locked_flash > 0 and near and not near.unlocked(total_stars, total_keys):
                enter_prompt = near.prompt(total_stars, total_keys)

            # A / Enter / Z (in doorway) — primary interact is A
            want_enter = False
            for e in events:
                if e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_a, pygame.K_RETURN, pygame.K_KP_ENTER):
                        want_enter = True
                    elif e.key == pygame.K_z and near is not None:
                        want_enter = True
                    elif e.key == pygame.K_m:
                        on = music_toggle()
                        if on:
                            music_for_world(world)
                    elif e.key == pygame.K_ESCAPE:
                        persist(save, mario, total_stars)
                        music_stop()
                        level_sel = LevelSelectScene(total_stars)
                        state = STATE_LEVEL_SEL

            def _apply_enter_result(res):
                nonlocal world, mario, cam, enter_prompt, locked_flash, state, warp_cd
                if res is None:
                    return False
                kind, payload = res
                if kind == "locked":
                    locked_flash = 90
                    play_sfx("hurt")
                    return False
                if kind == "teleport":
                    tx, ty, tz = payload
                    mario.x, mario.y, mario.z = float(tx), float(ty), float(tz)
                    mario.vx = mario.vy = mario.vz = 0.0
                    mario.snap_to_floor(world.dynamic_platforms())
                    play_sfx("cap")
                    warp_cd = 40
                    return True
                if kind == "course":
                    packed = begin_play(payload, total_stars, obj_mgr, total_keys)
                    if not packed:
                        locked_flash = 90
                        play_sfx("hurt")
                        return False
                    world, mario, cam = packed
                    mario.coins = save.get("coins", mario.coins)
                    mario.lives = save.get("lives", mario.lives)
                    enter_prompt = None
                    warp_cd = 50
                    return True
                return False

            just_warped = False
            if warp_cd <= 0 and want_enter and near is not None:
                just_warped = _apply_enter_result(try_use_enterable(near, total_stars, total_keys))

            result = None
            if not just_warped:
                # movers first so platforms exist under feet
                for mv in getattr(world, "movers", []):
                    mv.update()
                plats = world.dynamic_platforms()
                result = mario.update(keys, cam.yaw, plats)
                for pole in getattr(world, "poles", []):
                    pole.try_climb(mario, keys)
                for cannon in getattr(world, "cannons", []):
                    cannon.update()
                    if keys[pygame.K_a] and near is None:
                        cannon.try_launch(mario)
                cam.update(keys)
                near = nearest_enterable(mario, world)
                if warp_cd <= 0 and near is not None and near.auto and near.in_trigger(mario):
                    if near.unlocked(total_stars, total_keys):
                        just_warped = _apply_enter_result(try_use_enterable(near, total_stars, total_keys))
                    else:
                        enter_prompt = near.prompt(total_stars, total_keys)

            got_star = False
            mission_title = None
            for star in world.stars:
                if star.check(mario):
                    total_stars += 1
                    cs = save.setdefault("course_stars", {})
                    cs[world.name] = cs.get(world.name, 0) + 1
                    if getattr(star, "mid", None):
                        save.setdefault("missions", {}).setdefault(world.name, []).append(star.mid)
                    save["stars"] = total_stars
                    persist(save, mario, total_stars)
                    got_star = True
                    mission_title = getattr(star, "title", None)
                    play_sfx("star")
                    break
            for coin in world.coins:
                if coin.check(mario):
                    mario.give_coin(1)
            for rc in getattr(world, "red_coins", []):
                rc.update()
                if rc.check(mario):
                    mario.give_coin(2)
            world.check_red_coin_star()
            for bc in getattr(world, "blue_coins", []):
                bc.update()
                if bc.check(mario):
                    mario.give_coin(5)
            for u in getattr(world, "oneups", []):
                u.update()
                u.check(mario)
            for box in getattr(world, "boxes", []):
                box.update()
                contents = box.check(mario)
                if contents:
                    apply_box_contents(world, mario, contents)
            for cap in getattr(world, "caps", []):
                cap.update()
                cap.check(mario)
            for enemy in getattr(world, "enemies", []):
                er = enemy.update(mario)
                if er == "death":
                    result = "death"
            for boss in getattr(world, "bosses", []):
                br = boss.update(mario)
                if br == "death":
                    result = "death"
                elif br == "win":
                    # award key + star for Bowser arenas
                    total_keys = max(total_keys, save.get("keys", 0) + 1)
                    save["keys"] = total_keys
                    total_stars += 1
                    save["stars"] = total_stars
                    persist(save, mario, total_stars)
                    got_star = True
                    play_sfx("1up")
            obj_mgr.update_all()
            near = nearest_enterable(mario, world)
            enter_prompt = near.prompt(total_stars, total_keys) if near else enter_prompt
            render_world(screen, world, mario, cam)
            render_bhv_objects(screen, cam, mario, getattr(world, "sky_color", SKY_BLUE))
            draw_hud.total_stars = total_stars
            draw_hud.total_keys = total_keys
            draw_hud(screen, mario, world.name, enter_prompt=enter_prompt)
            if got_star:
                star_scene = StarGetScene(title=mission_title)
                state = STATE_STAR_GET
            if result == "death":
                if mario.lives <= 0:
                    music_stop()
                    persist(save, mario, total_stars)
                    state = STATE_MENU
                else:
                    mario.respawn(*world.spawn)
                    mario.snap_to_floor(world.dynamic_platforms())
                    mario.water_y = getattr(world, "water_y", None)

        elif state == STATE_STAR_GET:
            music_set_volume(STAR_GET_MUSIC_VOLUME)  # soft mute under star overlay
            render_world(screen, world, mario, cam)
            render_bhv_objects(screen, cam, mario, getattr(world, "sky_color", SKY_BLUE))
            draw_hud.total_stars = total_stars
            draw_hud(screen, mario, world.name, enter_prompt=None)
            star_scene.update()
            star_scene.draw(screen, total_stars)
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and star_scene.timer > 60:
                    music_set_volume(MUSIC_VOLUME)
                    state = STATE_PLAYING

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

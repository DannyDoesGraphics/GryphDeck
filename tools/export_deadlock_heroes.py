"""Export Deadlock hero portraits and team icons from the local game install.

    python tools/export_deadlock_heroes.py [--pak PATH] [--out DIR]

Reads the game's pak01_dir.vpk directly, takes each hero's card art
(panorama/images/heroes/<codename>_card_psd), and writes it as
frontend/public/static/Deadlock/Chars/<Hero>.png. Heroes whose card art is not
shipped yet (newly announced heroes) fall back to their smaller vertical art, so
re-run this after a game update to pick up the full-size cards.

It also writes the team icons (the Hidden King's crown and the Archmother's hand) as SVG to
frontend/public/static/Deadlock/Teams/, taken from the SVG source the game keeps inside its
compiled .vsvg_c files.

Only uncompressed BGRA8888 textures are supported, which is what the game uses
for these panorama images. Standard library only.
"""
import argparse
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAK = Path("C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/pak01_dir.vpk")
DEFAULT_OUT = ROOT / "frontend" / "public" / "static" / "Deadlock" / "Chars"
GAME_JSON = ROOT / "app" / "json" / "Deadlock.json"
IMAGE_DIR = "panorama/images/heroes/"

# Display name -> image codename. Image files use the heroes' original internal
# names, which can differ from the localization tokens (e.g. Abrams is "bull").
CODENAMES = {
    "Abrams": "bull", "Apollo": "fencer", "Baba": "baba", "Bebop": "bebop", "Billy": "punkgoat",
    "Calico": "nano", "Celeste": "unicorn", "Deadman Danny": "deadpack", "The Doorman": "doorman",
    "Drifter": "drifter", "Dynamo": "sumo", "Graves": "necro", "Grey Talon": "archer", "Haze": "haze",
    "Holliday": "astro", "Infernus": "inferno", "Ivy": "tengu", "Kelvin": "kelvin",
    "Lady Geist": "spectre", "Lash": "lash", "McGinnis": "engineer", "Mina": "vampirebat",
    "Mirage": "mirage", "Mo & Krill": "digger", "Nurse Harrow": "nurse", "Paige": "bookworm",
    "Paradox": "chrono", "Pocket": "synth", "Rat King": "ratking", "Rem": "familiar",
    "Seven": "gigawatt", "Shiv": "shiv", "Silver": "werewolf", "Sinclair": "magician",
    "Solomon": "chessmaster", "Venator": "priest", "Victor": "frank", "Vindicta": "hornet",
    "Violet": "artist", "Viscous": "viscous", "Vyper": "kali", "Warden": "warden",
    "Wraith": "wraith", "Yamato": "yamato",
}
BGRA8888 = 28
TEAM_ICONS = {
    "hidden_king.svg": "panorama/images/hud/core/team1_icon.vsvg_c",
    "archmother.svg": "panorama/images/hud/core/team2_icon.vsvg_c",
}


def read_cstr(f):
    out = bytearray()
    while (b := f.read(1)) not in (b"\x00", b""):
        out += b
    return out.decode("utf-8", "replace")


def read_vpk_tree(path):
    """Return {path: (archive, offset, length, preload)} and where embedded data starts."""
    entries = {}
    with open(path, "rb") as f:
        signature, version, tree_size = struct.unpack("<III", f.read(12))
        if signature != 0x55AA1234:
            raise ValueError(f"{path} is not a VPK directory file")
        header = 12 + (16 if version == 2 else 0)
        f.seek(header)
        while extension := read_cstr(f):
            while folder := read_cstr(f):
                while name := read_cstr(f):
                    _, preload, archive, offset, length, _ = struct.unpack("<IHHIIH", f.read(18))
                    entries[f"{folder}/{name}.{extension}"] = (archive, offset, length, f.read(preload))
    return entries, header + tree_size


def read_entry(pak, entries, data_start, name):
    archive, offset, length, preload = entries[name]
    if archive == 0x7FFF:
        source, offset = pak, offset + data_start
    else:
        source = pak.with_name(pak.name.replace("_dir", f"_{archive:03d}"))
    with open(source, "rb") as f:
        f.seek(offset)
        return preload + f.read(length)


def decode_texture(blob):
    """Decode a compiled .vtex_c into (width, height, RGBA bytes) for its full-size mip."""
    header_size, _, _, block_offset, block_count = struct.unpack_from("<IHHII", blob)
    position = 8 + block_offset
    for _ in range(block_count):
        kind, relative, _ = struct.unpack_from("<4sII", blob, position)
        if kind == b"DATA":
            width, height, depth, texture_format = struct.unpack_from("<HHHB", blob, position + 4 + relative + 20)
            break
        position += 12
    else:
        raise ValueError("texture has no DATA block")
    if texture_format != BGRA8888 or depth != 1:
        raise ValueError(f"unsupported texture format {texture_format}")
    size = width * height * 4
    pixels = blob[header_size:]
    if len(pixels) < size:
        raise ValueError("texture data is shorter than its size")
    # Mips are stored smallest first, so the full-size image is at the end.
    bgra = pixels[-size:]
    rgba = bytearray(bgra)
    rgba[0::4], rgba[2::4] = bgra[2::4], bgra[0::4]
    return width, height, bytes(rgba)


def encode_png(width, height, rgba):
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))
    stride = width * 4
    rows = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def extract_svg(blob):
    """Compiled .vsvg_c files keep the original SVG markup; return it."""
    start, end = blob.find(b"<svg"), blob.rfind(b"</svg>")
    if start < 0 or end < 0:
        raise ValueError("no SVG markup in compiled file")
    return blob[start:end + len(b"</svg>")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pak", type=Path, default=DEFAULT_PAK, help="path to citadel/pak01_dir.vpk")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder for <Hero>.png files")
    args = parser.parse_args()

    entries, data_start = read_vpk_tree(args.pak)
    args.out.mkdir(parents=True, exist_ok=True)
    heroes = json.loads(GAME_JSON.read_text(encoding="utf-8"))["chars"]
    for hero in heroes:
        codename = CODENAMES.get(hero)
        if codename is None:
            print(f"SKIPPED   {hero}: add its image codename to CODENAMES")
            continue
        for kind in ("card", "vertical"):
            name = f"{IMAGE_DIR}{codename}_{kind}_psd.vtex_c"
            if name in entries:
                width, height, rgba = decode_texture(read_entry(args.pak, entries, data_start, name))
                (args.out / f"{hero}.png").write_bytes(encode_png(width, height, rgba))
                print(f"{kind:9} {hero} ({width}x{height})")
                break
        else:
            print(f"MISSING   {hero}: no {codename}_card or {codename}_vertical art in the VPK")

    # Point out art for codenames this script does not know yet, e.g. after new heroes ship.
    known = set(CODENAMES.values())
    unknown = sorted({
        path[len(IMAGE_DIR):].split("_card_psd")[0]
        for path in entries
        if path.startswith(IMAGE_DIR) and path.endswith("_card_psd.vtex_c") and "/" not in path[len(IMAGE_DIR):]
    } - known)
    if unknown:
        print("Unmapped card art (unreleased or unused heroes):", ", ".join(unknown))

    teams_out = args.out.parent / "Teams"
    teams_out.mkdir(parents=True, exist_ok=True)
    for filename, name in TEAM_ICONS.items():
        (teams_out / filename).write_bytes(extract_svg(read_entry(args.pak, entries, data_start, name)))
        print(f"team icon {teams_out / filename}")


if __name__ == "__main__":
    main()

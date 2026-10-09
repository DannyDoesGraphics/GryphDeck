"""Shared helpers for the GryphDeck Deadlock tools: find the install, read and write VPKs,
and take apart/put together Source 2 compiled resources (the *_c files inside them)."""
import hashlib
import os
import re
import struct
import sys
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
from export_deadlock_heroes import read_entry, read_vpk_tree  # noqa: E402,F401

APP_ID = "1422450"
DEFAULT_STEAM = Path("C:/Program Files (x86)/Steam")


def steam_dir():
    """Steam's install folder, from the registry when available."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except (ImportError, OSError):
        return DEFAULT_STEAM


def deadlock_dir():
    """The Deadlock install folder (the one containing game/citadel).

    Set DEADLOCK_DIR to override; otherwise every Steam library is searched.
    """
    if os.environ.get("DEADLOCK_DIR"):
        return Path(os.environ["DEADLOCK_DIR"])
    steam = steam_dir()
    libraries = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        libraries += [Path(path.replace("\\\\", "\\")) for path in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8"))]
    for library in libraries:
        candidate = library / "steamapps" / "common" / "Deadlock"
        if (candidate / "game" / "citadel").is_dir():
            return candidate
    raise SystemExit("Could not find Deadlock. Set DEADLOCK_DIR to the folder that contains game\\citadel.")


def citadel_dir():
    return deadlock_dir() / "game" / "citadel"


class Pak:
    """Read-only view of a VPK directory file."""

    def __init__(self, path):
        self.path = Path(path)
        self.entries, self.data_start = read_vpk_tree(self.path)

    def __contains__(self, name):
        return name in self.entries

    def names(self):
        return [name for name in self.entries if not name.startswith(" /")]

    def read(self, name):
        return read_entry(self.path, self.entries, self.data_start, name)


def write_vpk(path, files):
    """Write a single-file VPK v2 with every file embedded in the directory file."""
    by_ext = {}
    for name, data in sorted(files.items()):
        folder, _, filename = name.rpartition("/")
        stem, _, ext = filename.rpartition(".")
        by_ext.setdefault(ext, {}).setdefault(folder or " ", []).append((stem, data))

    tree = bytearray()
    blob = bytearray()
    for ext, folders in by_ext.items():
        tree += ext.encode() + b"\0"
        for folder, entries in folders.items():
            tree += folder.encode() + b"\0"
            for stem, data in entries:
                tree += stem.encode() + b"\0"
                tree += struct.pack("<IHHIIH", zlib.crc32(data), 0, 0x7FFF, len(blob), len(data), 0xFFFF)
                blob += data
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"

    archive_md5 = b""  # no external archives
    tree_md5 = hashlib.md5(tree).digest()
    archive_md5_md5 = hashlib.md5(archive_md5).digest()
    header = struct.pack("<7I", 0x55AA1234, 2, len(tree), len(blob), len(archive_md5), 48, 0)
    whole = hashlib.md5(header + tree + blob + archive_md5 + tree_md5 + archive_md5_md5).digest()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + tree + blob + archive_md5 + tree_md5 + archive_md5_md5 + whole)


# Compiled resources: a 16-byte header, a table of named blocks (RED2, DATA, LaCo, ...), and
# the blocks themselves, each 16-byte aligned.

def read_blocks(data):
    """Return (header version, resource version, [(block name, bytes)])."""
    _, header_version, version, block_offset, count = struct.unpack_from("<IHHII", data, 0)
    blocks = []
    for i in range(count):
        entry = 8 + block_offset + i * 12
        rel, size = struct.unpack_from("<II", data, entry + 4)
        start = entry + 4 + rel
        blocks.append((data[entry:entry + 4].decode(), data[start:start + size]))
    return header_version, version, blocks


def write_blocks(header_version, version, blocks):
    table_start = 16
    data_start = table_start + 12 * len(blocks)
    data_start += -data_start % 16
    table = bytearray()
    body = bytearray()
    for i, (name, payload) in enumerate(blocks):
        entry = table_start + 12 * i
        table += name.encode() + struct.pack("<II", data_start + len(body) - (entry + 4), len(payload))
        body += payload + b"\0" * (-len(payload) % 16)
    out = bytearray(struct.pack("<IHHII", 0, header_version, version, 8, len(blocks)))
    out += table + b"\0" * (data_start - 16 - len(table)) + body
    struct.pack_into("<I", out, 0, len(out))
    return bytes(out)


def text_layout(stock, xml):
    """A Panorama layout (vxml_c) holding plain XML text.

    Current layouts are compiled to a binary AST (the LaCo block), but Panorama still reads
    the older text form: DATA = CRC32 of the text, an empty name list, then the text. The
    stock file's other blocks are kept so the resource still identifies as that layout.
    """
    header_version, version, blocks = read_blocks(stock)
    text = xml.encode() + b"\0"
    data = struct.pack("<IH", zlib.crc32(text), 0) + text
    kept = [(name, block) for name, block in blocks if name not in ("DATA", "LaCo")]
    return write_blocks(header_version, version, kept + [("DATA", data)])


def text_script(template, source):
    """A Panorama script (vts_c): a stock script's blocks with our JavaScript as DATA."""
    header_version, version, blocks = read_blocks(template)
    text = source.encode() + b"\0"
    return write_blocks(header_version, version, [(name, text if name == "DATA" else block) for name, block in blocks])

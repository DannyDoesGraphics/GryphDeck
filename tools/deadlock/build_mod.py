"""Build the GryphDeck spectator mod for Deadlock from the installed game.

    Scripts/python.exe tools/deadlock/build_mod.py [--offset 64] [--offline] [--out PATH]

Writes tools/deadlock/.cache/build/pak01_dir.vpk with the mods in mods.json (downloaded
from GameBanana each build; --offline reuses the last download), the spectator HUD pushed
down --offset px, and the side reporter script. Game files are rebuilt from the install,
so nothing from Valve is stored here; the build stops if a patched rule has changed.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game import APP_ID, Pak, citadel_dir, steam_dir, text_layout, text_script, write_vpk  # noqa: E402

CACHE = HERE / ".cache"
DEFAULT_OUT = CACHE / "build" / "pak01_dir.vpk"
VRF_VERSION = "20.0"
VRF_URL = f"https://github.com/ValveResourceFormat/ValveResourceFormat/releases/download/{VRF_VERSION}/cli-windows-x64.zip"
VRF_SHA256 = "d32ab327b8bbb42a2528866afb03bb582bdb779d0005488da32b90292afd3ff5"
USER_AGENT = "GryphDeck-Deadlock-Mod-Builder"

SPECTATE_LAYOUT = "panorama/layout/hud_spectate_bar.vxml_c"
SIDES_SCRIPT = "panorama/scripts/gryphdeck_sides.vts_c"
SCRIPT_TEMPLATE = "panorama/scripts/async.vts_c"  # any stock script: we keep only its headers


def css_value(prefix, value, stock_length):
    """Fit a declaration into exactly `stock_length` bytes, dropping the optional space."""
    for text in (f"{prefix}: {value};", f"{prefix}:{value};"):
        if len(text) == stock_length:
            return text.encode()
    raise SystemExit(f"{prefix}: {value} does not fit in {stock_length} bytes; pick another offset.")


def css_patches(offset):
    """(stylesheet, stock text, replacement). Compiled stylesheets keep their CSS as text
    that Panorama re-reads, so a same-length replacement edits a rule without moving
    anything else in the file."""
    return [
        ("citadel_hud_top_bar.vcss_c", b".spec_mode CitadelHudTopBar{margin-top: 8px;}",
         b".spec_mode CitadelHudTopBar{" + css_value("margin-top", f"{offset}px", 16) + b"}"),
        ("hud_spectate_bar.vcss_c", b"#spectate_target{margin-top: 12px;",
         b"#spectate_target{" + css_value("margin-top", f"{12 + offset}px", 17)),
        ("hud_spectate_bar.vcss_c", b"#camera_section{flow-children: down;}",
         b"#camera_section{visibility:collapse;}"),
        ("hud_spectate_bar.vcss_c", b".specPlayerNav{flow-children: right;}",
         b".specPlayerNav{visibility: collapse;}"),
        # "Map View (i)" under the minimap.
        ("hud_spectate_bar.vcss_c", b"#fow_view_section{margin-bottom: 64px;",
         b"#fow_view_section{visibility:collapse;"),
    ]


def fetch(url, timeout=30):
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        return response.read()


def decompiler():
    """Path to Source 2 Viewer's CLI, downloading the pinned release on first use."""
    folder = CACHE / f"vrf-{VRF_VERSION}"
    exe = folder / "Source2Viewer-CLI.exe"
    if not exe.exists():
        print(f"Downloading Source 2 Viewer {VRF_VERSION} (decompiler, ~50 MB, once)...")
        archive = fetch(VRF_URL, timeout=300)
        if hashlib.sha256(archive).hexdigest() != VRF_SHA256:
            raise SystemExit("Source 2 Viewer download did not match its pinned checksum; not using it.")
        folder.mkdir(parents=True, exist_ok=True)
        zipfile.ZipFile(io.BytesIO(archive)).extractall(folder)
    return exe


def decompile_layout(pak_path, name):
    """XML of a compiled layout inside a VPK."""
    with tempfile.TemporaryDirectory() as out:
        result = subprocess.run([str(decompiler()), "-i", str(pak_path), "--vpk_filepath", name, "-d", "-o", out],
                                capture_output=True, text=True)
        dumped = Path(out) / Path(name).with_suffix(".xml")
        if not dumped.exists():
            raise SystemExit(f"Could not decompile {name}:\n{result.stdout}{result.stderr}")
        xml = dumped.read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", xml)  # the decompiler's banner comment


def gamebanana_file(mod, offline):
    """(zip bytes, file name) of a mod's newest matching GameBanana file; cached for offline use."""
    folder = CACHE / "mods" / str(mod["gamebanana"])
    folder.mkdir(parents=True, exist_ok=True)
    if not offline:
        try:
            info = json.loads(fetch(f"https://gamebanana.com/apiv11/Mod/{mod['gamebanana']}?_csvProperties=_sName,_aFiles"))
            if mod.get("pin"):
                files = [entry for entry in info["_aFiles"] if entry["_idRow"] == mod["pin"]]
            else:
                files = [entry for entry in info["_aFiles"] if mod["file"].casefold() in entry["_sFile"].casefold()]
            if not files:
                raise SystemExit(f"{mod['name']}: no GameBanana file matches {mod.get('pin') or mod['file']!r}.")
            newest = max(files, key=lambda entry: entry["_tsDateAdded"])
            cached = folder / f"{newest['_idRow']}_{newest['_sFile']}"
            if not cached.exists():
                print(f"{mod['name']}: downloading {newest['_sFile']}...")
                cached.write_bytes(fetch(f"https://gamebanana.com/dl/{newest['_idRow']}", timeout=120))
            return cached.read_bytes(), cached.name
        except (OSError, ValueError, KeyError) as error:
            print(f"{mod['name']}: could not reach GameBanana ({error}); using the last download.")
    downloads = sorted(folder.glob("*.zip"), key=lambda path: int(path.name.split("_", 1)[0]))
    if not downloads:
        raise SystemExit(f"{mod['name']} has never been downloaded; build once while online.")
    return downloads[-1].read_bytes(), downloads[-1].name


def mod_files(mod, offline):
    """{path: bytes} of the addon VPK inside a mod's download."""
    archive, source = gamebanana_file(mod, offline)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        vpks = [name for name in bundle.namelist() if name.lower().endswith(".vpk")]
        if len(vpks) != 1:
            raise SystemExit(f"{mod['name']} ({source}) has {len(vpks)} VPKs; expected one.")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pak01_dir.vpk"
            path.write_bytes(bundle.read(vpks[0]))
            pak = Pak(path)
            files = {name: pak.read(name) for name in pak.names()}
    print(f"{mod['name']}: {source} ({len(files)} files)")
    return files, source


def apply_css_patches(files, stock, offset):
    """Patch each rule where the game will read it: a bundled mod's copy if it has the rule
    (Top Bar Plus keeps the stock top bar stylesheet under styles/base/), else the stock file."""
    for target, original, replacement in css_patches(offset):
        assert len(original) == len(replacement), (original, replacement)
        stock_name = f"panorama/styles/{target}"
        candidates = [name for name in files if name.rsplit("/", 1)[-1] == target] + [stock_name]
        for name in candidates:
            data = files[name] if name in files else stock.read(name)
            if data.count(original) == 1:
                files[name] = data.replace(original, replacement)
                print(f"  {name}: {replacement.decode()}")
                break
        else:
            raise SystemExit(f"{original.decode()!r} is no longer in {target}; Deadlock changed it. Update css_patches().")


def add_side_reporter(files, stock):
    """Make the spectator bar layout load gryphdeck_sides.js."""
    if SPECTATE_LAYOUT in files:
        raise SystemExit(f"A bundled mod replaces {SPECTATE_LAYOUT}; it cannot be combined with the side reporter.")
    xml = decompile_layout(stock.path, SPECTATE_LAYOUT)
    include = '<include src="s2r://panorama/scripts/gryphdeck_sides.vts" />'
    if "<scripts>" in xml:
        xml = xml.replace("<scripts>", f"<scripts>\n\t\t{include}", 1)
    elif "</styles>" in xml:
        xml = xml.replace("</styles>", f"</styles>\n\t<scripts>\n\t\t{include}\n\t</scripts>", 1)
    else:
        raise SystemExit(f"{SPECTATE_LAYOUT} has no <styles> block any more; update add_side_reporter().")
    files[SPECTATE_LAYOUT] = text_layout(stock.read(SPECTATE_LAYOUT), xml)
    files[SIDES_SCRIPT] = text_script(stock.read(SCRIPT_TEMPLATE), (HERE / "gryphdeck_sides.js").read_text(encoding="utf-8"))
    print(f"  {SPECTATE_LAYOUT}: loads gryphdeck_sides.js")


def game_build():
    # The manifest lives in the steamapps folder of whichever library holds Deadlock.
    for manifest in (citadel_dir().parents[3] / f"appmanifest_{APP_ID}.acf",
                     steam_dir() / "steamapps" / f"appmanifest_{APP_ID}.acf"):
        if manifest.exists():
            found = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8"))
            if found:
                return found.group(1)
    return "unknown"


def build(offset=64, offline=False, out=DEFAULT_OUT):
    stock = Pak(citadel_dir() / "pak01_dir.vpk")
    files = {}
    bundled = []
    for mod in json.loads((HERE / "mods.json").read_text(encoding="utf-8"))["mods"]:
        extra, source = mod_files(mod, offline)
        clashes = sorted(set(extra) & set(files))
        if clashes:
            raise SystemExit(f"{mod['name']} replaces files another bundled mod already does: {', '.join(clashes)}")
        files.update(extra)
        bundled.append({"name": mod["name"], "gamebanana": mod["gamebanana"], "file": source})

    print("GryphDeck changes:")
    apply_css_patches(files, stock, offset)
    add_side_reporter(files, stock)

    out = Path(out)
    write_vpk(out, files)
    manifest = {"built": int(time.time()), "game_build": game_build(), "offset": offset,
                "mods": bundled, "files": sorted(files)}
    out.with_name("manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(files)} files, Deadlock build {manifest['game_build']})")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--offset", type=int, default=64, help="spectator top bar margin in 1080p px (stock: 8)")
    parser.add_argument("--offline", action="store_true", help="reuse the last mod downloads instead of checking GameBanana")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.offset, args.offline, args.out)


if __name__ == "__main__":
    main()

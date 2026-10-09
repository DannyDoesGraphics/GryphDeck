"""Start Deadlock for a GryphDeck broadcast and report the match to GryphDeck.

    Scripts/python.exe tools/deadlock/spectator.py [--keep-mods] [--no-build] [--offline] [--attach] [-- launch options]

Builds and installs the spectator mod (other addons are set aside until the game closes),
launches Deadlock with -condebug, and forwards the match phase and side reports from
console.log to POST /api/deadlock. --attach only follows an already running game.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game import APP_ID, Pak, citadel_dir, steam_dir  # noqa: E402

PACK_NAME = "pak01_dir.vpk"
PAUSED = "gryphdeck-paused"
SESSION = "gryphdeck-session.json"
SIDES_LINE = re.compile(r"GRYPHDECK (\{.*\})\s*$")
STATE_LINE = re.compile(r"OnGameStateChanged: (\w+) \((\d+)\)")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def deadlock_running():
    try:
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq deadlock.exe", "/NH"], capture_output=True, text=True)
    except OSError:
        return False
    return "deadlock.exe" in result.stdout.lower()


# --- Mods -----------------------------------------------------------------------------------

def restore_addons(addons):
    """Undo a session: remove our pack and move paused addons back."""
    session_file = addons / PAUSED / SESSION
    if not session_file.exists():
        return
    session = json.loads(session_file.read_text(encoding="utf-8"))
    installed = addons / session["installed"]
    for attempt in range(20):  # Deadlock can hold the file for a moment after it exits
        try:
            installed.unlink(missing_ok=True)
            break
        except PermissionError:
            if attempt == 19:
                raise SystemExit(f"{installed} is still in use; close Deadlock and run this again.")
            time.sleep(0.5)
    for name in session["moved"]:
        source, target = addons / PAUSED / name, addons / name
        if not source.exists():
            continue
        if target.exists():
            log(f"Left {source} in place: {target} already exists.")
            continue
        source.rename(target)
    session_file.unlink()
    try:
        (addons / PAUSED).rmdir()
    except OSError:
        log(f"{addons / PAUSED} still holds files; check it.")
    log("Put your Deadlock addons back.")


def install_pack(addons, pack, keep_mods):
    """Install the built pack; returns nothing, records the session for restore_addons."""
    addons.mkdir(exist_ok=True)
    paused = addons / PAUSED
    paused.mkdir(exist_ok=True)
    moved = []
    if keep_mods:
        taken = {path.name.lower() for path in addons.glob("*.vpk")}
        name = next(f"pak{n:02d}_dir.vpk" for n in range(1, 100) if f"pak{n:02d}_dir.vpk" not in taken)
        ours = set(Pak(pack).names())
        for other in sorted(addons.glob("*_dir.vpk")):
            overlap = ours & set(Pak(other).names())
            if overlap:
                log(f"Warning: {other.name} also replaces {len(overlap)} of the GryphDeck mod's files "
                    f"(e.g. {sorted(overlap)[0]}); the lower-numbered VPK wins.")
    else:
        name = PACK_NAME
        for vpk in sorted(addons.glob("*.vpk")):
            vpk.rename(paused / vpk.name)
            moved.append(vpk.name)
        if moved:
            log(f"Moved {len(moved)} addon VPK(s) aside for the broadcast (citadel/addons/{PAUSED}).")
    shutil.copyfile(pack, addons / name)
    (paused / SESSION).write_text(json.dumps({"installed": name, "moved": moved}, indent=2), encoding="utf-8")
    log(f"Installed the GryphDeck spectator mod as citadel/addons/{name}.")


def ensure_addons_search_path(citadel):
    """Deadlock only reads citadel/addons if gameinfo.gi lists it; game updates can reset it."""
    gameinfo = citadel / "gameinfo.gi"
    text = gameinfo.read_text(encoding="utf-8")
    if re.search(r"^\s*Game\s+citadel/addons\s*$", text, re.MULTILINE):
        return
    fixed, count = re.subn(r"^(\s*)(Game\s+citadel\s*)$", r"\1Game\t\t\t\tcitadel/addons\n\1\2", text, count=1, flags=re.MULTILINE)
    if not count:
        raise SystemExit("gameinfo.gi has no 'Game citadel' search path to put the addons path before; add it by hand.")
    backup = citadel / "gameinfo.gi.gryphdeck-backup"
    if not backup.exists():
        shutil.copyfile(gameinfo, backup)
    gameinfo.write_text(fixed, encoding="utf-8")
    log("Added the citadel/addons search path to gameinfo.gi.")


# --- GryphDeck ------------------------------------------------------------------------------

class Forwarder:
    """Posts events to GryphDeck, re-sending the latest of each kind after an outage."""

    def __init__(self, server):
        self.url = server.rstrip("/") + "/api/deadlock"
        self.latest = {}
        self.connected = None
        self.status = None

    def send(self, event):
        self.latest[event["type"]] = event
        self._post(event)

    def _post(self, event):
        request = Request(self.url, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=3) as response:
                reply = response.read()
        except HTTPError as error:
            # GryphDeck is up but refused this event; resending it would not help.
            log(f"GryphDeck rejected a {event['type']} event: {error.read().decode('utf-8', 'replace')}")
            return True
        except (URLError, OSError) as error:
            if self.connected is not False:
                log(f"GryphDeck is not reachable at {self.url} ({error}); will keep trying.")
            self.connected = False
            return False
        if self.connected is False:
            log("Reconnected to GryphDeck.")
            self.connected = True
            for other in self.latest.values():
                if other is not event:
                    self._post(other)
        self.connected = True
        self.report(reply)
        return True

    def report(self, reply):
        """Echo GryphDeck's side detection status when it changes, loudly if it needs the operator."""
        try:
            reply = json.loads(reply)
        except ValueError:
            return
        if reply.get("ignored"):
            status = "GryphDeck ignored this: load Deadlock on the control page."
        else:
            sides = reply.get("sides") or {}
            status = sides.get("status")
            if sides.get("attention"):
                status = f"ACTION NEEDED: {status}"
        if status and status != self.status:
            self.status = status
            log(status)

    def retry(self):
        if self.connected is False and self.latest:
            # Re-send the phase first so a fresh GryphDeck resets before reading the sides.
            for kind in ("state", "teams"):
                if kind in self.latest and not self._post(self.latest[kind]):
                    return


def parse_line(line):
    if (match := SIDES_LINE.search(line)):
        try:
            event = json.loads(match.group(1))
        except ValueError:
            return None
        return event if event.get("type") == "teams" else None
    if (match := STATE_LINE.search(line)):
        return {"type": "state", "state": match.group(1), "id": int(match.group(2))}
    return None


def follow(console_log, forwarder, start_at_end, launched):
    """Tail console.log until Deadlock exits, forwarding GryphDeck events."""
    position = 0
    if start_at_end:
        # Attaching to a running game: send only the newest phase and sides already logged.
        if console_log.exists():
            caught_up = {}
            with open(console_log, "rb") as f:
                for raw in f:
                    event = parse_line(raw.decode("utf-8", "replace"))
                    if event:
                        caught_up[event["type"]] = event
                position = f.tell()
            for kind in ("state", "teams"):
                if kind in caught_up:
                    forwarder.send(caught_up[kind])
    seen_game = deadlock_running()
    started = time.monotonic()
    last_check = 0.0
    pending = b""
    while True:
        if console_log.exists():
            size = console_log.stat().st_size
            if size < position:  # the game started a new log
                position, pending = 0, b""
            if size > position:
                with open(console_log, "rb") as f:
                    f.seek(position)
                    chunk = f.read(size - position)
                position = size
                lines = (pending + chunk).split(b"\n")
                pending = lines.pop()
                for raw in lines:
                    event = parse_line(raw.decode("utf-8", "replace"))
                    if event:
                        if event["type"] == "state":
                            log(f"Match phase: {event['state']}")
                        forwarder.send(event)
        now = time.monotonic()
        if now - last_check >= 2:
            last_check = now
            forwarder.retry()
            running = deadlock_running()
            if running:
                seen_game = True
            elif seen_game:
                log("Deadlock closed.")
                return
            elif launched and now - started > 180:
                log("Deadlock did not start within 3 minutes.")
                return
        time.sleep(0.25)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-mods", action="store_true", help="leave your other addon VPKs installed")
    parser.add_argument("--no-build", action="store_true", help="install the last built mod instead of rebuilding")
    parser.add_argument("--offline", action="store_true", help="build from the last mod downloads")
    parser.add_argument("--offset", type=int, default=64, help="spectator HUD offset (see build_mod.py)")
    parser.add_argument("--server", default="http://127.0.0.1:5000", help="GryphDeck backend URL")
    parser.add_argument("--attach", action="store_true", help="only follow an already running Deadlock")
    parser.add_argument("launch_options", nargs=argparse.REMAINDER, help="extra Deadlock launch options after --")
    args = parser.parse_args()
    launch_options = [option for option in args.launch_options if option != "--"]

    citadel = citadel_dir()
    addons = citadel / "addons"
    console_log = citadel / "console.log"
    forwarder = Forwarder(args.server)

    if args.attach or deadlock_running():
        if not args.attach:
            log("Deadlock is already running, so the mod and launch options can't change now. "
                "Following it; for the side reporter it must have been started with -condebug and the GryphDeck mod.")
        follow(console_log, forwarder, start_at_end=True, launched=False)
        return

    restore_addons(addons)  # an earlier session that was interrupted
    if args.no_build:
        from build_mod import DEFAULT_OUT as pack
        if not pack.exists():
            raise SystemExit("No built mod yet; run without --no-build once.")
    else:
        from build_mod import build
        pack = build(args.offset, args.offline)
    ensure_addons_search_path(citadel)
    install_pack(addons, pack, args.keep_mods)
    try:
        try:
            console_log.unlink()
        except FileNotFoundError:
            pass
        steam = steam_dir() / "steam.exe"
        log("Launching Deadlock with -condebug...")
        subprocess.Popen([str(steam), "-applaunch", APP_ID, "-condebug", *launch_options])
        follow(console_log, forwarder, start_at_end=False, launched=True)
    except KeyboardInterrupt:
        if deadlock_running():
            log("Stopped following. Deadlock is still running with the GryphDeck mod; "
                "your addons are restored the next time this script starts.")
            return
    restore_addons(addons)


if __name__ == "__main__":
    main()

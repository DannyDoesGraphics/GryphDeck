import copy
import html
import json
import math
import re
import time
import urllib.request
from pathlib import Path

if __package__:
    from ..TeamSource import TeamSource
else:
    from TeamSource import TeamSource

SITE = "https://www.collegedeadlock.com"
SEASON = "season-3"
CACHE_FILE = (
    Path(__file__).resolve().parents[3] / "cache" / "deadlock" / "collegedeadlock.json"
)
TEAM_LIST_MAX_AGE = 24 * 60 * 60
PULL_COOLDOWN = 5 * 60


def download(path):
    request = urllib.request.Request(SITE + path, headers={"User-Agent": "GryphDeck"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8")


def save():
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def stale(entry, max_age):
    return time.time() - entry.get("fetched", 0) >= max_age


def scrape_teams():
    season = download(f"/events/{SEASON}")
    teams = {}
    for division in sorted(
        set(re.findall(rf'href="/events/({SEASON}-division-\d+)"', season))
    ):
        number = division.rsplit("-", 1)[1]
        for slug, name in re.findall(
            r'href="/teams/([^"]+)">([^<]+)</a>', download(f"/events/{division}")
        ):
            teams[slug] = {"name": html.unescape(name), "division": number}
    return teams


def steam_id(player):
    """A player's Steam account ID, from their StatLocker link; kept once found."""
    if player not in cache["steam_ids"]:
        found = re.search(
            r'href="https://statlocker.gg/profile/(\d+)"',
            download(f"/players/{player}"),
        )
        if not found:
            return None
        cache["steam_ids"][player] = int(found[1])
    return cache["steam_ids"][player]


def scrape_roster(slug):
    page = download(f"/teams/{slug}")
    return [
        {
            "name": html.unescape(name),
            "sub": ">Sub</span>" in row,
            "steam_id": steam_id(player),
        }
        for row in page.split("<li ")
        for player, name in re.findall(r'href="/players/([^"]*)">([^<]+)</a>', row)
    ]


def college_team(slug):
    """A source for one College Deadlock team."""

    def fetch(self):
        """Download the roster, or reuse the cached one if pulled in the last 5 minutes."""
        team = cache["teams"][slug]
        wait = team.get("pulled", 0) + PULL_COOLDOWN - time.time()
        if wait <= 0:
            team["pulled"] = time.time()
            team["players"] = scrape_roster(slug)
            save()
        elif "players" not in team:
            raise ValueError(f"Try again in {math.ceil(wait / 60)} min.")
        return {
            "name": team["name"],
            "players": copy.deepcopy(team["players"]),
            "extra": {
                "division": team["division"],
                "url": f"{SITE}/teams/{slug}",
                "pulled": team["pulled"],
                "steam_ids": {
                    player["name"]: player.get("steam_id") for player in team["players"]
                },
            },
        }

    team = cache["teams"][slug]
    return type(
        slug,
        (TeamSource,),
        {
            "__module__": __name__,
            "kind": f"collegedeadlock:{slug}",
            "label": f"College Deadlock D{team['division']}: {team['name']}",
            "description": "Roster from collegedeadlock.com.",
            "games": ("Deadlock",),
            "fetch": fetch,
        },
    )


cache = (
    json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    if CACHE_FILE.exists()
    else {"teams": {}}
)
cache.setdefault("steam_ids", {})
if stale(cache, TEAM_LIST_MAX_AGE):
    try:
        cache["teams"] = {
            slug: {**cache["teams"].get(slug, {}), **team}
            for slug, team in scrape_teams().items()
        }
        cache["fetched"] = time.time()
        save()
    except Exception:
        if not cache["teams"]:
            raise

globals().update(
    (f"team:{slug}", college_team(slug))
    for slug, team in sorted(
        cache["teams"].items(),
        key=lambda item: (int(item[1]["division"]), item[1]["name"].lower()),
    )
)

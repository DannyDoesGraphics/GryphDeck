import copy
import html
import json
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
ROSTER_MAX_AGE = 5 * 60


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


def scrape_roster(slug):
    page = download(f"/teams/{slug}")
    return [
        {"name": html.unescape(name), "sub": ">Sub</span>" in row}
        for row in page.split("<li ")
        for name in re.findall(r'href="/players/[^"]*">([^<]+)</a>', row)
    ]


def college_team(slug):
    """A source for one College Deadlock team; a stale roster beats a failed scrape."""

    def fetch(self):
        team = cache["teams"][slug]
        if stale(team, ROSTER_MAX_AGE):
            try:
                team.update(players=scrape_roster(slug), fetched=time.time())
                save()
            except Exception:
                if "players" not in team:
                    raise
        return {
            "name": team["name"],
            "players": copy.deepcopy(team["players"]),
            "extra": {"division": team["division"], "url": f"{SITE}/teams/{slug}"},
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

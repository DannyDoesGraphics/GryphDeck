"""Work out which GryphDeck team is on which in-game side.

The side reporter sends each side's (player, hero) pairs; GryphDeck has the same pairs from
the rosters and draft (roster player N drafted pick N). Side 1 is the Hidden King (left).
"""
import unicodedata

MAX_TEAMS = 4
MAX_PLAYERS = 12
MAX_TEXT = 128


def normalize(text):
    """Case-, accent-, and punctuation-insensitive form of a name ("The Doorman" -> "doorman")."""
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(char for char in text if char.isalnum() or char == " ").strip()
    if text.startswith("the "):
        text = text[4:]
    return text.replace(" ", "")


def _same_name(roster_name, game_name):
    if not roster_name or not game_name:
        return False
    if roster_name == game_name:
        return True
    # Tags and decorations ("GG Danny" vs "danny") still match on a long enough core name.
    shorter, longer = sorted((roster_name, game_name), key=len)
    return len(shorter) >= 4 and shorter in longer


def parse_teams(teams):
    """Validate the reporter's teams list; returns {side: [(name, hero), ...]}.

    Names and heroes are normalized; a hero is "" until it is chosen (the top bar shows "#").
    """
    if not isinstance(teams, list) or len(teams) > MAX_TEAMS:
        raise ValueError("Teams must be a short list.")
    sides = {}
    for team in teams:
        if not isinstance(team, dict) or type(team.get("side")) is not int:
            raise ValueError("Each team needs a numeric side.")
        players = team.get("players", [])
        if not isinstance(players, list) or len(players) > MAX_PLAYERS:
            raise ValueError("Players must be a short list.")
        pairs = []
        for player in players:
            if not isinstance(player, dict):
                raise ValueError("Each player must be an object.")
            name, hero = player.get("name", ""), player.get("hero", "")
            if not isinstance(name, str) or not isinstance(hero, str) or len(name) > MAX_TEXT or len(hero) > MAX_TEXT:
                raise ValueError("Player and hero names must be short text.")
            if name.strip() or normalize(hero):
                pairs.append((normalize(name), normalize(hero)))
        if team["side"] in (1, 2):
            sides[team["side"]] = pairs
    return sides


def complete(sides):
    """True once both sides are shown with every player's hero chosen: later reports add nothing."""
    return all(sides.get(side) and all(hero for _, hero in sides[side]) for side in (1, 2))


def _direction(straight, crossed):
    if straight == crossed:
        return None
    return "keep" if straight > crossed else "swap"


def detect(sides, rosters, picks):
    """Return (decision, reason, stuck); decision is "keep", "swap", or None.

    A matching roster name or a drafted hero only one side plays places a team. Mirrored
    heroes count for nothing, and names and picks that disagree are not guessed. stuck means
    the game has shown everything, so only the operator can settle it.
    """
    if 1 not in sides or 2 not in sides or not (sides[1] and sides[2]):
        return None, "waiting for both sides", False

    rosters = [[normalize(name) for name in team] for team in rosters]
    picks = [[normalize(hero) if hero else "" for hero in team] for team in picks]
    names = {side: [name for name, _ in sides[side]] for side in (1, 2)}
    heroes = {side: {hero for _, hero in sides[side] if hero} for side in (1, 2)}
    mirrored = heroes[1] & heroes[2]

    def name_hits(team, side):
        return sum(any(_same_name(ours, theirs) for theirs in names[side]) for ours in rosters[team])

    def hero_hits(team, side):
        return sum(1 for hero in picks[team] if hero and hero in heroes[side] and hero not in mirrored)

    by_names = _direction(name_hits(0, 1) + name_hits(1, 2), name_hits(0, 2) + name_hits(1, 1))
    by_heroes = _direction(hero_hits(0, 1) + hero_hits(1, 2), hero_hits(0, 2) + hero_hits(1, 1))

    if by_names and by_heroes and by_names != by_heroes:
        return None, "names and picks disagree", True
    if by_names or by_heroes:
        reason = " and ".join(label for label, found in (("player names", by_names), ("hero picks", by_heroes)) if found)
        return by_names or by_heroes, reason, False

    # No usable evidence: say what is missing.
    found_names = any(name_hits(team, side) for team in (0, 1) for side in (1, 2))
    drafted = [hero for team in picks for hero in team if hero]
    in_game = [hero for hero in drafted if hero in heroes[1] | heroes[2]]
    if not any(rosters):
        name_part = "no roster"
    elif not found_names:
        name_part = "no names match"
    else:
        name_part = "names match both sides"
    if not drafted:
        hero_part = "no picks"
    elif not in_game:
        hero_part = "no picks in game"
    elif all(hero in mirrored for hero in in_game):
        hero_part = "picks are on both sides"
    else:
        hero_part = "picks match both sides"
    return None, f"{name_part}, {hero_part}", complete(sides)

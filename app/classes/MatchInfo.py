import json

if __package__:
    from .TeamSource import SOURCES, ManualSource
else:
    from TeamSource import SOURCES, ManualSource


def roster_entries(players):
    """Player names -> (Name, sub) mappings"""
    entries = []
    for player in players:
        if isinstance(player, dict):
            entries.append((str(player["name"]), bool(player.get("sub"))))
        else:
            entries.append((str(player), False))
    return entries


class MatchInfo:
    def __init__(self, team_size=None):
        self.sources = [ManualSource(), ManualSource()]
        self.scores = [0, 0]
        self.team_size = team_size
        self.lineups = [None, None]

    # expects 1 or 2
    def team_info(self, teamNum):
        if teamNum > 2 or teamNum < 1:
            return None

        source = self.sources[teamNum - 1]
        team = source.try_fetch()
        roster = roster_entries(team["players"])
        lineup = self.lineup(teamNum, roster)
        return {
            "Name": team["name"],
            "Score": self.scores[teamNum - 1],
            "Players": lineup,
            "Roster": [{"Name": name, "Sub": sub} for name, sub in roster],
            "Bench": [name for name, _ in roster if name not in lineup],
            "Source": {
                "Kind": source.kind,
                "Label": source.label,
                "Error": source.error,
            },
            "Extra": team["extra"],
        }

    def lineup(self, teamNum, roster):
        """Return a list of players in the lineup. Manual source shows entire roster.

        Otherwise, a sourced team starts with regalars, with first N (where N is expected capacity) is selected.
        """
        names = [name for name, _ in roster]
        if self.editable(teamNum):
            return names
        chosen = self.lineups[teamNum - 1]
        if chosen is None:
            regulars = [name for name, sub in roster if not sub]
            subs = [name for name, sub in roster if sub]
            return (regulars + subs)[: self.team_size]
        return [name for name in chosen if name in names]

    def current_lineup(self, teamNum):
        """The list behind what a team shows"""
        if self.editable(teamNum):
            return self.sources[teamNum - 1].players
        return list(self.team_info(teamNum)["Players"])

    def save_lineup(self, teamNum, players):
        if not self.editable(teamNum):
            self.lineups[teamNum - 1] = players

    def editable(self, teamNum):
        """Only teams on the Manual source accept name and roster changes."""
        return 1 <= teamNum <= 2 and isinstance(self.sources[teamNum - 1], ManualSource)

    def set_source(self, teamNum, kind):
        """Switch a team's source. Switching to Manual keeps the team as it is."""
        if teamNum > 2 or teamNum < 1:
            return False
        if not isinstance(kind, str) or kind not in SOURCES:
            raise ValueError("Choose a source from the list.")

        if kind == "manual":
            team = self.team_info(teamNum)
            replacement = ManualSource(team["Name"], team["Players"], team["Extra"])
        else:
            replacement = SOURCES[kind]()
        self.sources[teamNum - 1] = replacement
        self.lineups[teamNum - 1] = None
        return True

    def update_team_name(self, teamNum, name):
        if not self.editable(teamNum):
            return False

        self.sources[teamNum - 1].name = name
        return True

    def update_team_score(self, teamNum, score):
        if teamNum > 2 or teamNum < 1:
            return False

        self.scores[teamNum - 1] = score
        return True

    def add_player(self, teamNum, playerName):
        """Add a typed player to a Manual team, or a bench player to a sourced lineup."""
        if teamNum > 2 or teamNum < 1:
            return False
        if self.editable(teamNum):
            self.sources[teamNum - 1].players.append(playerName)
            return True
        if playerName not in self.team_info(teamNum)["Bench"]:
            return False
        players = self.current_lineup(teamNum)
        players.append(playerName)
        self.save_lineup(teamNum, players)
        return True

    def remove_player(self, teamNum, playerName):
        """Remove a Manual player, or send a sourced player to the bench."""
        if teamNum > 2 or teamNum < 1:
            return False

        players = self.current_lineup(teamNum)
        if playerName in players:
            players.remove(playerName)
            self.save_lineup(teamNum, players)
            return True

        return False

    def substitute_player(self, teamNum, index, playerName, substitute):
        """Put a bench player into a sourced team's lineup in place of playerName."""
        if teamNum > 2 or teamNum < 1 or self.editable(teamNum):
            return False
        if substitute not in self.team_info(teamNum)["Bench"]:
            return False
        lineup = self.current_lineup(teamNum)
        if not 0 <= index < len(lineup) or lineup[index] != playerName:
            return False
        lineup[index] = substitute
        self.save_lineup(teamNum, lineup)
        return True

    def move_player(self, teamNum, fromIndex, toIndex, playerName):
        """Move the player at fromIndex to toIndex. playerName must still be at
        fromIndex, so a drag made against an outdated roster changes nothing."""
        if teamNum > 2 or teamNum < 1:
            return False

        players = self.current_lineup(teamNum)
        if not (0 <= fromIndex < len(players) and 0 <= toIndex < len(players)):
            return False
        if players[fromIndex] != playerName:
            return False

        players.insert(toIndex, players.pop(fromIndex))
        self.save_lineup(teamNum, players)
        return True

    def swap_sides(self):
        self.sources[0], self.sources[1] = self.sources[1], self.sources[0]
        self.scores[0], self.scores[1] = self.scores[1], self.scores[0]
        self.lineups[0], self.lineups[1] = self.lineups[1], self.lineups[0]

    def __str__(self):
        return json.dumps(
            {
                "team_1": self.team_info(1),
                "team_2": self.team_info(2),
            },
            indent=2,
        )

    def print_info(self):
        """Print both teams, including their scores, players, and sources."""
        print(self)

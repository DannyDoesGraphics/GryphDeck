import json

if __package__:
    from .TeamSource import SOURCES, ManualSource
else:
    from TeamSource import SOURCES, ManualSource


class MatchInfo:
    def __init__(self):
        self.sources = [ManualSource(), ManualSource()]
        self.scores = [0, 0]

    # expects 1 or 2
    def team_info(self, teamNum):
        if teamNum > 2 or teamNum < 1:
            return None

        source = self.sources[teamNum - 1]
        team = source.try_fetch()
        return {
            "Name": team["name"],
            "Score": self.scores[teamNum - 1],
            "Players": team["players"],
            "Source": {
                "Kind": source.kind,
                "Label": source.label,
                "Error": source.error,
            },
            "Extra": team["extra"],
        }

    def editable(self, teamNum):
        """Only teams on the Manual source accept name and roster changes."""
        return 1 <= teamNum <= 2 and isinstance(self.sources[teamNum - 1], ManualSource)

    def set_source(self, teamNum, kind):
        """Switch a team's source. Switching to Manual keeps the team as it is."""
        if teamNum > 2 or teamNum < 1:
            return False
        if not isinstance(kind, str) or kind not in SOURCES:
            raise ValueError("Choose a source from the list.")

        current = self.sources[teamNum - 1]
        self.sources[teamNum - 1] = (
            ManualSource(**current.try_fetch()) if kind == "manual" else SOURCES[kind]()
        )
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
        if not self.editable(teamNum):
            return False

        self.sources[teamNum - 1].players.append(playerName)
        return True

    def remove_player(self, teamNum, playerName):
        if not self.editable(teamNum):
            return False

        players = self.sources[teamNum - 1].players
        if playerName in players:
            players.remove(playerName)
            return True

        return False

    def move_player(self, teamNum, fromIndex, toIndex, playerName):
        """Move the player at fromIndex to toIndex. playerName must still be at
        fromIndex, so a drag made against an outdated roster changes nothing."""
        if not self.editable(teamNum):
            return False

        players = self.sources[teamNum - 1].players
        if not (0 <= fromIndex < len(players) and 0 <= toIndex < len(players)):
            return False
        if players[fromIndex] != playerName:
            return False

        players.insert(toIndex, players.pop(fromIndex))
        return True

    def swap_sides(self):
        self.sources[0], self.sources[1] = self.sources[1], self.sources[0]
        self.scores[0], self.scores[1] = self.scores[1], self.scores[0]

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

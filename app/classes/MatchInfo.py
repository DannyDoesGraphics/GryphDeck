import json


class MatchInfo:
    def __init__(self, max_players=None):
        self.max_players = max_players
        # Players are active
        self.players = [[], []]
        # Roster are all potential (subs)
        self.rosters = [{}, {}]
        self.teams = [("", 0), ("", 0)]

    # expects 1 or 2
    def team_info(self, teamNum):
        if teamNum > 2 or teamNum < 1:
            return None

        return {
            "Name": self.teams[teamNum - 1][0],
            "Score": self.teams[teamNum - 1][1],
            "Players": self.players[teamNum - 1],
        }

    def update_team_name(self, teamNum, name):
        if teamNum > 2 or teamNum < 1:
            return False

        self.teams[teamNum - 1] = (name, self.teams[teamNum - 1][1])
        return True

    def update_team_score(self, teamNum, score):
        if teamNum > 2 or teamNum < 1:
            return False

        self.teams[teamNum - 1] = (self.teams[teamNum - 1][0], score)
        return True

    def load_team(self, teamNum, name, roster):
        """Replace a side's name and roster, keeping its score and activating the first players."""
        if teamNum > 2 or teamNum < 1:
            return False

        self.update_team_name(teamNum, name)
        self.rosters[teamNum - 1] = {
            player: dict(metadata) for player, metadata in roster.items()
        }
        self.players[teamNum - 1] = list(roster)[: self.max_players]
        return True

    def add_player(self, teamNum, playerName):
        """New players start benched when the active set is full."""
        if teamNum > 2 or teamNum < 1:
            return False

        self.rosters[teamNum - 1].setdefault(playerName, {})
        self.set_player_active(teamNum, playerName, True)
        return True

    def remove_player(self, teamNum, playerName):
        if teamNum > 2 or teamNum < 1:
            return False

        if playerName in self.rosters[teamNum - 1]:
            self.set_player_active(teamNum, playerName, False)
            del self.rosters[teamNum - 1][playerName]
            return True

        return False

    def set_player_active(self, teamNum, playerName, active):
        """Keep active players in roster order, refusing more than max_players."""
        if teamNum > 2 or teamNum < 1 or playerName not in self.rosters[teamNum - 1]:
            return False

        selected = set(self.players[teamNum - 1]) - {playerName}
        if (
            active
            and self.max_players is not None
            and len(selected) >= self.max_players
        ):
            return False
        if active:
            selected.add(playerName)
        self.players[teamNum - 1] = [
            player for player in self.rosters[teamNum - 1] if player in selected
        ]
        return True

    def swap_sides(self):
        self.players[0], self.players[1] = self.players[1], self.players[0]
        self.rosters[0], self.rosters[1] = self.rosters[1], self.rosters[0]
        self.teams[0], self.teams[1] = self.teams[1], self.teams[0]

    def __str__(self):
        return json.dumps(
            {
                "team_1": self.team_info(1),
                "team_2": self.team_info(2),
            },
            indent=2,
        )

    def print_info(self):
        """Print both teams, including their scores and players."""
        print(self)

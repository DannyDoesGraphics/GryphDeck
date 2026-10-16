import json


class MatchInfo:
    def __init__(self):
        self.players = [[], []]
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

    def add_player(self, teamNum, playerName):
        if teamNum > 2 or teamNum < 1:
            return False

        self.players[teamNum - 1].append(playerName)
        return True

    def remove_player(self, teamNum, playerName):
        if teamNum > 2 or teamNum < 1:
            return False

        if playerName in self.players[teamNum - 1]:
            self.players[teamNum - 1].remove(playerName)
            return True

        return False

    def swap_sides(self):
        self.players[0], self.players[1] = self.players[1], self.players[0]
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

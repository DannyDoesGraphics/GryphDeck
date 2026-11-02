from .TeamSource import TeamSource


class ManualTeamSource(TeamSource):
    """Manual editing mode."""

    def __init__(self):
        super().__init__("Manual")

    def teams(self):
        return []

    def roster(self, team):
        raise ValueError("Manual has no saved teams.")

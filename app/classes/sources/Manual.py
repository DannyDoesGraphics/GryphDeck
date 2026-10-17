import copy

if __package__:
    from ..TeamSource import TeamSource
else:
    from TeamSource import TeamSource


class ManualSource(TeamSource):
    """A team entered by hand on the control page."""

    kind = "manual"
    label = "Manual"
    description = "Name and roster are entered here."

    def __init__(self, name="", players=(), extra=None):
        super().__init__()
        self.name = name
        self.players = list(players)
        self.extra = copy.deepcopy(extra) if extra else {}

    def current(self):
        """Typed edits show immediately."""
        return self.fetch()

    def fetch(self):
        return {
            "name": self.name,
            "players": list(self.players),
            "extra": copy.deepcopy(self.extra),
        }

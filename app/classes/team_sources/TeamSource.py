import logging
from abc import ABC, abstractmethod
from typing import final

logger = logging.getLogger(__name__)


class TeamSource(ABC):
    """Abstract class for team sources allowing custom team sourcing and roster management."""

    def __init__(self, name):
        self.name = name
        self.error = None

    @classmethod
    def sources(cls):
        """Return one instance per entry this source offers in the team source list."""
        return [cls()]

    @abstractmethod
    def teams(self):
        """Return an iterable of team names."""

    @abstractmethod
    def roster(self, team):
        """Return {player name: {metadata field: value}} for one team."""

    @final
    def fetch_teams(self):
        """Attempt to fetch all teams. Returns empty set on a fail."""
        return self._attempt(lambda: sorted(str(team) for team in self.teams()), [])

    @final
    def fetch_roster(self, team):
        """Attempt to fetch all rosters. Returns `None` on a fail."""
        return self._attempt(
            lambda: {
                str(player): {
                    str(field): str(value) for field, value in metadata.items()
                }
                for player, metadata in self.roster(team).items()
            },
            None,
        )

    @final
    def _attempt(self, fetch, fallback):
        try:
            result = fetch()
        except Exception as error:
            logger.exception("Team source %s failed", self.name)
            self.error = f"Could not fetch from {self.name}: {error}"
            return fallback
        self.error = None
        return result

import importlib.util
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

SOURCE_DIR = Path(__file__).resolve().parent / "sources"
logger = logging.getLogger(__name__)


class TeamSource(ABC):
    """Abstract class that all sources must satisfy"""

    kind: str
    """MUST be unique from other sources"""

    label: str
    """User-facing name"""

    description = ""
    """Note under dropdown"""

    games = ()
    """Game keys (app/json/<Game>.json names) this source works with; empty means every game"""

    def __init__(self):
        self.team = {"name": "", "players": [], "extra": {}}
        """Empty team by default"""

        self.error = None
        """Last error to prevent log spam"""

        self.fetched = False
        """Whether fetch() has been tried"""

    @abstractmethod
    def fetch(self) -> dict[str, Any]:
        """Return {"name": str, "players": [str], "extra": dict}."""

    def current(self):
        """The last fetched team, fetched the first time it is needed"""
        if not self.fetched:
            self.try_fetch()
        return self.team

    def refresh(self):
        """fetch() again on request"""
        self.try_fetch()
        if self.error:
            raise ValueError(self.error)

    def try_fetch(self):
        """fetch(), applied only if it succeeds"""
        self.fetched = True
        try:
            self.team = self.fetch()
            self.error = None
        except Exception as error:
            if self.error is None:  # log once, not on every state request
                logger.exception("%s source failed", self.label)
            self.error = f"{type(error).__name__}: {error}"
        return self.team


def load_sources(directory=SOURCE_DIR):
    """Import every source file. Fails silently pass through"""
    sources = {}
    for path in sorted(directory.glob("*.py")):
        name = f"{__package__}.sources.{path.stem}" if __package__ else path.stem
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load {path.name}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            logger.exception("Skipped source file %s", path.name)
            continue
        sources.update(
            (value.kind, value)
            for value in vars(module).values()
            if isinstance(value, type)
            and issubclass(value, TeamSource)
            and value.__module__ == name
        )
    return {"manual": sources.pop("manual"), **sources}


SOURCES = load_sources()
ManualSource = SOURCES["manual"]


def supports(source, game):
    """Whether `source` can be used while `game` is loaded."""
    return not source.games or game in source.games

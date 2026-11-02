import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def available_team_sources():
    """Import every FooTeamSource.py here, skipping any that fail."""
    sources = {}
    for path in sorted(Path(__file__).parent.glob("?*TeamSource.py")):
        try:
            module = importlib.import_module(f"{__package__}.{path.stem}")
            sources.update(
                (source.name, source) for source in getattr(module, path.stem).sources()
            )
        except Exception:
            logger.exception("Skipping team source %s", path.stem)
    return sources


def team_source_names():
    return list(available_team_sources())


def load_team_source(name):
    source = available_team_sources().get(name)
    if source is None:
        raise ValueError("Choose a team source from the available list.")
    return source

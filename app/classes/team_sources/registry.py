from pathlib import Path

from .CsvTeamSource import CsvTeamSource
from .ManualTeamSource import ManualTeamSource

TEAM_DIR = Path(__file__).resolve().parent.parent.parent / "teams"


def team_source_names():
    return ["Manual", *sorted(path.stem for path in TEAM_DIR.glob("*.csv"))]


def load_team_source(name):
    if name == "Manual":
        return ManualTeamSource()
    if name not in team_source_names():
        raise ValueError("Choose a team source from the available list.")
    return CsvTeamSource(TEAM_DIR / f"{name}.csv")

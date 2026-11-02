import csv
from pathlib import Path

from .TeamSource import TeamSource

TEAM_DIR = Path(__file__).resolve().parent.parent.parent / "teams"


class CsvTeamSource(TeamSource):
    """Importing of team rosters via CSV files."""

    def __init__(self, path):
        super().__init__(Path(path).stem)
        self.path = Path(path)

    @classmethod
    def sources(cls):
        return [cls(path) for path in sorted(TEAM_DIR.glob("*.csv"))]

    def teams(self):
        return self.rosters()

    def roster(self, team):
        rosters = self.rosters()
        if team not in rosters:
            raise ValueError(f"{team} is not in {self.name}.csv.")
        return rosters[team]

    def rosters(self):
        rosters = {}
        with self.path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if not {"Team", "Player"} <= set(reader.fieldnames or []):
                raise ValueError(
                    f"{self.name}.csv needs Team and Player column headings."
                )
            for row in reader:
                team = (row["Team"] or "").strip()
                player = (row["Player"] or "").strip()
                if not team or not player:
                    continue
                rosters.setdefault(team, {})[player] = {
                    field.strip(): value.strip()
                    for field, value in row.items()
                    if field not in (None, "Team", "Player") and value and value.strip()
                }
        return rosters

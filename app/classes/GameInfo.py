import json
from pathlib import Path


class GameInfo:
    def __init__(self, name):
        self.name = name
        self.element_positions = []
        self.enabled_components = []

        self.maps = []
        self.chars = []

        self.load_game_info(self.name)

    def load_game_info(self, game_name):
        config_path = (
            Path(__file__).resolve().parent.parent / "json" / f"{game_name}.json"
        )
        with config_path.open(mode="r", encoding="utf-8") as json_file:
            data = json.load(json_file)
            self.name = data["name"]
            self.element_positions = data["element_positions"]
            self.enabled_components = data["enabled_components"]
            self.maps = data["maps"]
            self.chars = data["chars"]

    def __str__(self):
        return json.dumps(
            {
                "name": self.name,
                "element_positions": self.element_positions,
                "enabled_components": self.enabled_components,
                "maps": self.maps,
                "chars": self.chars,
            },
            indent=2,
        )

    def ban_options(self):
        """Use configured components, not their current on-screen toggle state."""
        components = {name.casefold() for name in self.enabled_components}
        return {
            "map": {
                "supported": any(
                    "map" in name and ("pick" in name or "ban" in name)
                    for name in components
                ),
                "choices": self.maps,
            },
            "hero": {
                "supported": any(
                    ("character" in name or "hero" in name) and "ban" in name
                    for name in components
                ),
                "choices": self.chars,
            },
        }

    def print_info(self):
        """Print the game's configuration for debugging."""
        print(self)

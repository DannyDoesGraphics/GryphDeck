import json

if __package__:
    from .GameInfo import GameInfo
    from .MatchInfo import MatchInfo
else:
    from GameInfo import GameInfo
    from MatchInfo import MatchInfo


class StateManager:
    def __init__(self, game_name="Valorant"):
        self.game_info = GameInfo(game_name)
        self.game_key = game_name
        self.current_scene = "idle"

        self.match_info = MatchInfo()
        self.bans = {"map": [], "hero": []}

        self.current_idle_components = []  # (component_name, position, enabled)
        self.current_pregame_components = []  # (component_name, position, enabled)
        self.current_ingame_components = []  # (component_name, position, enabled)

        self.load_components(self.game_info)

    def load_game(self, game_name):
        """Reset game components and bans while retaining teams and selected scene."""
        replacement = StateManager(game_name)
        self.game_info = replacement.game_info
        self.game_key = replacement.game_key
        self.current_idle_components = replacement.current_idle_components
        self.current_pregame_components = replacement.current_pregame_components
        self.current_ingame_components = replacement.current_ingame_components
        self.bans = replacement.bans

    def update_ban(self, kind, name, *, remove=False):
        options = self.game_info.ban_options()
        if not isinstance(kind, str) or kind not in options:
            raise ValueError("Ban type must be map or hero.")
        selection = "picks" if kind == "map" else "bans"
        selected_word = "picked" if kind == "map" else "banned"
        if not options[kind]["supported"]:
            raise ValueError(f"This game does not have {kind} {selection}.")
        canonical = next(
            (
                choice
                for choice in options[kind]["choices"]
                if choice.casefold() == name.casefold()
            ),
            None,
        )
        if canonical is None:
            raise ValueError(f"Choose a {kind} from the current game's list.")
        selected = self.bans[kind]
        if remove:
            if canonical not in selected:
                raise ValueError(f"That {kind} is no longer {selected_word}.")
            selected.remove(canonical)
        else:
            if canonical in selected:
                raise ValueError(f"That {kind} is already {selected_word}.")
            selected.append(canonical)

    def load_components(self, game_info):
        """Load disabled components, adding shared components to every scene."""
        scene_components = {
            "idle": self.current_idle_components,
            "pregame": self.current_pregame_components,
            "ingame": self.current_ingame_components,
        }
        for components in scene_components.values():
            components.clear()

        for component_name in game_info.enabled_components:
            component = next(
                elem
                for elem in game_info.element_positions
                if elem["Name"] == component_name
            )
            scene = component["Scene"].lower()
            for scene_name, components in scene_components.items():
                if scene == "all" or scene == scene_name:
                    components.append([component_name, component["Position"], False])

    def enable_component(self, scene, component_name):
        # Find the component list
        component_list = []
        match scene:
            case "idle":
                component_list = self.current_idle_components
            case "pregame":
                component_list = self.current_pregame_components
            case "ingame":
                component_list = self.current_ingame_components

        # Update the copied list
        for component in component_list:
            if component[0] == component_name:
                component[2] = True
                for other_component in component_list:
                    if (
                        other_component[1] == component[1]
                        and other_component[0] != component_name
                        and other_component[2] == True
                    ):
                        other_component[2] = False
                break

        # Set the list
        match scene:
            case "idle":
                self.current_idle_components = component_list
            case "pregame":
                self.current_pregame_components = component_list
            case "ingame":
                self.current_ingame_components = component_list

    def disable_component(self, scene, component_name):
        # Find the component list
        component_list = []
        match scene:
            case "idle":
                component_list = self.current_idle_components
            case "pregame":
                component_list = self.current_pregame_components
            case "ingame":
                component_list = self.current_ingame_components

        # Update the copied list
        for component in component_list:
            if component[0] == component_name and component[2] == True:
                component[2] = False
                break

        # Set the list
        match scene:
            case "idle":
                self.current_idle_components = component_list
            case "pregame":
                self.current_pregame_components = component_list
            case "ingame":
                self.current_ingame_components = component_list

    def create_post_request(self):
        """Return a JSON document containing the enabled overlays for every scene.

        Each component has a name, its configured location and scale, and display data.
        Team arrays are ordered left then right. Static overlays receive game
        and scene context; dynamic overlays also receive their current values.
        This builds the request body; the caller handles its transport.
        """
        scales = {
            element["Name"]: element.get("Scale", 1)
            for element in self.game_info.element_positions
        }
        scenes = {}
        for scene in ("idle", "pregame", "ingame"):
            scenes[scene] = []
            for name, location, enabled in getattr(self, f"current_{scene}_components"):
                if not enabled:
                    continue
                data = {"game": self.game_info.name, "scene": scene}
                component = name.casefold()
                if component == "team roster":
                    data["teams"] = [
                        {
                            "name": self.match_info.team_info(team)["Name"],
                            "players": self.match_info.team_info(team)["Players"],
                        }
                        for team in (1, 2)
                    ]
                elif component.startswith("score "):
                    data["teams"] = [
                        {
                            "name": self.match_info.team_info(team)["Name"],
                            "score": self.match_info.team_info(team)["Score"],
                        }
                        for team in (1, 2)
                    ]
                elif "map" in component and "pick" in component:
                    data["map_picks"] = self.bans["map"]
                elif (
                    "character" in component or "hero" in component
                ) and "ban" in component:
                    data["hero_bans"] = self.bans["hero"]
                scenes[scene].append(
                    {
                        "name": name,
                        "location": location,
                        "scale": scales.get(name, 1),
                        "data": data,
                    }
                )
        return json.dumps(
            {"game": self.game_info.name, "scenes": scenes},
            ensure_ascii=False,
            indent=2,
        )

    def __str__(self):
        return json.dumps(
            {
                "game": self.game_info.name,
                "team_1": self.match_info.team_info(1),
                "team_2": self.match_info.team_info(2),
                "components (name, position, enabled)": {
                    "idle": self.current_idle_components,
                    "pregame": self.current_pregame_components,
                    "ingame": self.current_ingame_components,
                },
            },
            indent=2,
        )

    def print_info(self):
        """Print the game, match, and component state for every scene."""
        print(self)


# Scene
# Components

# Scene (Idle, Pregame, Ingame)
# Screen (Score Pregame, Starting Soon, Tech Pauce, etc.)
# Components (Sponsorship Badge, Chartacter Bans Ingame, etc)

# /idle
# /pregame
# /ingame

# backend - all the configuration (including UI)

# frontend - all rendering

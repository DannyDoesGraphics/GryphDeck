import json

if __package__:
    from .GameInfo import GameInfo
    from .MatchInfo import MatchInfo
    from . import SideDetection
else:
    from GameInfo import GameInfo
    from MatchInfo import MatchInfo
    import SideDetection

# Deadlock match phases (OnGameStateChanged ids) before the game is in progress. Entering
# one of these after any later phase (or none) means a new match: the sides are unknown again.
PREGAME_PHASES = range(0, 7)

class StateManager:

    def __init__(self, game_name="Valorant"):
        self.game_info = GameInfo(game_name)
        self.game_key = game_name
        self.current_scene = "idle"

        self.match_info = MatchInfo()
        self.bans = {"map": [], "hero": []}
        self.draft = self.empty_draft(self.game_info)
        self.sides = self.empty_sides()
        self.side_report = None  # the game's last parsed side report, re-checked after roster/draft edits

        self.current_idle_components = [] # (component_name, position, enabled)
        self.current_pregame_components = [] # (component_name, position, enabled)
        self.current_ingame_components = [] # (component_name, position, enabled)

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
        self.draft = replacement.draft
        self.sides = replacement.sides
        self.side_report = replacement.side_report

    @staticmethod
    def empty_draft(game_info):
        """Per-team pick and ban slots for games whose JSON defines a draft."""
        if not game_info.draft:
            return None
        return {
            "label": "",
            "first_pick": 0,  # 0 = not shown, otherwise team 1 or 2
            "player_names": True,  # False shows hero picks only, without player names
            "teams": [
                {"picks": [None] * game_info.draft["picks"], "bans": [None] * game_info.draft["bans"]}
                for _ in (1, 2)
            ],
        }

    @staticmethod
    def empty_sides():
        """Whether the overlays know which in-game side each team is on.

        Until they do, team colours stay grey. "auto" lets the Deadlock side reporter
        (POST /api/deadlock) set them; "attention" means detection gave up and the operator
        has to choose; "phase" is the last match phase the game reported.
        """
        return {"known": False, "auto": True, "attention": False, "status": "Sides not known yet.",
                "phase": None, "phase_id": None}

    def set_sides(self, **changes):
        """Operator control.

        left: which in-game side the left team is on (1 Hidden King, 2 Archmother); 2 swaps the
        teams so the left team is always the Hidden King, then shows the colours.
        known: False turns the colours back to grey. auto: side detection on/off.
        """
        if "left" in changes and (type(changes["left"]) is not int or changes["left"] not in (1, 2)):
            raise ValueError("Left side must be 1 (Hidden King) or 2 (Archmother).")
        for key in ("known", "auto"):
            if key in changes and type(changes[key]) is not bool:
                raise ValueError(f"Sides {key} must be true or false.")
        if "left" in changes:
            if changes["left"] == 2:
                self.swap_sides()
            self.sides.update(known=True, attention=False, status="Set by hand.")
        if "known" in changes:
            self.sides["known"] = changes["known"]
            self.sides["attention"] = False
            self.sides["status"] = "Set by hand." if changes["known"] else "Sides not known yet."
        if "auto" in changes:
            self.sides["auto"] = changes["auto"]

    def apply_deadlock_event(self, event):
        """Apply a match phase or side report from Deadlock; returns True if the overlays change."""
        if not isinstance(event, dict):
            raise ValueError("Expected a JSON object.")
        was_known = self.sides["known"]
        swapped = False
        if event.get("type") == "state":
            phase, phase_id = event.get("state"), event.get("id")
            if not isinstance(phase, str) or len(phase) > 40 or type(phase_id) is not int:
                raise ValueError("A state event needs a phase name and id.")
            previous = self.sides["phase_id"]
            new_match = phase_id in PREGAME_PHASES and (previous is None or previous not in PREGAME_PHASES)
            self.sides["phase"], self.sides["phase_id"] = phase, phase_id
            if new_match:
                self.side_report = None
            if new_match and self.sides["auto"]:
                self.sides.update(known=False, attention=False,
                                  status="New match: waiting for sides.")
        elif event.get("type") == "teams":
            self.side_report = SideDetection.parse_teams(event.get("teams"))
            swapped = self.redetect_sides()
        else:
            raise ValueError("Unknown Deadlock event.")
        return swapped or self.sides["known"] != was_known

    def redetect_sides(self):
        """Match the game's last side report against the rosters and draft, if still needed.

        Called for each report and after the operator edits rosters or picks, so a fix applies
        at once. Returns True if the teams were swapped.
        """
        if self.side_report is None or not self.sides["auto"] or self.sides["known"]:
            return False
        rosters = [self.match_info.team_info(team)["Players"] for team in (1, 2)]
        picks = [team["picks"] for team in self.draft["teams"]] if self.draft else [[], []]
        decision, reason, stuck = SideDetection.detect(self.side_report, rosters, picks)
        if decision is None:
            self.sides["attention"] = stuck
            self.sides["status"] = (f"Can't tell sides: {reason}."
                                    if stuck else f"Detecting: {reason}.")
            return False
        if decision == "swap":
            self.swap_sides()
        self.sides.update(known=True, attention=False, status=f"Detected from {reason}"
                          + ("; teams swapped." if decision == "swap" else "."))
        return decision == "swap"

    def set_draft_slot(self, team, kind, slot, hero, move=False):
        """Place a hero in one team's pick or ban slot; None clears the slot.

        A hero can occupy only one slot across both teams' picks and bans: with move, a hero
        already in another slot leaves it for this one.
        """
        if self.draft is None:
            raise ValueError("This game does not have a hero draft.")
        if type(team) is not int or team not in (1, 2):
            raise ValueError("Team must be 1 or 2.")
        if kind not in ("picks", "bans"):
            raise ValueError("Draft slot must be a pick or a ban.")
        slots = self.draft["teams"][team - 1][kind]
        if type(slot) is not int or not 0 <= slot < len(slots):
            raise ValueError(f"Choose a {kind[:-1]} slot from 1 to {len(slots)}.")
        if hero is not None:
            if not isinstance(hero, str):
                raise ValueError("Choose a hero from the current game's list.")
            hero = next((name for name in self.game_info.chars if name.casefold() == hero.strip().casefold()), None)
            if hero is None:
                raise ValueError("Choose a hero from the current game's list.")
            for index, other in enumerate(self.draft["teams"]):
                for other_kind in ("picks", "bans"):
                    for other_slot, name in enumerate(other[other_kind]):
                        if name == hero and (index, other_kind, other_slot) != (team - 1, kind, slot):
                            if move:
                                other[other_kind][other_slot] = None
                                continue
                            selection = "picked" if other_kind == "picks" else "banned"
                            raise ValueError(f"{hero} is already {selection} by team {index + 1}.")
        slots[slot] = hero

    def pick_players(self, team):
        """The player under each pick: roster player N drafted pick N; None for hero picks only."""
        picks = self.draft["teams"][team - 1]["picks"]
        if not self.draft["player_names"]:
            return [None] * len(picks)
        players = self.match_info.team_info(team)["Players"]
        return [players[slot] if slot < len(players) else None for slot in range(len(picks))]

    def set_draft_details(self, **changes):
        """Update the draft's match label and/or first pick (0 hides the marker)."""
        if self.draft is None:
            raise ValueError("This game does not have a hero draft.")
        if "first_pick" in changes:
            first_pick = changes["first_pick"]
            if type(first_pick) is not int or first_pick not in (0, 1, 2):
                raise ValueError("First pick must be none, team 1, or team 2.")
        if "label" in changes:
            label = changes["label"]
            if not isinstance(label, str) or len(label.strip()) > 80:
                raise ValueError("Match label must be text of up to 80 characters.")
            changes["label"] = label.strip()
        if "player_names" in changes and type(changes["player_names"]) is not bool:
            raise ValueError("Player names must be on or off.")
        self.draft.update((key, changes[key]) for key in ("first_pick", "label", "player_names") if key in changes)

    def remove_player(self, team, player):
        """Remove a player; later players keep their own picks (roster player N drafted pick N)."""
        players = self.match_info.players[team - 1]
        if player not in players:
            return False
        slot = players.index(player)
        self.match_info.remove_player(team, player)
        if self.draft is not None:
            picks = self.draft["teams"][team - 1]["picks"]
            if slot < len(picks):
                del picks[slot]
                picks.append(None)
        return True

    def swap_sides(self):
        """Swap teams and their draft, so each team keeps its own picks and bans."""
        self.match_info.swap_sides()
        if self.draft is not None:
            teams = self.draft["teams"]
            teams[0], teams[1] = teams[1], teams[0]
            self.draft["first_pick"] = {0: 0, 1: 2, 2: 1}[self.draft["first_pick"]]

    def update_ban(self, kind, name, *, remove=False):
        options = self.game_info.ban_options()
        if not isinstance(kind, str) or kind not in options:
            raise ValueError("Ban type must be map or hero.")
        selection = "picks" if kind == "map" else "bans"
        selected_word = "picked" if kind == "map" else "banned"
        if not options[kind]["supported"]:
            raise ValueError(f"This game does not have {kind} {selection}.")
        canonical = next((choice for choice in options[kind]["choices"] if choice.casefold() == name.casefold()), None)
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
                elem for elem in game_info.element_positions
                if elem['Name'] == component_name
            )
            scene = component['Scene'].lower()
            for scene_name, components in scene_components.items():
                if scene == "all" or scene == scene_name:
                    components.append([component_name, component['Position'], False])

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
                    if other_component[1] == component[1] and other_component[0] != component_name and other_component[2] == True:
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

        Each component has a name, its configured location, and display data.
        Team arrays are ordered left then right. Static overlays receive game
        and scene context; dynamic overlays also receive their current values.
        This builds the request body; the caller handles its transport.
        """
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
                        {"name": self.match_info.team_info(team)["Name"],
                         "players": self.match_info.team_info(team)["Players"]}
                        for team in (1, 2)
                    ]
                elif component.startswith("score "):
                    data["teams"] = [
                        {"name": self.match_info.team_info(team)["Name"],
                         "score": self.match_info.team_info(team)["Score"]}
                        for team in (1, 2)
                    ]
                elif component in ("hero draft", "deadlock top bar"):
                    # A game JSON without a "draft" section shows empty teams rather than failing.
                    draft = self.draft or {"label": "", "first_pick": 0,
                                           "teams": [{"picks": [], "bans": []}, {"picks": [], "bans": []}]}
                    data["label"] = draft["label"]
                    data["first_pick"] = draft["first_pick"]
                    data["sides_known"] = self.sides["known"]
                    data["teams"] = [
                        {"name": self.match_info.team_info(team)["Name"],
                         "score": self.match_info.team_info(team)["Score"],
                         "players": self.match_info.team_info(team)["Players"],
                         "picks": draft["teams"][team - 1]["picks"],
                         "pick_players": self.pick_players(team) if self.draft else [],
                         "bans": draft["teams"][team - 1]["bans"]}
                        for team in (1, 2)
                    ]
                elif "map" in component and "pick" in component:
                    data["map_picks"] = self.bans["map"]
                elif ("character" in component or "hero" in component) and "ban" in component:
                    data["hero_bans"] = self.bans["hero"]
                scenes[scene].append({"name": name, "location": location, "data": data})
        return json.dumps({"game": self.game_info.name, "scenes": scenes}, ensure_ascii=False, indent=2)

    def __str__(self):
        return json.dumps({
            "game": self.game_info.name,
            "team_1": self.match_info.team_info(1),
            "team_2": self.match_info.team_info(2),
            "components (name, position, enabled)": {
                "idle": self.current_idle_components,
                "pregame": self.current_pregame_components,
                "ingame": self.current_ingame_components,
            },
        }, indent=2)

    def print_info(self):
        """Print the game, match, and component state for every scene."""
        print(self)

# Scene
# Components

# Scene (Idle, Pregame, Ingame)
# Screen (Score Pregame, Starting Soon, Tech Pauce, etc.)
# Components (Sponsorship Badge, Chartacter Bans Ingame, etc)

#/idle
#/pregame
#/ingame

#backend - all the configuration (including UI)

#frontend - all rendering

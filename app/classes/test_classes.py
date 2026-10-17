"""Run with `python app/classes/test_classes.py`; add --demo to print examples."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

if __package__:
    from .GameInfo import GameInfo
    from .MatchInfo import MatchInfo
    from .StateManager import StateManager
    from .TeamSource import (
        SOURCE_DIR,
        ManualSource,
        TeamSource,
        load_sources,
    )
    from .TeamSource import logger as source_log
else:
    from GameInfo import GameInfo
    from MatchInfo import MatchInfo
    from StateManager import StateManager
    from TeamSource import (
        SOURCE_DIR,
        ManualSource,
        TeamSource,
        load_sources,
    )
    from TeamSource import logger as source_log


IMPORT = """if __package__:
    from ..TeamSource import TeamSource
else:
    from TeamSource import TeamSource
"""
CONFIG_DIR = Path(__file__).resolve().parent.parent / "json"
MANUAL = {"Kind": "manual", "Label": "Manual", "Error": None}


class LockedSource(TeamSource):
    """A read-only source standing in for one fetched from elsewhere."""

    kind = "locked"
    label = "Locked"

    def fetch(self):
        return {"name": "Fetched", "players": ["Remote"], "extra": {"wins": 4}}


class ValorantSource(TeamSource):
    """A source that only works while Valorant is loaded."""

    kind = "valorant"
    label = "Valorant only"
    games = ("Valorant",)

    def fetch(self):
        return {"name": "Valorant Team", "players": ["Agent"], "extra": {}}


class FlakySource(LockedSource):
    """A read-only source whose fetch() raises `failure` once it is set."""

    kind = "flaky"
    label = "Flaky"
    failure = None

    def fetch(self):
        if self.failure:
            raise self.failure
        return super().fetch()


class GameInfoTests(unittest.TestCase):
    def test_load_every_game_configuration(self):
        paths = list(CONFIG_DIR.glob("*.json"))
        self.assertTrue(paths, "No game configurations found")
        for path in paths:
            with self.subTest(game=path.stem):
                data = json.loads(path.read_text(encoding="utf-8"))
                game = GameInfo(path.stem)
                for field in (
                    "name",
                    "element_positions",
                    "enabled_components",
                    "maps",
                    "chars",
                ):
                    self.assertEqual(getattr(game, field), data[field])

    def test_reload_replaces_configuration(self):
        game = GameInfo("Valorant")
        game.load_game_info("Miscellaneous")
        expected = GameInfo("Miscellaneous")
        self.assertEqual(vars(game), vars(expected))

    def test_missing_game_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            GameInfo("__missing_test_game__")


class MatchInfoTests(unittest.TestCase):
    def setUp(self):
        self.match = MatchInfo()

    def test_initial_teams(self):
        for team in (1, 2):
            self.assertEqual(
                self.match.team_info(team),
                {
                    "Name": "",
                    "Score": 0,
                    "Players": [],
                    "Source": MANUAL,
                    "Extra": {},
                },
            )

    def test_update_names_and_scores(self):
        for team, name, score in ((1, "Gryphons", 3), (2, "Rivals", 1)):
            self.assertTrue(self.match.update_team_name(team, name))
            self.assertTrue(self.match.update_team_score(team, score))
            self.assertEqual(
                self.match.team_info(team),
                {
                    "Name": name,
                    "Score": score,
                    "Players": [],
                    "Source": MANUAL,
                    "Extra": {},
                },
            )

    def test_add_and_remove_players(self):
        self.assertTrue(self.match.add_player(1, "Player One"))
        self.assertTrue(self.match.add_player(1, "Player Two"))
        self.assertTrue(self.match.add_player(2, "Opponent"))
        self.assertTrue(self.match.remove_player(1, "Player One"))
        self.assertFalse(self.match.remove_player(1, "Missing Player"))
        self.assertEqual(self.match.team_info(1)["Players"], ["Player Two"])
        self.assertEqual(self.match.team_info(2)["Players"], ["Opponent"])

    def test_move_player_reorders_the_roster(self):
        for name in ("A", "B", "C", "D"):
            self.match.add_player(1, name)
        self.assertTrue(self.match.move_player(1, 0, 2, "A"))
        self.assertEqual(self.match.team_info(1)["Players"], ["B", "C", "A", "D"])
        self.assertTrue(self.match.move_player(1, 3, 0, "D"))
        self.assertEqual(self.match.team_info(1)["Players"], ["D", "B", "C", "A"])

    def test_move_player_rejects_outdated_or_invalid_moves(self):
        for name in ("A", "B", "C"):
            self.match.add_player(1, name)
        self.assertFalse(self.match.move_player(1, 0, 2, "B"))
        self.assertFalse(self.match.move_player(1, 0, 3, "A"))
        self.assertFalse(self.match.move_player(1, -1, 0, "C"))
        self.assertFalse(self.match.move_player(2, 0, 0, "A"))
        self.assertEqual(self.match.team_info(1)["Players"], ["A", "B", "C"])

    def test_invalid_team_numbers_leave_match_unchanged(self):
        before = str(self.match)
        for team in (-1, 0, 3):
            with self.subTest(team=team):
                self.assertIsNone(self.match.team_info(team))
                self.assertFalse(self.match.update_team_name(team, "Invalid"))
                self.assertFalse(self.match.update_team_score(team, 10))
                self.assertFalse(self.match.add_player(team, "Invalid"))
                self.assertFalse(self.match.remove_player(team, "Invalid"))
        self.assertEqual(str(self.match), before)

    def test_swap_sides_moves_names_scores_and_players(self):
        for team in (1, 2):
            self.match.update_team_name(team, f"Team {team}")
            self.match.update_team_score(team, team * 2)
            self.match.add_player(team, f"Player {team}")
        before = [self.match.team_info(1), self.match.team_info(2)]
        self.match.swap_sides()
        self.assertEqual(self.match.team_info(1), before[1])
        self.assertEqual(self.match.team_info(2), before[0])
        self.match.swap_sides()
        self.assertEqual(self.match.team_info(1), before[0])
        self.assertEqual(self.match.team_info(2), before[1])

    def test_manual_source_keeps_current_team(self):
        self.match.update_team_name(1, "Gryphons")
        self.match.add_player(1, "Captain")
        self.match.sources[0].extra["wins"] = 2
        before = self.match.team_info(1)
        self.assertTrue(self.match.set_source(1, "manual"))
        self.assertEqual(self.match.team_info(1), before)
        self.assertFalse(self.match.set_source(3, "manual"))
        with self.assertRaises(ValueError):
            self.match.set_source(1, "unknown")
        self.assertEqual(self.match.team_info(1), before)

    def test_locked_source_rejects_name_and_roster_edits(self):
        self.match.sources[0] = LockedSource()
        before = self.match.team_info(1)
        self.assertFalse(self.match.editable(1))
        self.assertFalse(self.match.update_team_name(1, "Changed"))
        self.assertFalse(self.match.add_player(1, "Extra"))
        self.assertFalse(self.match.remove_player(1, "Remote"))
        self.assertEqual(self.match.team_info(1), before)
        self.assertTrue(self.match.update_team_score(1, 2))
        self.assertEqual(self.match.team_info(1)["Score"], 2)
        self.match.set_source(1, "manual")
        self.assertEqual(
            self.match.team_info(1),
            {
                "Name": "Fetched",
                "Score": 2,
                "Players": ["Remote"],
                "Source": MANUAL,
                "Extra": {"wins": 4},
            },
        )
        self.assertTrue(self.match.add_player(1, "Extra"))

    def test_swap_sides_moves_sources(self):
        self.match.sources[0] = LockedSource()
        self.match.swap_sides()
        self.assertTrue(self.match.editable(1))
        self.assertFalse(self.match.editable(2))
        self.assertEqual(self.match.team_info(2)["Name"], "Fetched")


class TeamSourceTests(unittest.TestCase):
    def test_manual_snapshot_is_a_copy(self):
        source = ManualSource("Gryphons", ["Captain"], {"stats": {"wins": 1}})
        snapshot = source.fetch()
        snapshot["players"].append("Intruder")
        snapshot["extra"]["stats"]["wins"] = 9
        self.assertEqual(
            source.fetch(),
            {
                "name": "Gryphons",
                "players": ["Captain"],
                "extra": {"stats": {"wins": 1}},
            },
        )

    def test_switching_to_manual_keeps_the_team(self):
        match = MatchInfo()
        match.sources[0] = LockedSource()
        self.assertTrue(match.set_source(1, "manual"))
        self.assertIsInstance(match.sources[0], ManualSource)
        self.assertEqual(match.sources[0].fetch(), LockedSource().fetch())
        for kind in ("unknown", "", None, ["manual"], {"kind": "manual"}):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                match.set_source(1, kind)

    def test_failing_fetch_keeps_the_team(self):
        match = MatchInfo()
        source = match.sources[1] = FlakySource()

        def fetched(error):
            return {
                "Name": "Fetched",
                "Score": 0,
                "Players": ["Remote"],
                "Extra": {"wins": 4},
                "Source": {
                    "Kind": "flaky",
                    "Label": "Flaky",
                    "Error": error,
                },
            }

        self.assertEqual(match.team_info(2), fetched(None))
        source.failure = RuntimeError("feed down")
        with self.assertLogs(source_log, "ERROR"):
            self.assertEqual(match.team_info(2), fetched("RuntimeError: feed down"))
        match.set_source(2, "manual")
        self.assertEqual(match.sources[1].fetch(), LockedSource().fetch())
        match.sources[1] = source
        source.failure = None
        self.assertEqual(match.team_info(2), fetched(None))

    def test_load_sources_skips_files_that_fail_to_import(self):
        files = {
            "Manual.py": (SOURCE_DIR / "Manual.py").read_text(encoding="utf-8"),
            "Alpha.py": IMPORT
            + "class Alpha(TeamSource):\n    kind = 'alpha'\n    label = 'Alpha'\n    def fetch(self): return {}\n",
            "Syntax.py": "def broken(:\n",
            "Crash.py": "raise RuntimeError('import failed')\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            for name, text in files.items():
                Path(directory, name).write_text(text, encoding="utf-8")
            with self.assertLogs(source_log, "ERROR"):
                sources = load_sources(Path(directory))
        self.assertEqual(list(sources), ["manual", "alpha"])


class StateManagerTests(unittest.TestCase):
    def setUp(self):
        self.state = StateManager("Valorant")

    def test_load_game_moves_unsupported_sources_to_manual(self):
        match = self.state.match_info
        match.sources = [ValorantSource(), LockedSource()]
        self.state.load_game("Valorant")
        self.assertIsInstance(match.sources[0], ValorantSource)
        self.state.load_game("Overwatch")
        self.assertIsInstance(match.sources[0], ManualSource)
        self.assertEqual(match.sources[0].fetch(), ValorantSource().fetch())
        self.assertIsInstance(match.sources[1], LockedSource)

    def test_initial_game_and_match(self):
        self.assertIsInstance(self.state.game_info, GameInfo)
        self.assertEqual(self.state.game_info.name, "Valorant")
        self.assertIsInstance(self.state.match_info, MatchInfo)

    def test_scene_assignment_for_every_game(self):
        for path in CONFIG_DIR.glob("*.json"):
            state = StateManager(path.stem)
            for scene in ("idle", "pregame", "ingame"):
                with self.subTest(game=path.stem, scene=scene):
                    expected = [
                        [component["Name"], component["Position"], False]
                        for component in state.game_info.element_positions
                        if component["Name"] in state.game_info.enabled_components
                        and component["Scene"].lower() in (scene, "all")
                    ]
                    self.assertCountEqual(
                        getattr(state, f"current_{scene}_components"),
                        expected,
                    )

    def test_enable_and_disable_in_each_scene(self):
        for scene, name in (
            ("idle", "Starting Soon"),
            ("pregame", "Team Roster"),
            ("ingame", "Score Ingame"),
        ):
            with self.subTest(scene=scene):
                components = getattr(self.state, f"current_{scene}_components")
                component = next(item for item in components if item[0] == name)
                self.state.enable_component(scene, name)
                self.assertTrue(component[2])
                self.state.disable_component(scene, name)
                self.assertFalse(component[2])

    def test_same_position_conflict_preserves_other_positions(self):
        self.state.enable_component("pregame", "Sponsorships Badge")
        self.state.enable_component("pregame", "Team Roster")
        self.state.enable_component("pregame", "Score Pregame")
        enabled = {
            name
            for name, position, active in self.state.current_pregame_components
            if active
        }
        self.assertEqual(enabled, {"Score Pregame", "Sponsorships Badge"})

    def test_shared_components_have_independent_scene_state(self):
        self.state.enable_component("idle", "Sponsorships Badge")
        for scene in ("idle", "pregame", "ingame"):
            components = getattr(self.state, f"current_{scene}_components")
            badge = next(item for item in components if item[0] == "Sponsorships Badge")
            self.assertEqual(badge[2], scene == "idle")

    def test_unknown_scene_or_component_is_a_no_op(self):
        self.state.enable_component("idle", "Starting Soon")
        before = str(self.state)
        for operation in (self.state.enable_component, self.state.disable_component):
            operation("unknown", "Starting Soon")
            operation("idle", "Unknown Component")
        self.assertEqual(str(self.state), before)

    def test_reloading_resets_state_without_duplicates(self):
        before = str(self.state)
        self.state.enable_component("idle", "Starting Soon")
        self.state.load_components(self.state.game_info)
        self.assertEqual(str(self.state), before)

    def test_instances_do_not_share_mutable_state(self):
        other = StateManager("Valorant")
        before = str(other)
        self.state.match_info.add_player(1, "Player One")
        self.state.enable_component("idle", "Starting Soon")
        self.state.game_info.maps.append("Test Map")
        self.assertEqual(str(other), before)
        self.assertNotIn("Test Map", other.game_info.maps)

    def test_post_request_includes_all_scenes_and_only_enabled_components(self):
        self.assertEqual(
            json.loads(self.state.create_post_request()),
            {
                "game": "Valorant",
                "scenes": {"idle": [], "pregame": [], "ingame": []},
            },
        )
        self.state.enable_component("idle", "Starting Soon")
        self.state.enable_component("idle", "Sponsorships Badge")
        self.state.enable_component("pregame", "Team Roster")
        self.state.enable_component("pregame", "Score Pregame")
        self.state.enable_component("ingame", "Score Ingame")
        self.state.current_scene = "ingame"
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual(
            {c["name"] for c in scenes["idle"]}, {"Starting Soon", "Sponsorships Badge"}
        )
        self.assertEqual([c["name"] for c in scenes["pregame"]], ["Score Pregame"])
        self.assertEqual(scenes["ingame"][0]["location"], "BottomCenter")
        for component in scenes["idle"]:
            self.assertEqual(component["data"], {"game": "Valorant", "scene": "idle"})
        self.state.disable_component("ingame", "Score Ingame")
        self.assertEqual(
            json.loads(self.state.create_post_request())["scenes"]["ingame"], []
        )

    def test_post_request_includes_configured_scales_and_defaults_missing_scales(self):
        for element in self.state.game_info.element_positions:
            element.pop("Scale", None)
            if element["Name"] == "Score Ingame":
                element["Scale"] = 0.5
            elif element["Name"] == "Sponsorships Badge":
                element["Scale"] = 1.5
        self.state.enable_component("idle", "Starting Soon")
        self.state.enable_component("ingame", "Score Ingame")
        for scene in ("idle", "pregame", "ingame"):
            self.state.enable_component(scene, "Sponsorships Badge")
        scenes = json.loads(self.state.create_post_request())["scenes"]
        for components in scenes.values():
            for component in components:
                expected = {"Score Ingame": 0.5, "Sponsorships Badge": 1.5}.get(
                    component["name"], 1
                )
                self.assertEqual(component["scale"], expected)
        self.state.load_game("Overwatch")
        self.state.enable_component("ingame", "Score Ingame")
        self.assertEqual(
            json.loads(self.state.create_post_request())["scenes"]["ingame"][0][
                "scale"
            ],
            1,
        )

    def test_post_request_uses_live_rosters_scores_and_side_order(self):
        for team in (1, 2):
            self.state.match_info.update_team_name(team, f"Team {team}")
            self.state.match_info.update_team_score(team, team * 3)
            self.state.match_info.add_player(team, f"Player {team}")
        self.state.enable_component("pregame", "Team Roster")
        self.state.enable_component("ingame", "Score Ingame")
        original_json = self.state.create_post_request()
        scenes = json.loads(original_json)["scenes"]
        self.assertEqual(
            scenes["pregame"][0]["data"]["teams"],
            [
                {"name": "Team 1", "players": ["Player 1"]},
                {"name": "Team 2", "players": ["Player 2"]},
            ],
        )
        self.assertEqual(
            scenes["ingame"][0]["data"]["teams"],
            [
                {"name": "Team 1", "score": 3},
                {"name": "Team 2", "score": 6},
            ],
        )
        self.state.match_info.swap_sides()
        swapped = json.loads(self.state.create_post_request())["scenes"]
        for scene in ("pregame", "ingame"):
            self.assertEqual(
                swapped[scene][0]["data"]["teams"],
                scenes[scene][0]["data"]["teams"][::-1],
            )
        self.assertEqual(json.loads(original_json)["scenes"], scenes)

    def test_post_request_contains_selected_maps_and_heroes_not_catalogs(self):
        self.state.load_game("Overwatch")
        self.state.update_ban("map", "King's Row")
        self.state.update_ban("hero", "L\u00facio")
        self.state.enable_component("pregame", "Map Picks")
        self.state.enable_component("ingame", "Character Bans Ingame")
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual(
            scenes["pregame"][0]["data"],
            {
                "game": "Overwatch",
                "scene": "pregame",
                "map_picks": ["King's Row"],
            },
        )
        self.assertEqual(scenes["ingame"][0]["data"]["hero_bans"], ["L\u00facio"])
        self.state.enable_component("pregame", "Character Bans Pregame")
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual(scenes["pregame"][0]["data"]["hero_bans"], ["L\u00facio"])
        self.state.update_ban("hero", "L\u00facio", remove=True)
        self.assertEqual(
            json.loads(self.state.create_post_request())["scenes"]["ingame"][0]["data"][
                "hero_bans"
            ],
            [],
        )
        self.state.load_game("Miscellaneous")
        self.assertEqual(
            json.loads(self.state.create_post_request())["scenes"],
            {"idle": [], "pregame": [], "ingame": []},
        )


class PrintInfoTests(unittest.TestCase):
    def test_print_info_and_builtin_print_show_readable_state(self):
        state = StateManager("Valorant")
        state.match_info.update_team_name(1, "Gryphons")
        state.match_info.add_player(1, "Player One")
        for instance, expected_text in (
            (state.game_info, ("Valorant", "maps", "chars", "Team Roster")),
            (state.match_info, ("Gryphons", "Player One", "Score")),
            (
                state,
                ("Valorant", "Gryphons", "Player One", "idle", "pregame", "ingame"),
            ),
        ):
            with self.subTest(class_name=type(instance).__name__):
                output = io.StringIO()
                with redirect_stdout(output):
                    instance.print_info()
                    print(instance)
                self.assertEqual(output.getvalue(), (str(instance) + "\n") * 2)
                for value in expected_text:
                    self.assertIn(value, output.getvalue())


def print_demo():
    """Show a populated match and the result of switching overlapping components."""
    state = StateManager("Valorant")
    print("\nGame configuration:")
    state.game_info.print_info()

    match = state.match_info
    match.update_team_name(1, "Gryphons")
    match.update_team_name(2, "Rivals")
    match.update_team_score(1, 3)
    match.update_team_score(2, 1)
    match.add_player(1, "Player One")
    match.add_player(2, "Player Two")
    print("\nMatch before swapping sides:")
    match.print_info()
    match.swap_sides()
    print("\nMatch after swapping sides:")
    match.print_info()

    state.enable_component("pregame", "Team Roster")
    state.enable_component("pregame", "Sponsorships Badge")
    print("\nState with roster and sponsorship badge enabled:")
    state.print_info()
    state.enable_component("pregame", "Score Pregame")
    print("\nState after Score Pregame replaces Team Roster at Center:")
    state.print_info()
    state.disable_component("pregame", "Score Pregame")
    print("\nState after disabling Score Pregame:")
    state.print_info()


if __name__ == "__main__":
    show_demo = "--demo" in sys.argv
    if show_demo:
        sys.argv.remove("--demo")
    result = unittest.main(verbosity=2, exit=False).result
    if show_demo and result.wasSuccessful():
        print_demo()
    sys.exit(0 if result.wasSuccessful() else 1)

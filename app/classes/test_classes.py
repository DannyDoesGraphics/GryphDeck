"""Run with `python app/classes/test_classes.py`; add --demo to print examples."""

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest

if __package__:
    from .GameInfo import GameInfo
    from .MatchInfo import MatchInfo
    from . import SideDetection
    from .StateManager import StateManager
else:
    from GameInfo import GameInfo
    from MatchInfo import MatchInfo
    import SideDetection
    from StateManager import StateManager


CONFIG_DIR = Path(__file__).resolve().parent.parent / "json"


class GameInfoTests(unittest.TestCase):
    def test_load_every_game_configuration(self):
        paths = list(CONFIG_DIR.glob("*.json"))
        self.assertTrue(paths, "No game configurations found")
        for path in paths:
            with self.subTest(game=path.stem):
                data = json.loads(path.read_text(encoding="utf-8"))
                game = GameInfo(path.stem)
                for field in ("name", "element_positions", "enabled_components", "maps", "chars"):
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
            self.assertEqual(self.match.team_info(team), {
                "Name": "", "Score": 0, "Players": [],
            })

    def test_update_names_and_scores(self):
        for team, name, score in ((1, "Gryphons", 3), (2, "Rivals", 1)):
            self.assertTrue(self.match.update_team_name(team, name))
            self.assertTrue(self.match.update_team_score(team, score))
            self.assertEqual(self.match.team_info(team), {
                "Name": name, "Score": score, "Players": [],
            })

    def test_add_and_remove_players(self):
        self.assertTrue(self.match.add_player(1, "Player One"))
        self.assertTrue(self.match.add_player(1, "Player Two"))
        self.assertTrue(self.match.add_player(2, "Opponent"))
        self.assertTrue(self.match.remove_player(1, "Player One"))
        self.assertFalse(self.match.remove_player(1, "Missing Player"))
        self.assertEqual(self.match.team_info(1)["Players"], ["Player Two"])
        self.assertEqual(self.match.team_info(2)["Players"], ["Opponent"])

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


class StateManagerTests(unittest.TestCase):
    def setUp(self):
        self.state = StateManager("Valorant")

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
                        getattr(state, f"current_{scene}_components"), expected,
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
            name for name, position, active in self.state.current_pregame_components
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
        self.assertEqual(json.loads(self.state.create_post_request()), {
            "game": "Valorant", "scenes": {"idle": [], "pregame": [], "ingame": []},
        })
        self.state.enable_component("idle", "Starting Soon")
        self.state.enable_component("idle", "Sponsorships Badge")
        self.state.enable_component("pregame", "Team Roster")
        self.state.enable_component("pregame", "Score Pregame")
        self.state.enable_component("ingame", "Score Ingame")
        self.state.current_scene = "ingame"
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual({c["name"] for c in scenes["idle"]}, {"Starting Soon", "Sponsorships Badge"})
        self.assertEqual([c["name"] for c in scenes["pregame"]], ["Score Pregame"])
        self.assertEqual(scenes["ingame"][0]["location"], "BottomCenter")
        for component in scenes["idle"]:
            self.assertEqual(component["data"], {"game": "Valorant", "scene": "idle"})
        self.state.disable_component("ingame", "Score Ingame")
        self.assertEqual(json.loads(self.state.create_post_request())["scenes"]["ingame"], [])

    def test_post_request_uses_live_rosters_scores_and_side_order(self):
        for team in (1, 2):
            self.state.match_info.update_team_name(team, f"Team {team}")
            self.state.match_info.update_team_score(team, team * 3)
            self.state.match_info.add_player(team, f"Player {team}")
        self.state.enable_component("pregame", "Team Roster")
        self.state.enable_component("ingame", "Score Ingame")
        original_json = self.state.create_post_request()
        scenes = json.loads(original_json)["scenes"]
        self.assertEqual(scenes["pregame"][0]["data"]["teams"], [
            {"name": "Team 1", "players": ["Player 1"]},
            {"name": "Team 2", "players": ["Player 2"]},
        ])
        self.assertEqual(scenes["ingame"][0]["data"]["teams"], [
            {"name": "Team 1", "score": 3}, {"name": "Team 2", "score": 6},
        ])
        self.state.match_info.swap_sides()
        swapped = json.loads(self.state.create_post_request())["scenes"]
        for scene in ("pregame", "ingame"):
            self.assertEqual(swapped[scene][0]["data"]["teams"], scenes[scene][0]["data"]["teams"][::-1])
        self.assertEqual(json.loads(original_json)["scenes"], scenes)

    def test_post_request_contains_selected_maps_and_heroes_not_catalogs(self):
        self.state.load_game("Overwatch")
        self.state.update_ban("map", "King's Row")
        self.state.update_ban("hero", "L\u00facio")
        self.state.enable_component("pregame", "Map Picks")
        self.state.enable_component("ingame", "Character Bans Ingame")
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual(scenes["pregame"][0]["data"], {
            "game": "Overwatch", "scene": "pregame", "map_picks": ["King's Row"],
        })
        self.assertEqual(scenes["ingame"][0]["data"]["hero_bans"], ["L\u00facio"])
        self.state.enable_component("pregame", "Character Bans Pregame")
        scenes = json.loads(self.state.create_post_request())["scenes"]
        self.assertEqual(scenes["pregame"][0]["data"]["hero_bans"], ["L\u00facio"])
        self.state.update_ban("hero", "L\u00facio", remove=True)
        self.assertEqual(json.loads(self.state.create_post_request())["scenes"]["ingame"][0]["data"]["hero_bans"], [])
        self.state.load_game("Miscellaneous")
        self.assertEqual(json.loads(self.state.create_post_request())["scenes"], {"idle": [], "pregame": [], "ingame": []})

    def test_draft_slots_are_per_team_and_unique(self):
        self.assertIsNone(self.state.draft)
        with self.assertRaises(ValueError):
            self.state.set_draft_slot(1, "picks", 0, "Jett")
        self.state.load_game("Deadlock")
        self.assertEqual(self.state.draft["teams"][0], {"picks": [None] * 6, "bans": [None] * 2})
        self.state.set_draft_slot(1, "picks", 0, " rat king ")
        self.state.set_draft_slot(2, "bans", 1, "Mo & Krill")
        self.state.set_draft_slot(1, "picks", 0, "Rat King")  # same slot again is fine
        for team, kind, slot, hero in ((2, "picks", 0, "Rat King"), (1, "bans", 0, "mo & krill"),
                                       (1, "picks", 6, "Haze"), (3, "picks", 0, "Haze"),
                                       (1, "draws", 0, "Haze"), (1, "picks", 1, "Jett"), (1, "picks", "0", "Haze")):
            with self.subTest(team=team, kind=kind, slot=slot, hero=hero), self.assertRaises(ValueError):
                self.state.set_draft_slot(team, kind, slot, hero)
        self.state.set_draft_slot(1, "picks", 0, None)
        self.state.set_draft_slot(2, "picks", 0, "Rat King")
        self.assertEqual(self.state.draft["teams"][0]["picks"][0], None)
        self.assertEqual(self.state.draft["teams"][1], {"picks": ["Rat King"] + [None] * 5, "bans": [None, "Mo & Krill"]})
        # Moving takes the hero out of its old slot, across teams and kinds.
        self.state.set_draft_slot(1, "bans", 0, "Rat King", move=True)
        self.state.set_draft_slot(1, "picks", 3, "mo & krill", move=True)
        self.assertEqual(self.state.draft["teams"][1], {"picks": [None] * 6, "bans": [None, None]})
        self.assertEqual(self.state.draft["teams"][0]["bans"][0], "Rat King")
        self.assertEqual(self.state.draft["teams"][0]["picks"][3], "Mo & Krill")

    def test_draft_post_request_and_side_swap(self):
        self.state.load_game("Deadlock")
        for team in (1, 2):
            self.state.match_info.update_team_name(team, f"Team {team}")
            self.state.match_info.add_player(team, f"Player {team}")
        self.state.set_draft_slot(1, "picks", 0, "Haze")
        self.state.set_draft_slot(2, "bans", 0, "Violet")
        self.state.set_draft_details(label="Grand Final", first_pick=1)
        with self.assertRaises(ValueError):
            self.state.set_draft_details(first_pick=3, label="Not applied")
        self.assertEqual(self.state.draft["label"], "Grand Final")
        self.state.enable_component("pregame", "Hero Draft")
        data = json.loads(self.state.create_post_request())["scenes"]["pregame"][0]["data"]
        self.assertEqual((data["label"], data["first_pick"]), ("Grand Final", 1))
        self.assertEqual(data["teams"][0], {"name": "Team 1", "score": 0, "players": ["Player 1"],
                                            "picks": ["Haze"] + [None] * 5,
                                            "pick_players": ["Player 1"] + [None] * 5, "bans": [None, None]})
        self.state.enable_component("ingame", "Deadlock Top Bar")
        top_bar = json.loads(self.state.create_post_request())["scenes"]["ingame"][0]["data"]
        self.assertEqual({**top_bar, "scene": "pregame"}, data)
        self.state.swap_sides()
        swapped = json.loads(self.state.create_post_request())["scenes"]["pregame"][0]["data"]
        self.assertEqual(swapped["teams"], data["teams"][::-1])
        self.assertEqual(swapped["first_pick"], 2)
        self.state.load_game("Deadlock")
        self.assertEqual(self.state.draft["teams"][0]["picks"], [None] * 6)
        self.assertEqual(self.state.match_info.team_info(1)["Name"], "Team 2")

    def test_removing_a_player_keeps_later_players_picks(self):
        self.state.load_game("Deadlock")
        for name, hero in (("Ann", "Haze"), ("Bo", "Ivy"), ("Cy", "Kelvin")):
            self.state.match_info.add_player(1, name)
            self.state.set_draft_slot(1, "picks", len(self.state.match_info.players[0]) - 1, hero)
        self.assertTrue(self.state.remove_player(1, "Bo"))
        self.assertEqual(self.state.match_info.players[0], ["Ann", "Cy"])
        self.assertEqual(self.state.draft["teams"][0]["picks"], ["Haze", "Kelvin"] + [None] * 4)
        self.assertFalse(self.state.remove_player(1, "Bo"))


def deadlock_teams(side1, side2, heroes1=(), heroes2=()):
    """A side reporter "teams" event: player names (and heroes, "#" while undecided) per side."""
    def players(names, heroes):
        return [{"name": name, "hero": heroes[i] if i < len(heroes) else "#"} for i, name in enumerate(names)]
    return {"type": "teams", "teams": [{"side": 1, "players": players(side1, heroes1)},
                                       {"side": 2, "players": players(side2, heroes2)}]}


class SideDetectionTests(unittest.TestCase):
    def test_normalize_ignores_case_accents_punctuation_and_the(self):
        self.assertEqual(SideDetection.normalize("The Doorman"), "doorman")
        self.assertEqual(SideDetection.normalize("  Zo\u00eb_X!  "), "zoex")
        self.assertEqual(SideDetection.normalize("#"), "")

    def test_player_names_and_drafted_heroes_each_decide(self):
        sides = SideDetection.parse_teams(deadlock_teams(["[GG] Danny", "Ash"], ["Rook"], ["Haze"], ["Abrams"])["teams"])
        self.assertEqual(SideDetection.detect(sides, [["danny"], ["rook"]], [[], []]), ("keep", "player names", False))
        self.assertEqual(SideDetection.detect(sides, [["Rook"], ["Danny"]], [[], []]), ("swap", "player names", False))
        # "Ash" is too short to match inside another name, so only exact names count.
        self.assertIsNone(SideDetection.detect(sides, [["Ashley"], []], [[], []])[0])
        # Roster player N drafted pick N: hero picks find the sides without any name matching.
        self.assertEqual(SideDetection.detect(sides, [["Nobody"], []], [["Abrams", None], ["Haze"]]),
                         ("swap", "hero picks", False))
        self.assertEqual(SideDetection.detect(sides, [["Danny"], ["Rook"]], [["Haze"], ["Abrams"]]),
                         ("keep", "player names and hero picks", False))

    def test_mirrored_heroes_in_show_matches_say_nothing(self):
        sides = SideDetection.parse_teams(deadlock_teams(["Bot A", "Bot B"], ["Bot C", "Bot D"],
                                                         ["Haze", "Abrams"], ["Haze", "Abrams"])["teams"])
        decision, reason, stuck = SideDetection.detect(sides, [["Danny"], ["Rook"]], [["Haze", "Abrams"], ["Abrams", "Haze"]])
        self.assertEqual((decision, stuck), (None, True))
        self.assertEqual(reason, "no names match, picks are on both sides")
        # One hero only one side plays is enough.
        sides = SideDetection.parse_teams(deadlock_teams(["Bot A", "Bot B"], ["Bot C", "Bot D"],
                                                         ["Haze", "Abrams"], ["Haze", "Wraith"])["teams"])
        self.assertEqual(SideDetection.detect(sides, [["Danny"], ["Rook"]], [["Haze", "Wraith"], ["Haze", "Abrams"]])[0], "swap")

    def test_names_and_heroes_pointing_opposite_ways_is_not_guessed(self):
        sides = SideDetection.parse_teams(deadlock_teams(["Danny"], ["Rook"], ["Haze"], ["Abrams"])["teams"])
        decision, reason, stuck = SideDetection.detect(sides, [["Danny"], ["Rook"]], [["Abrams"], ["Haze"]])
        self.assertEqual((decision, stuck), (None, True))
        self.assertEqual(reason, "names and picks disagree")

    def test_waits_while_the_game_can_still_show_more(self):
        sides = SideDetection.parse_teams([{"side": 0, "players": []}])
        self.assertEqual(SideDetection.detect(sides, [["a"], ["b"]], [[], []])[2], False)
        sides = SideDetection.parse_teams(deadlock_teams([], [])["teams"])
        self.assertIsNone(SideDetection.detect(sides, [["a"], ["b"]], [[], []])[0])
        # Heroes still being chosen ("#"): no evidence yet, but not stuck.
        sides = SideDetection.parse_teams(deadlock_teams(["Bot A"], ["Bot B"])["teams"])
        self.assertEqual(SideDetection.detect(sides, [["Danny"], ["Rook"]], [["Haze"], ["Abrams"]]),
                         (None, "no names match, no picks in game", False))

    def test_rejects_malformed_reports(self):
        for teams in (None, {}, [{"side": "1"}], [{"side": 1, "players": "x"}],
                      [{"side": 1, "players": [{"name": 3}]}], [{"side": 1, "players": [{"name": "x" * 129}]}],
                      [{"side": 1, "players": [{}] * 13}], [{"side": 1}] * 5):
            with self.subTest(teams=teams), self.assertRaises(ValueError):
                SideDetection.parse_teams(teams)


class DeadlockSidesTests(unittest.TestCase):
    def setUp(self):
        self.state = StateManager("Deadlock")
        for team, names in ((1, ["Danny", "Kestrel"]), (2, ["Rook", "Vale"])):
            self.state.match_info.update_team_name(team, f"Team {team}")
            for name in names:
                self.state.match_info.add_player(team, name)

    def test_unknown_until_detected_then_swaps_once(self):
        self.assertFalse(self.state.sides["known"])
        self.assertFalse(self.state.apply_deadlock_event({"type": "state", "state": "HeroSelection", "id": 3}))
        self.assertFalse(self.state.apply_deadlock_event(deadlock_teams([], [])))
        self.assertIn("waiting", self.state.sides["status"])
        self.assertTrue(self.state.apply_deadlock_event(deadlock_teams(["Rook", "Vale"], ["Danny", "Kestrel"])))
        self.assertTrue(self.state.sides["known"])
        self.assertEqual(self.state.sides["status"], "Detected from player names; teams swapped.")
        self.assertEqual(self.state.match_info.team_info(1)["Name"], "Team 2")
        # Further reports in the same match change nothing.
        self.assertFalse(self.state.apply_deadlock_event(deadlock_teams(["Danny"], ["Rook"])))
        self.assertEqual(self.state.match_info.team_info(1)["Name"], "Team 2")
        self.state.enable_component("pregame", "Hero Draft")
        self.state.enable_component("ingame", "Deadlock Top Bar")
        data = json.loads(self.state.create_post_request())
        flags = [component["data"]["sides_known"] for scene in data["scenes"].values()
                 for component in scene if "teams" in component["data"]]
        self.assertEqual(flags, [True, True])

    def test_new_match_resets_sides_but_in_game_phases_do_not(self):
        self.state.apply_deadlock_event(deadlock_teams(["Danny"], ["Rook"]))
        self.assertTrue(self.state.sides["known"])
        self.assertFalse(self.state.apply_deadlock_event({"type": "state", "state": "GameInProgress", "id": 7}))
        self.assertTrue(self.state.apply_deadlock_event({"type": "state", "state": "WaitingForPlayersToJoin", "id": 2}))
        self.assertFalse(self.state.sides["known"])
        self.state.apply_deadlock_event(deadlock_teams(["Danny"], ["Rook"]))
        self.assertFalse(self.state.apply_deadlock_event({"type": "state", "state": "HeroSelection", "id": 3}))
        self.assertTrue(self.state.sides["known"])

    def test_operator_override_and_manual_mode(self):
        self.state.set_sides(auto=False)
        self.state.apply_deadlock_event(deadlock_teams(["Rook"], ["Danny"]))
        self.state.apply_deadlock_event({"type": "state", "state": "WaitingForPlayersToJoin", "id": 2})
        self.assertFalse(self.state.sides["known"])
        self.assertEqual(self.state.match_info.team_info(1)["Name"], "Team 1")
        self.state.set_sides(known=True)
        self.assertEqual(self.state.sides["status"], "Set by hand.")
        for changes in ({"known": "yes"}, {"auto": 1}, {"left": 3}, {"left": True}, {"left": "2"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.state.set_sides(**changes)
        for event in (None, {"type": "nope"}, {"type": "state", "state": "x", "id": "3"}):
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.state.apply_deadlock_event(event)

    def test_draft_fix_settles_the_last_report_at_once(self):
        report = deadlock_teams(["Bot A"], ["Bot B"], ["Haze"], ["Wraith"])
        self.state.apply_deadlock_event(report)
        self.assertTrue(self.state.sides["attention"])
        self.state.set_draft_slot(1, "picks", 0, "Wraith")
        self.assertTrue(self.state.redetect_sides())
        self.assertEqual((self.state.sides["known"], self.state.sides["attention"]), (True, False))
        self.assertEqual(self.state.sides["status"], "Detected from hero picks; teams swapped.")
        self.assertEqual(self.state.match_info.team_info(1)["Players"], ["Rook", "Vale"])
        # A new match forgets the report.
        self.state.apply_deadlock_event({"type": "state", "state": "WaitingForPlayersToJoin", "id": 2})
        self.assertFalse(self.state.redetect_sides())
        self.assertFalse(self.state.sides["known"])

    def test_undecidable_match_asks_the_operator_and_keeps_rosters(self):
        # Show match: nobody's in-game name is on the rosters and both sides play the same heroes.
        for team, picks in ((0, ["Haze", "Abrams"]), (1, ["Abrams", "Haze"])):
            self.state.draft["teams"][team]["picks"][:2] = picks
        report = deadlock_teams(["Bot A", "Bot B"], ["Bot C", "Bot D"], ["#", "#"], ["#", "#"])
        self.state.apply_deadlock_event(report)
        self.assertFalse(self.state.sides["attention"])
        self.assertTrue(self.state.sides["status"].startswith("Detecting:"))
        report = deadlock_teams(["Bot A", "Bot B"], ["Bot C", "Bot D"], ["Haze", "Abrams"], ["Abrams", "Haze"])
        self.assertFalse(self.state.apply_deadlock_event(report))
        self.assertFalse(self.state.sides["known"])
        self.assertTrue(self.state.sides["attention"])
        self.assertEqual(self.state.sides["status"],
                         "Can't tell sides: no names match, picks are on both sides.")
        self.assertEqual(self.state.match_info.team_info(1)["Players"], ["Danny", "Kestrel"])
        # The operator says the left team is the Archmother: the teams swap and colour.
        self.state.set_sides(left=2)
        self.assertEqual((self.state.sides["known"], self.state.sides["attention"]), (True, False))
        self.assertEqual(self.state.match_info.team_info(1)["Players"], ["Rook", "Vale"])
        self.assertEqual(self.state.draft["teams"][0]["picks"][:2], ["Abrams", "Haze"])
        self.state.set_sides(known=False)
        self.state.set_sides(left=1)
        self.assertEqual(self.state.match_info.team_info(1)["Players"], ["Rook", "Vale"])
        self.assertTrue(self.state.sides["known"])


class PlayerNamesTests(unittest.TestCase):
    def test_hero_picks_only_hides_player_names(self):
        state = StateManager("Deadlock")
        state.match_info.add_player(1, "Alpha")
        state.set_draft_slot(1, "picks", 0, "Haze")
        state.enable_component("pregame", "Hero Draft")

        def pick_players():
            scene = json.loads(state.create_post_request())["scenes"]["pregame"][0]
            return scene["data"]["teams"][0]["pick_players"]

        self.assertEqual(pick_players(), ["Alpha"] + [None] * 5)
        state.set_draft_details(player_names=False)
        self.assertEqual(pick_players(), [None] * 6)
        with self.assertRaises(ValueError):
            state.set_draft_details(player_names="no")


class PrintInfoTests(unittest.TestCase):
    def test_print_info_and_builtin_print_show_readable_state(self):
        state = StateManager("Valorant")
        state.match_info.update_team_name(1, "Gryphons")
        state.match_info.add_player(1, "Player One")
        for instance, expected_text in (
            (state.game_info, ("Valorant", "maps", "chars", "Team Roster")),
            (state.match_info, ("Gryphons", "Player One", "Score")),
            (state, ("Valorant", "Gryphons", "Player One", "idle", "pregame", "ingame")),
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

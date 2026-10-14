"""Integration tests: python -m unittest app.test_routes app.classes.test_classes."""

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from app import create_app
from app.classes.TeamSource import SOURCES
from app.classes.TeamSource import logger as source_log
from app.classes.test_classes import MANUAL, FlakySource, LockedSource, ValorantSource


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.manager = self.app.extensions["state_manager"]
        print_patch = patch("app.routes.print")
        self.print_output = print_patch.start()
        self.addCleanup(print_patch.stop)
        post_patch = patch("app.routes.urlopen")
        self.post_overlay = post_patch.start()
        self.addCleanup(post_patch.stop)

    def action(self, action, **data):
        response = self.client.post("/api/control", json={"action": action, **data})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_dashboard_and_default_game(self):
        for path in ("/", "/UI", "/static/css/control.css", "/static/js/control.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()
        state = self.client.get("/api/state").get_json()
        self.assertEqual(state["game"], "Valorant")
        self.assertEqual(state["scene"], "idle")
        self.assertIn("Overwatch", state["games"])

    def test_toggle_conflicts_and_scene_independence(self):
        self.action("select_scene", scene="pregame")
        self.assertEqual(self.manager.current_scene, "pregame")
        for name in ("Sponsorships Badge", "Team Roster", "Score Pregame"):
            state = self.action("toggle_component", scene="pregame", component=name)
        self.assertEqual(
            {c["name"] for c in state["components"]["pregame"] if c["enabled"]},
            {"Sponsorships Badge", "Score Pregame"},
        )
        self.assertFalse(any(c["enabled"] for c in state["components"]["idle"]))
        state = self.action(
            "toggle_component", scene="pregame", component="Score Pregame"
        )
        self.assertEqual(
            {c["name"] for c in state["components"]["pregame"] if c["enabled"]},
            {"Sponsorships Badge"},
        )
        self.action("select_scene", scene="ingame")
        state = self.action(
            "toggle_component", scene="ingame", component="Score Ingame"
        )
        self.assertTrue(
            next(
                c for c in state["components"]["ingame"] if c["name"] == "Score Ingame"
            )["enabled"]
        )

    def test_match_edit_and_swap_uses_existing_method(self):
        for team, name, score in ((1, "Gryphons", 3), (2, "Rivals", 1)):
            self.action("update_team", team=team, name=name, score=score)
            self.action("add_player", team=team, player=f"Player {team}")
        self.action("add_player", team=1, player="Reserve")
        self.action("remove_player", team=1, player="Reserve")
        before = self.client.get("/api/state").get_json()["teams"]
        with patch.object(
            self.manager.match_info,
            "swap_sides",
            wraps=self.manager.match_info.swap_sides,
        ) as swap:
            after = self.action("swap_sides")
            swap.assert_called_once_with()
        self.assertEqual(after["teams"], before[::-1])
        self.assertEqual(self.manager.match_info.team_info(1), before[1])
        scene = self.client.get("/api/scenes/ingame").get_json()
        self.assertEqual(scene["teams"], ["Rivals", "Gryphons"])
        self.assertEqual(scene["score"], {"home": 1, "away": 3})
        self.assertEqual(scene["players"], [["Player 2"], ["Player 1"]])

    def test_game_load_keeps_match_and_resets_components(self):
        self.action("update_team", team=1, name="Gryphons", score=5)
        self.action("add_player", team=1, player="Captain")
        match = self.manager.match_info
        games = self.client.get("/api/state").get_json()["games"]
        for game in games:
            with self.subTest(game=game):
                self.action("toggle_component", scene="idle", component="Starting Soon")
                state = self.action("load_game", game=game)
                self.assertEqual(state["game_key"], game)
                self.assertIn(state["game_key"], state["games"])
                self.assertIs(self.manager.match_info, match)
                self.assertEqual(
                    state["teams"][0],
                    {
                        "Name": "Gryphons",
                        "Score": 5,
                        "Players": ["Captain"],
                        "Source": MANUAL,
                        "Extra": {},
                    },
                )
                self.assertFalse(
                    any(
                        c["enabled"]
                        for components in state["components"].values()
                        for c in components
                    )
                )

    def test_team_fields_save_independently(self):
        state = self.action("update_team", team=1, score=3)
        self.assertEqual(
            state["teams"][0],
            {"Name": "", "Score": 3, "Players": [], "Source": MANUAL, "Extra": {}},
        )
        state = self.action("update_team", team=1, name="Gryphons")
        self.assertEqual(
            state["teams"][0],
            {
                "Name": "Gryphons",
                "Score": 3,
                "Players": [],
                "Source": MANUAL,
                "Extra": {},
            },
        )
        for fields in (
            {},
            {"name": " "},
            {"score": -1},
            {"name": "Changed", "score": 1000},
        ):
            response = self.client.post(
                "/api/control", json={"action": "update_team", "team": 1, **fields}
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.get("/api/state").get_json(), state)

    def test_ban_options_follow_game_components_and_catalogs(self):
        for game, maps, heroes in (
            ("Valorant", True, False),
            ("CSGO", True, False),
            ("Overwatch", True, True),
            ("MarvelRivals", True, True),
            ("Miscellaneous", False, False),
        ):
            with self.subTest(game=game):
                state = self.action("load_game", game=game)
                self.assertEqual(
                    state["ban_options"]["map"],
                    {"supported": maps, "choices": self.manager.game_info.maps},
                )
                self.assertEqual(
                    state["ban_options"]["hero"],
                    {"supported": heroes, "choices": self.manager.game_info.chars},
                )
        self.manager.game_info.enabled_components = [
            "Map Bans Pregame",
            "Hero Bans Ingame",
        ]
        options = self.client.get("/api/state").get_json()["ban_options"]
        self.assertTrue(options["map"]["supported"])
        self.assertTrue(options["hero"]["supported"])

    def test_bans_are_shared_and_exposed_to_scenes(self):
        self.action("load_game", game="Overwatch")
        self.action("add_ban", kind="map", name="  king's row  ")
        state = self.action("add_ban", kind="hero", name="ana")
        expected = {"map": ["King's Row"], "hero": ["Ana"]}
        self.assertEqual(state["bans"], expected)
        self.assertEqual(
            self.app.test_client().get("/api/state").get_json()["bans"], expected
        )
        for scene in ("pregame", "ingame"):
            self.assertEqual(
                self.client.get(f"/api/scenes/{scene}").get_json()["bans"], expected
            )
        self.assertEqual(self.action("swap_sides")["bans"], expected)
        self.assertEqual(
            self.action(
                "toggle_component", scene="pregame", component="Character Bans Pregame"
            )["bans"],
            expected,
        )
        state = self.action("remove_ban", kind="hero", name="ANA")
        self.assertEqual(state["bans"], {"map": ["King's Row"], "hero": []})
        state = self.action("remove_ban", kind="map", name="King's Row")
        self.assertEqual(state["bans"], {"map": [], "hero": []})

    def test_invalid_bans_do_not_mutate_state(self):
        self.action("add_ban", kind="map", name="Ascent")
        before = self.client.get("/api/state").get_json()
        cases = [
            ("add_ban", "map", "ASCENT"),
            ("add_ban", "map", "Unknown"),
            ("add_ban", "hero", "Astra"),
            ("add_ban", "map", " "),
            ("add_ban", [], "Ascent"),
            ("add_ban", "unknown", "Ascent"),
            ("add_ban", "map", None),
            ("remove_ban", "map", "Abyss"),
        ]
        for action, kind, name in cases:
            with self.subTest(action=action, kind=kind, name=name):
                response = self.client.post(
                    "/api/control", json={"action": action, "kind": kind, "name": name}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.client.get("/api/state").get_json(), before)

    def test_loading_game_resets_bans_but_failed_load_retains_them(self):
        self.action("load_game", game="Overwatch")
        self.action("add_ban", kind="map", name="Ilios")
        self.action("add_ban", kind="hero", name="Ana")
        before = self.client.get("/api/state").get_json()
        with (
            patch("app.classes.StateManager.GameInfo", side_effect=KeyError("maps")),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            response = self.client.post(
                "/api/control", json={"action": "load_game", "game": "Valorant"}
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/state").get_json(), before)
        self.assertEqual(
            self.action("load_game", game="Overwatch")["bans"], {"map": [], "hero": []}
        )
        self.action("add_ban", kind="hero", name="Ana")
        self.assertEqual(
            self.action("load_game", game="Valorant")["bans"], {"map": [], "hero": []}
        )

    def test_invalid_requests_do_not_mutate_state(self):
        before = self.client.get("/api/state").get_json()
        payloads = [
            None,
            [],
            {},
            {"action": "unknown"},
            {"action": "load_game", "game": "../classes/MatchInfo"},
            {"action": "select_scene", "scene": "unknown"},
            {"action": "toggle_component", "scene": "idle", "component": "Team Roster"},
            {"action": "add_player", "team": 1, "player": "   "},
            {"action": "add_player", "team": True, "player": "Player"},
            {"action": "remove_player", "team": 1, "player": "Missing"},
            {"action": "set_team_source", "team": 1, "source": "unknown"},
            {"action": "set_team_source", "team": 1, "source": ["manual"]},
            {"action": "set_team_source", "team": 1},
            {"action": "set_team_source", "team": 3, "source": "manual"},
        ]
        for score in (-1, 1000, 1.5, "3", True, None):
            payloads.append(
                {
                    "action": "update_team",
                    "team": 1,
                    "name": "Do not save",
                    "score": score,
                }
            )
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/api/control", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.client.get("/api/state").get_json(), before)

    def test_team_sources(self):
        state = self.client.get("/api/state").get_json()
        self.assertEqual(
            state["sources"],
            [
                {
                    "kind": "manual",
                    "label": "Manual",
                    "description": "Name and roster are entered here.",
                },
            ],
        )
        self.action("update_team", team=1, name="Gryphons", score=2)
        self.action("add_player", team=1, player="Captain")
        before = self.client.get("/api/state").get_json()
        self.assertEqual(
            self.action("set_team_source", team=1, source="manual"), before
        )

    def test_sources_follow_the_loaded_game(self):
        with patch.dict(SOURCES, {"valorant": ValorantSource}):
            state = self.action("set_team_source", team=2, source="valorant")
            self.assertEqual(
                [option["kind"] for option in state["sources"]], ["manual", "valorant"]
            )
            state = self.action("load_game", game="Overwatch")
        self.assertEqual([option["kind"] for option in state["sources"]], ["manual"])
        self.assertEqual(
            state["teams"][1],
            {
                "Name": "Valorant Team",
                "Score": 0,
                "Players": ["Agent"],
                "Source": MANUAL,
                "Extra": {},
            },
        )

    def test_failing_source_keeps_the_deck_up(self):
        source = self.manager.match_info.sources[1] = FlakySource()
        self.client.get("/api/state")
        source.failure = RuntimeError("feed down")
        with self.assertLogs(source_log, "ERROR"):
            response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        team = response.get_json()["teams"][1]
        self.assertEqual(
            (team["Name"], team["Players"], team["Source"]["Error"]),
            ("Fetched", ["Remote"], "RuntimeError: feed down"),
        )
        self.assertEqual(
            self.action("update_team", team=1, name="Still works")["teams"][0]["Name"],
            "Still works",
        )

    def test_locked_source_rejects_name_and_roster_but_keeps_score(self):
        self.manager.match_info.sources[1] = LockedSource()
        before = self.client.get("/api/state").get_json()
        self.assertEqual(
            before["teams"][1]["Source"],
            {"Kind": "locked", "Label": "Locked", "Error": None},
        )
        for payload in (
            {"action": "update_team", "team": 2, "name": "Changed"},
            {"action": "update_team", "team": 2, "name": "Changed", "score": 1},
            {"action": "add_player", "team": 2, "player": "Extra"},
            {"action": "remove_player", "team": 2, "player": "Remote"},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/control", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("source", response.get_json()["error"])
                self.assertEqual(self.client.get("/api/state").get_json(), before)
        self.assertEqual(
            self.action("update_team", team=2, score=4)["teams"][1]["Score"], 4
        )
        state = self.action("set_team_source", team=2, source="manual")
        self.assertEqual(
            state["teams"][1],
            {
                "Name": "Fetched",
                "Score": 4,
                "Players": ["Remote"],
                "Source": MANUAL,
                "Extra": {"wins": 4},
            },
        )
        self.action("add_player", team=2, player="Extra")

    def test_failed_load_retains_current_game(self):
        before = self.client.get("/api/state").get_json()
        with (
            patch(
                "app.classes.StateManager.GameInfo",
                side_effect=KeyError("enabled_components"),
            ),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            response = self.client.post(
                "/api/control", json={"action": "load_game", "game": "Overwatch"}
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/state").get_json(), before)

    def test_state_is_shared_between_clients_but_not_app_instances(self):
        self.action("update_team", team=1, name="Shared", score=1)
        self.assertEqual(
            self.app.test_client().get("/api/state").get_json()["teams"][0]["Name"],
            "Shared",
        )
        self.assertEqual(
            create_app().test_client().get("/api/state").get_json()["teams"][0]["Name"],
            "",
        )

    def test_every_successful_update_builds_and_prints_current_scene_json(self):
        actions = [
            ("load_game", {"game": "Overwatch"}),
            ("toggle_component", {"scene": "ingame", "component": "Score Ingame"}),
            ("update_team", {"team": 1, "name": "Gryphons", "score": 4}),
            ("add_player", {"team": 1, "player": "Captain"}),
            ("remove_player", {"team": 1, "player": "Captain"}),
            ("add_ban", {"kind": "map", "name": "Ilios"}),
            ("remove_ban", {"kind": "map", "name": "Ilios"}),
            ("add_ban", {"kind": "hero", "name": "Ana"}),
            ("remove_ban", {"kind": "hero", "name": "Ana"}),
            ("select_scene", {"scene": "ingame"}),
            ("swap_sides", {}),
        ]
        for action, fields in actions:
            with self.subTest(action=action, fields=fields):
                self.print_output.reset_mock()
                self.post_overlay.reset_mock()
                with patch.object(
                    self.manager,
                    "create_post_request",
                    wraps=self.manager.create_post_request,
                ) as build:
                    state = self.action(action, **fields)
                    build.assert_called_once_with()
                self.print_output.assert_called_once_with(
                    self.manager.create_post_request()
                )
                self.post_overlay.assert_called_once()
                outgoing = self.post_overlay.call_args.args[0]
                self.assertEqual(outgoing.full_url, "http://127.0.0.1:3000/api/overlay")
                self.assertEqual(outgoing.method, "POST")
                self.assertEqual(
                    outgoing.get_header("Content-type"), "application/json"
                )
                self.assertEqual(
                    json.loads(outgoing.data),
                    json.loads(self.manager.create_post_request()),
                )
                self.assertEqual(state, self.client.get("/api/state").get_json())
                if action == "update_team":
                    document = json.loads(self.print_output.call_args.args[0])
                    self.assertEqual(
                        document["scenes"]["ingame"][0]["data"]["teams"][0],
                        {"name": "Gryphons", "score": 4},
                    )

    def test_rejected_updates_and_reads_do_not_print_scene_json(self):
        with patch.object(
            self.manager, "create_post_request", wraps=self.manager.create_post_request
        ) as build:
            self.client.get("/api/state")
            self.client.get("/api/scenes/ingame")
            for payload in (
                {"action": "unknown"},
                {"action": "update_team", "team": 1, "score": -1},
            ):
                self.assertEqual(
                    self.client.post("/api/control", json=payload).status_code, 400
                )
            build.assert_not_called()
        self.print_output.assert_not_called()
        self.post_overlay.assert_not_called()

    def test_overlay_snapshot_and_failed_delivery_recovery(self):
        self.post_overlay.side_effect = URLError("Frontend offline")
        with self.assertLogs(self.app.logger, level="WARNING"):
            self.action("toggle_component", scene="ingame", component="Score Ingame")
        with self.assertLogs(self.app.logger, level="WARNING"):
            self.action("update_team", team=1, name="Gryphons", score=7)
        response = self.client.get("/api/overlay")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(
            response.get_json(), json.loads(self.manager.create_post_request())
        )
        self.assertEqual(
            response.get_json()["scenes"]["ingame"][0]["data"]["teams"][0]["score"], 7
        )

    def test_overlay_delivery_url_is_configurable(self):
        self.app.config["OVERLAY_POST_URL"] = "http://127.0.0.1:3005/api/overlay"
        self.action("update_team", team=1, score=2)
        self.assertEqual(
            self.post_overlay.call_args.args[0].full_url,
            self.app.config["OVERLAY_POST_URL"],
        )


if __name__ == "__main__":
    unittest.main()

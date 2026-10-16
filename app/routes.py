from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, render_template, request

main = Blueprint("main", __name__, url_prefix="/api")
control = Blueprint("control", __name__)
GAME_DIR = Path(__file__).resolve().parent / "json"
SCENE_NAMES = ("idle", "pregame", "ingame")


def available_games():
    return sorted(path.stem for path in GAME_DIR.glob("*.json"))


def state_data():
    state = current_app.extensions["state_manager"]
    return {
        "game": state.game_info.name,
        "game_key": state.game_key,
        "games": available_games(),
        "scene": state.current_scene,
        "teams": [state.match_info.team_info(1), state.match_info.team_info(2)],
        "ban_options": state.game_info.ban_options(),
        "bans": state.bans,
        "components": {
            scene: [
                {"name": name, "position": position, "enabled": enabled}
                for name, position, enabled in getattr(
                    state, f"current_{scene}_components"
                )
            ]
            for scene in SCENE_NAMES
        },
    }


@control.get("/")
@control.get("/UI")
def dashboard():
    return render_template("index.html")


@main.get("/state")
def get_state():
    with current_app.extensions["state_lock"]:
        response = jsonify(state_data())
    response.headers["Cache-Control"] = "no-store"
    return response


@main.get("/overlay")
def get_overlay():
    """Let the frontend recover the current document after startup or a missed POST."""
    with current_app.extensions["state_lock"]:
        document = current_app.extensions["state_manager"].create_post_request()
    return current_app.response_class(
        document, mimetype="application/json", headers={"Cache-Control": "no-store"}
    )


def publish_overlay(document):
    """Send the scene document without undoing a saved edit if Next.js is offline."""
    target = current_app.config["OVERLAY_POST_URL"]
    if not target:
        return
    outgoing = Request(
        target,
        data=document.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(
            outgoing, timeout=current_app.config["OVERLAY_POST_TIMEOUT"]
        ) as response:
            response.read()
    except (URLError, OSError, ValueError) as error:
        current_app.logger.warning(
            "Overlay delivery failed; the frontend can recover via /api/overlay: %s",
            error,
        )


def required_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
        raise ValueError(
            f"{key.replace('_', ' ').capitalize()} must contain 1–80 characters."
        )
    return value.strip()


@main.post("/control")
def update_state():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object."), 400
    with current_app.extensions["state_lock"]:
        state = current_app.extensions["state_manager"]
        match = state.match_info
        action = data.get("action")
        try:
            if action == "load_game":
                game = required_text(data, "game")
                if game not in available_games():
                    raise ValueError(
                        "Choose a game from the available JSON configurations."
                    )
                state.load_game(game)
            elif action == "select_scene":
                scene_name = data.get("scene")
                if scene_name not in SCENE_NAMES:
                    raise ValueError("Unknown scene.")
                state.current_scene = scene_name
            elif action == "toggle_component":
                scene_name = data.get("scene")
                if scene_name not in SCENE_NAMES:
                    raise ValueError("Unknown scene.")
                name = required_text(data, "component")
                components = getattr(state, f"current_{scene_name}_components")
                component = next((item for item in components if item[0] == name), None)
                if component is None:
                    raise ValueError("Component is not available in this scene.")
                operation = (
                    state.disable_component if component[2] else state.enable_component
                )
                operation(scene_name, name)
            elif action == "swap_sides":
                match.swap_sides()
            elif action in ("add_ban", "remove_ban"):
                state.update_ban(
                    data.get("kind"),
                    required_text(data, "name"),
                    remove=action == "remove_ban",
                )
            elif action in ("update_team", "add_player", "remove_player"):
                team = data.get("team")
                if type(team) is not int or team not in (1, 2):
                    raise ValueError("Team must be 1 or 2.")
                if action == "update_team":
                    if "name" not in data and "score" not in data:
                        raise ValueError("Provide a team name or score.")
                    name = required_text(data, "name") if "name" in data else None
                    score = data.get("score")
                    if "score" in data and (
                        type(score) is not int or not 0 <= score <= 999
                    ):
                        raise ValueError(
                            "Score must be a whole number between 0 and 999."
                        )
                    if name is not None:
                        match.update_team_name(team, name)
                    if "score" in data:
                        match.update_team_score(team, score)
                else:
                    player = required_text(data, "player")
                    if action == "add_player":
                        match.add_player(team, player)
                    elif not match.remove_player(team, player):
                        raise ValueError("Player is no longer on this team.")
            else:
                raise ValueError("Unknown action.")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except (OSError, KeyError, TypeError, StopIteration):
            current_app.logger.exception("Could not load game configuration")
            return jsonify(
                error="Could not load that game JSON. Check its configuration."
            ), 400
        scene_json = state.create_post_request()
        print(scene_json)
        publish_overlay(scene_json)
        return jsonify(state_data())


SCENES = {
    "idle": {
        "title": "Stream starting soon",
        "message": "The broadcast will begin shortly.",
        "status": "idle",
    },
    "pregame": {
        "title": "Get ready",
        "message": "Players are preparing for the next match.",
        "teams": ["Gryphons", "Opponent"],
        "theme": "pregame",
    },
    "ingame": {
        "title": "Match in progress",
        "message": "Live match data will appear here.",
        "score": {"home": 0, "away": 0},
        "teams": ["Gryphons", "Opponent"],
        "theme": "ingame",
    },
    "ui": {
        "title": "GryphDeck control UI",
        "message": "Choose a scene to preview.",
        "routes": ["/idle", "/pregame", "/ingame", "/UI"],
        "theme": "ui",
    },
}


@main.route("/")
def index():
    return jsonify(
        name="GryphDeck API",
        endpoints=[
            "/api/health",
            "/api/state",
            "/api/control",
            "/api/overlay",
            "/api/scenes/<scene>",
        ],
    )


@main.route("/health")
def health():
    return jsonify(status="ok")


@main.route("/scenes/<string:scene>")
def scene(scene):
    scene_data = SCENES.get(scene.lower())
    if scene_data is None:
        return jsonify(error="Scene not found"), 404

    with current_app.extensions["state_lock"]:
        state = state_data()
        result = dict(scene_data)
        if scene.lower() in SCENE_NAMES:
            result.update(
                game=state["game"],
                active=state["scene"] == scene.lower(),
                components=state["components"][scene.lower()],
            )
            if scene.lower() in ("pregame", "ingame"):
                result["bans"] = state["bans"]
                result["teams"] = [team["Name"] for team in state["teams"]]
                result["players"] = [team["Players"] for team in state["teams"]]
            if scene.lower() == "ingame":
                result["score"] = {
                    "home": state["teams"][0]["Score"],
                    "away": state["teams"][1]["Score"],
                }
        return jsonify(scene=scene.lower(), **result)

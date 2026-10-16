import os
from threading import RLock

from flask import Flask

from app.classes.StateManager import StateManager


def create_app():
    """Create the control page and API with one shared, in-memory match."""
    app = Flask(__name__)
    app.config["OVERLAY_POST_URL"] = os.environ.get(
        "OVERLAY_POST_URL", "http://127.0.0.1:3000/api/overlay"
    )
    app.config["OVERLAY_POST_TIMEOUT"] = 1.0
    app.extensions["state_manager"] = StateManager()
    app.extensions["state_lock"] = RLock()

    from app.routes import control, main

    app.register_blueprint(main)
    app.register_blueprint(control)

    @app.after_request
    def add_cors_headers(response):
        """Allow the local Next.js frontend to call the development API."""
        response.headers["Access-Control-Allow-Origin"] = app.config.get(
            "FRONTEND_ORIGIN", "http://localhost:3000"
        )
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    return app

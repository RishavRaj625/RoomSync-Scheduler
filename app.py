"""
app.py

Application entry point. Creates the Flask app, wires up configuration,
initializes the database, registers the routes blueprint, and exposes a
couple of small template globals (theme toggle, file-size formatting).

Run locally with:
    python app.py
"""

from flask import Flask

import config
from database import init_db
from routes import bp as roomsync_bp
import utils


def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    init_db()

    app.register_blueprint(roomsync_bp)

    @app.template_filter("filesize")
    def filesize_filter(value):
        return utils.format_file_size(value)

    @app.context_processor
    def inject_globals():
        from flask import session
        return {"current_username": session.get("username")}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

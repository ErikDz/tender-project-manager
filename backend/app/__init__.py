import os
from flask import Flask
from flask_cors import CORS
from supabase import create_client

from .config import Config


def create_app(config=None):
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config or Config)

    # CORS for Next.js frontend
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # Initialize Supabase client
    supabase_url = app.config["SUPABASE_URL"]
    supabase_key = app.config["SUPABASE_SERVICE_ROLE_KEY"]
    if supabase_url and supabase_key:
        app.supabase = create_client(supabase_url, supabase_key)
    else:
        app.supabase = None

    # Ensure upload directory exists
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # Register blueprints
    from .routes.projects import projects_bp
    from .routes.documents import documents_bp
    from .routes.processing import processing_bp
    from .routes.graph import graph_bp
    from .routes.todos import todos_bp

    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(documents_bp, url_prefix="/api/projects")
    app.register_blueprint(processing_bp, url_prefix="/api")
    app.register_blueprint(graph_bp, url_prefix="/api/projects")
    app.register_blueprint(todos_bp, url_prefix="/api/projects")

    # Health check
    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app

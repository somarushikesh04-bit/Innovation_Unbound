import os
from flask import Flask, jsonify

from app.config import config_by_name
from app.extensions import db, migrate, jwt, cors, limiter


def create_app(config_name: str = None) -> Flask:
    """Application Factory Pattern."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    limiter.init_app(app)

    # Register blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.ledger.routes import ledger_bp
    from app.blueprints.invoices.routes import invoices_bp
    from app.blueprints.analytics.routes import analytics_bp
    from app.blueprints.advisor.routes import advisor_bp
    from app.blueprints.smartshield.routes import shield_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(advisor_bp)
    app.register_blueprint(shield_bp)

    # Health check
    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok", "version": "1.0.0"})

    # Serve SPA
    @app.route("/")
    @app.route("/<path:path>")
    def index(path=""):
        from flask import send_from_directory, render_template
        try:
            return render_template("index.html")
        except Exception:
            return jsonify({"status": "running", "api": "/api"}), 200

    # JWT error handlers
    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": f"Invalid token: {reason}"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"error": "Authentication required"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired"}), 401

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Maximum size is 5 MB."}), 413

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app

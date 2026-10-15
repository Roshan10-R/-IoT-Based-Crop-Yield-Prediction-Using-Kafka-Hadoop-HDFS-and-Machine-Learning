"""
Flask Backend Application for IoT-Based Crop Yield Prediction System.
Exposes REST APIs for sensors, fields, predictions, model metrics, and storage status.
"""
import os
import sys
import logging
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["JSON_SORT_KEYS"] = False

    # CORS — allow React frontend on any origin in development
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize database
    from backend.services.database import DatabaseService
    db = DatabaseService()
    db.init_db()
    db.seed_actual_yields()

    # Register blueprints
    from backend.routes.health import hp
    from backend.routes.fields import bp_fields
    from backend.routes.sensors import bp_sensors
    from backend.routes.predictions import bp_predictions
    from backend.routes.metrics import bp_metrics
    from backend.routes.yields import bp_yields
    from backend.routes.storage import bp_storage

    app.register_blueprint(hp)
    app.register_blueprint(bp_fields)
    app.register_blueprint(bp_sensors)
    app.register_blueprint(bp_predictions)
    app.register_blueprint(bp_metrics)
    app.register_blueprint(bp_yields)
    app.register_blueprint(bp_storage)

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "message": str(e)}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    logger.info("Flask app created. Environment: %s", os.getenv("APP_ENV", "development"))
    return app


app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    logger.info("Starting Flask server on %s:%d (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)

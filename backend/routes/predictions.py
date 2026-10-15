import sys
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, abort

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.database import DatabaseService
from ml.predict import get_predictor, ModelNotFoundError

bp_predictions = Blueprint('predictions', __name__)
db = DatabaseService()
logger = logging.getLogger(__name__)


@bp_predictions.route('/api/predictions', methods=['GET'])
def list_predictions():
    field_id = request.args.get('field_id')
    limit = min(int(request.args.get('limit', 50)), 200)
    preds = db.get_predictions(field_id=field_id, limit=limit)
    return jsonify({'predictions': preds, 'count': len(preds)})


@bp_predictions.route('/api/predictions', methods=['POST'])
def create_prediction():
    data = request.get_json(force=True) or {}
    field_id = data.get('field_id', 'FIELD_001')
    crop_type = data.get('crop_type', 'wheat')
    season = data.get('season', 'rabi')
    area_ha = float(data.get('area_ha', 5.0))
    year = int(data.get('year', 2024))
    demo_mode = bool(data.get('demo_mode', False))
    feature_overrides = data.get('feature_overrides')

    # Fetch recent sensor readings for this field
    sensor_readings = db.get_sensor_history(field_id=field_id, limit=200)

    try:
        predictor = get_predictor()
        result = predictor.predict(
            field_id=field_id,
            crop_type=crop_type,
            season=season,
            area_ha=area_ha,
            year=year,
            sensor_readings=sensor_readings if sensor_readings else None,
            feature_overrides=feature_overrides,
            demo_mode=demo_mode,
        )
    except ModelNotFoundError as exc:
        return jsonify({'error': str(exc), 'hint': 'Run python ml/train.py to train the model'}), 503
    except Exception as exc:
        logger.exception('Prediction error')
        return jsonify({'error': str(exc)}), 500

    # Save prediction
    try:
        pred_id = db.save_prediction(result)
        result['prediction_id'] = pred_id
    except Exception as exc:
        logger.warning('Could not save prediction to DB: %s', exc)

    return jsonify(result), 201

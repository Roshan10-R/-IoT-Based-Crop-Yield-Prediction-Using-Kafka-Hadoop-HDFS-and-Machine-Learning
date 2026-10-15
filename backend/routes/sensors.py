from flask import Blueprint, jsonify, request
from backend.services.database import DatabaseService

bp_sensors = Blueprint('sensors', __name__)
db = DatabaseService()

@bp_sensors.route('/api/sensors/latest')
def latest_readings():
    limit = min(int(request.args.get('limit', 50)), 200)
    readings = db.get_latest_sensor_readings(limit=limit)
    return jsonify({'readings': readings, 'count': len(readings)})

@bp_sensors.route('/api/sensors/history')
def sensor_history():
    field_id = request.args.get('field_id')
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    readings = db.get_sensor_history(
        field_id=field_id, limit=limit, offset=offset,
        start_date=start_date, end_date=end_date
    )
    return jsonify({'readings': readings, 'count': len(readings), 'offset': offset})

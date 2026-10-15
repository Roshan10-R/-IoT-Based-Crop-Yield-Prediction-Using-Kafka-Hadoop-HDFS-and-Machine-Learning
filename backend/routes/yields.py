from flask import Blueprint, jsonify, request
from backend.services.database import DatabaseService

bp_yields = Blueprint('yields', __name__)
db = DatabaseService()

@bp_yields.route('/api/yields/history')
def yield_history():
    field_id = request.args.get('field_id')
    limit = min(int(request.args.get('limit', 100)), 500)
    records = db.get_actual_yields(field_id=field_id, limit=limit)
    return jsonify({'yields': records, 'count': len(records)})

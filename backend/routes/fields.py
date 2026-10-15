from flask import Blueprint, jsonify, request, abort
from backend.services.database import DatabaseService

bp_fields = Blueprint('fields', __name__)
db = DatabaseService()

@bp_fields.route('/api/fields')
def list_fields():
    fields = db.get_fields()
    return jsonify({'fields': fields, 'count': len(fields)})

@bp_fields.route('/api/fields/<field_id>')
def get_field(field_id):
    field = db.get_field(field_id)
    if not field:
        abort(404, description=f'Field {field_id} not found')
    return jsonify(field)

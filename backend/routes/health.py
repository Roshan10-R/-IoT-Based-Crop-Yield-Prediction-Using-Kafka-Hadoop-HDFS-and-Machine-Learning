from flask import Blueprint, jsonify
import os

hp = Blueprint('health', __name__)

@hp.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'Crop Yield Prediction API',
        'version': '1.0.0',
    })

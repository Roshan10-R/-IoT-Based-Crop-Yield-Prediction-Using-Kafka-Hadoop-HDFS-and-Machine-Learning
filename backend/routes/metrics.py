import json
import sys
from pathlib import Path
from flask import Blueprint, jsonify

ROOT = Path(__file__).parent.parent.parent
META_FILE = ROOT / 'ml' / 'saved_models' / 'model_metadata.json'
REPORT_FILE = ROOT / 'ml' / 'reports' / 'evaluation_report.json'

bp_metrics = Blueprint('metrics', __name__)


@bp_metrics.route('/api/model/metrics')
def model_metrics():
    data = {'model_loaded': False}
    if META_FILE.exists():
        with open(META_FILE) as f:
            meta = json.load(f)
        data.update(meta)
        data['model_loaded'] = True
    if REPORT_FILE.exists():
        with open(REPORT_FILE) as f:
            report = json.load(f)
        data['evaluation_report'] = report
    return jsonify(data)

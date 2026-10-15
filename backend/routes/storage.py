import sys
from pathlib import Path
from flask import Blueprint, jsonify

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.hdfs_writer import HDFSWriter
from storage.hdfs_reader import HDFSReader

bp_storage = Blueprint('storage', __name__)
_writer = HDFSWriter()
_reader = HDFSReader()

@bp_storage.route('/api/storage/status')
def storage_status():
    status = _writer.status()
    summary = _reader.inspect_storage()
    return jsonify({'storage_status': status, 'storage_summary': summary})

import React from 'react';
import { 
  Database, 
  Server, 
  FolderTree, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw 
} from 'lucide-react';

export const StorageInspector = ({ storageData = {}, onRefresh }) => {
  const status = storageData?.storage_status || {};
  const summary = storageData?.storage_summary || {};
  const isHdfs = status?.active_backend === 'hdfs';

  const localFiles = summary?.local_fallback?.files || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Storage Architecture Explanation Alert */}
      <div className={`alert-box ${isHdfs ? 'alert-success' : 'alert-warning'}`}>
        {isHdfs ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
        <div>
          <strong>
            Storage Status: {isHdfs ? 'Hadoop HDFS Active' : 'Local Fallback Storage Active (Explicit Mode)'}
          </strong>
          <p style={{ marginTop: '4px' }}>
            {isHdfs
              ? 'Sensor batches are streamed via Kafka Consumer and persisted directly to Hadoop HDFS partitioned by date (/crop-yield/raw/sensor-readings/dt=YYYYMMDD).'
              : 'Hadoop NameNode is not currently reachable on the network. The pipeline has safely activated the local fallback directory (./data/local_fallback/) to prevent silent data loss. When Docker HDFS is started, files can be synchronized without data drops.'}
          </p>
        </div>
      </div>

      {/* Cluster Overview Grid */}
      <div className="cards-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">HDFS Status</span>
            <div className="stat-card-icon" style={{ background: isHdfs ? '#f0fdf4' : '#fef2f2', color: isHdfs ? '#16a34a' : '#dc2626' }}>
              <Server size={20} />
            </div>
          </div>
          <div className="stat-card-value" style={{ fontSize: '1.4rem' }}>
            {status?.hdfs_available ? 'ONLINE' : 'OFFLINE'}
          </div>
          <div className="stat-card-subtext">NameNode: {status?.namenode_url || 'http://localhost:9870'}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Batches Flushed</span>
            <div className="stat-card-icon" style={{ background: '#f8fafc', color: '#0284c7' }}>
              <Database size={20} />
            </div>
          </div>
          <div className="stat-card-value">{status?.batches_written || 0}</div>
          <div className="stat-card-subtext">Batched writes from Kafka Consumer</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">Local Storage Bytes</span>
            <div className="stat-card-icon" style={{ background: '#fffbeb', color: '#d97706' }}>
              <FolderTree size={20} />
            </div>
          </div>
          <div className="stat-card-value">
            {((status?.bytes_written_local || 0) / 1024).toFixed(1)} KB
          </div>
          <div className="stat-card-subtext">{summary?.local_fallback?.file_count || 0} JSONL files</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-card-title">HDFS Storage Bytes</span>
            <div className="stat-card-icon" style={{ background: '#faf5ff', color: '#9333ea' }}>
              <FileText size={20} />
            </div>
          </div>
          <div className="stat-card-value">
            {((status?.bytes_written_hdfs || 0) / 1024).toFixed(1)} KB
          </div>
          <div className="stat-card-subtext">{summary?.hdfs?.file_count || 0} files in cluster</div>
        </div>
      </div>

      {/* Directory Structure & Stored Files */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem' }}>
        {/* Local Fallback Stored Files */}
        <div className="section-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">
                <FolderTree size={18} color="#d97706" />
                Local Fallback Stored Batches (JSONL)
              </h3>
              <p className="panel-subtitle">Path: {status?.local_fallback_path || './data/local_fallback'}</p>
            </div>
            {onRefresh && (
              <button onClick={onRefresh} className="btn-primary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>
                <RefreshCw size={13} /> Refresh
              </button>
            )}
          </div>

          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Format</th>
                  <th>Directory</th>
                </tr>
              </thead>
              <tbody>
                {localFiles.map((fname, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#0f172a' }}>
                      <strong>{fname}</strong>
                    </td>
                    <td><span className="badge badge-green">JSONL</span></td>
                    <td style={{ fontSize: '0.78rem', color: '#64748b' }}>sensor-readings/</td>
                  </tr>
                ))}
                {localFiles.length === 0 && (
                  <tr>
                    <td colSpan="3" style={{ textAlign: 'center', padding: '1.5rem', color: '#94a3b8' }}>
                      No fallback files created yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* HDFS Directory Schema Reference */}
        <div className="section-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">
                <Database size={18} color="#16a34a" />
                Hadoop HDFS Directory Layout
              </h3>
              <p className="panel-subtitle">Configured enterprise namespace hierarchy</p>
            </div>
          </div>

          <div style={{ fontFamily: 'monospace', fontSize: '0.85rem', background: '#0f172a', color: '#e2e8f0', padding: '1.25rem', borderRadius: '8px', lineHeight: '1.8' }}>
            <div style={{ color: '#38bdf8' }}>hdfs://namenode:9000/crop-yield/</div>
            <div style={{ paddingLeft: '1.5rem', color: '#a7f3d0' }}>├── raw/</div>
            <div style={{ paddingLeft: '3rem', color: '#cbd5e1' }}>└── sensor-readings/dt=YYYYMMDD/*.jsonl</div>
            <div style={{ paddingLeft: '1.5rem', color: '#a7f3d0' }}>├── processed/</div>
            <div style={{ paddingLeft: '3rem', color: '#cbd5e1' }}>└── features/crop_features.parquet</div>
            <div style={{ paddingLeft: '1.5rem', color: '#a7f3d0' }}>├── datasets/</div>
            <div style={{ paddingLeft: '3rem', color: '#cbd5e1' }}>└── historical-yield/crop_yield_historical.csv</div>
            <div style={{ paddingLeft: '1.5rem', color: '#a7f3d0' }}>├── models/</div>
            <div style={{ paddingLeft: '3rem', color: '#cbd5e1' }}>└── crop_yield_model.joblib</div>
            <div style={{ paddingLeft: '1.5rem', color: '#a7f3d0' }}>└── predictions/</div>
            <div style={{ paddingLeft: '3rem', color: '#cbd5e1' }}>    └── predictions_log.jsonl</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StorageInspector;

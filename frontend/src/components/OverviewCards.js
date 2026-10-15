import React from 'react';
import { 
  Trees, 
  Droplet, 
  Thermometer, 
  TrendingUp, 
  HardDrive
} from 'lucide-react';

export const OverviewCards = ({ 
  fieldsCount = 5, 
  readings = [], 
  predictionsCount = 0, 
  storageStatus = {} 
}) => {
  // Compute average soil moisture and temperature from latest readings
  const avgMoisture = readings.length > 0 
    ? (readings.reduce((sum, r) => sum + (r.soil_moisture || 0), 0) / readings.length).toFixed(1)
    : '--';

  const avgTemp = readings.length > 0
    ? (readings.reduce((sum, r) => sum + (r.temperature || 0), 0) / readings.length).toFixed(1)
    : '--';

  const backendName = storageStatus?.storage_status?.active_backend === 'hdfs'
    ? 'Hadoop HDFS'
    : 'Local Fallback (Active)';

  return (
    <div className="cards-grid">
      <div className="stat-card">
        <div className="stat-card-header">
          <span className="stat-card-title">Monitored Fields</span>
          <div className="stat-card-icon" style={{ background: '#f0fdf4', color: '#16a34a' }}>
            <Trees size={20} />
          </div>
        </div>
        <div className="stat-card-value">{fieldsCount}</div>
        <div className="stat-card-subtext">Active IoT nodes across regions</div>
      </div>

      <div className="stat-card">
        <div className="stat-card-header">
          <span className="stat-card-title">Avg Soil Moisture</span>
          <div className="stat-card-icon" style={{ background: '#eff6ff', color: '#2563eb' }}>
            <Droplet size={20} />
          </div>
        </div>
        <div className="stat-card-value">{avgMoisture}%</div>
        <div className="stat-card-subtext">Real-time across all sensors</div>
      </div>

      <div className="stat-card">
        <div className="stat-card-header">
          <span className="stat-card-title">Avg Temperature</span>
          <div className="stat-card-icon" style={{ background: '#fffbeb', color: '#d97706' }}>
            <Thermometer size={20} />
          </div>
        </div>
        <div className="stat-card-value">{avgTemp}°C</div>
        <div className="stat-card-subtext">Field thermal readings</div>
      </div>

      <div className="stat-card">
        <div className="stat-card-header">
          <span className="stat-card-title">Total Predictions</span>
          <div className="stat-card-icon" style={{ background: '#faf5ff', color: '#9333ea' }}>
            <TrendingUp size={20} />
          </div>
        </div>
        <div className="stat-card-value">{predictionsCount}</div>
        <div className="stat-card-subtext">30-day pre-harvest forecasts</div>
      </div>

      <div className="stat-card">
        <div className="stat-card-header">
          <span className="stat-card-title">Storage Pipeline</span>
          <div className="stat-card-icon" style={{ background: '#f8fafc', color: '#475569' }}>
            <HardDrive size={20} />
          </div>
        </div>
        <div className="stat-card-value" style={{ fontSize: '1.25rem' }}>{backendName}</div>
        <div className="stat-card-subtext">HDFS REST WebHDFS / Batched JSONL</div>
      </div>
    </div>
  );
};

export default OverviewCards;

import React, { useState } from 'react';
import { 
  Radio, 
  AlertTriangle, 
  Battery, 
  Filter 
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  Legend, 
  BarChart, 
  Bar 
} from 'recharts';

export const SensorMonitor = ({ fields = [], readings = [], onRefresh }) => {
  const [selectedField, setSelectedField] = useState('ALL');

  const filteredReadings = selectedField === 'ALL'
    ? readings
    : readings.filter(r => r.field_id === selectedField);

  // Format data for charts (chronological order)
  const chartData = [...filteredReadings].reverse().slice(-30).map(r => ({
    time: r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '',
    soil_moisture: r.soil_moisture,
    temperature: r.temperature,
    rainfall: r.rainfall,
    field_id: r.field_id,
  }));

  const anomalyCount = filteredReadings.filter(r => r.is_anomaly).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Controls & Filter Bar */}
      <div className="section-panel" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Radio size={20} className="text-primary" style={{ color: '#16a34a' }} />
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Live IoT Telemetry Feed</h2>
            {anomalyCount > 0 && (
              <span className="badge badge-yellow" title="Simulated anomalies labeled for test">
                <AlertTriangle size={14} /> {anomalyCount} Simulated Anomalies Detected
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
              <Filter size={16} color="#64748b" />
              <span>Filter Field:</span>
            </div>
            <select 
              className="form-control" 
              style={{ width: 'auto', padding: '0.4rem 0.75rem' }}
              value={selectedField}
              onChange={(e) => setSelectedField(e.target.value)}
            >
              <option value="ALL">All Fields ({fields.length})</option>
              {fields.map(f => (
                <option key={f.field_id} value={f.field_id}>
                  {f.field_id} - {f.crop_type.toUpperCase()} ({f.state})
                </option>
              ))}
            </select>
            {onRefresh && (
              <button 
                onClick={onRefresh} 
                className="btn-primary" 
                style={{ padding: '0.4rem 0.9rem', fontSize: '0.82rem' }}
              >
                Refresh
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Telemetry Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem' }}>
        {/* Soil Moisture & Temperature Trends */}
        <div className="section-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">Soil Moisture & Temperature Dynamics</h3>
              <p className="panel-subtitle">Streaming time-series readings</p>
            </div>
          </div>
          <div style={{ width: '100%', height: 260 }}>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                  <YAxis yAxisId="left" stroke="#2563eb" fontSize={11} domain={[0, 100]} />
                  <YAxis yAxisId="right" orientation="right" stroke="#d97706" fontSize={11} domain={[0, 60]} />
                  <Tooltip />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="soil_moisture" name="Soil Moisture (%)" stroke="#2563eb" strokeWidth={2.5} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="temperature" name="Temp (°C)" stroke="#d97706" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                No telemetry data yet. Run sensor simulator to stream readings!
              </div>
            )}
          </div>
        </div>

        {/* Rainfall Interval (mm) */}
        <div className="section-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">Precipitation Events (mm)</h3>
              <p className="panel-subtitle">Simulated interval rainfall measurements</p>
            </div>
          </div>
          <div style={{ width: '100%', height: 260 }}>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#0284c7" fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="rainfall" name="Rainfall (mm)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                No precipitation events recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Telemetry Log Table */}
      <div className="section-panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">Latest Sensor Telemetry Log</h3>
            <p className="panel-subtitle">Stored in SQLite & buffered for HDFS batch storage</p>
          </div>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Showing {filteredReadings.slice(0, 15).length} of {filteredReadings.length} records
          </span>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Field ID</th>
                <th>Sensor ID</th>
                <th>Crop</th>
                <th>Growth Stage</th>
                <th>Soil Moisture</th>
                <th>Temperature</th>
                <th>Rainfall</th>
                <th>Battery</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredReadings.slice(0, 15).map((r, i) => (
                <tr key={r.id || i}>
                  <td style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                    {r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '--'}
                  </td>
                  <td><strong>{r.field_id}</strong></td>
                  <td style={{ color: '#64748b' }}>{r.sensor_id}</td>
                  <td>
                    <span className="badge badge-green" style={{ textTransform: 'capitalize' }}>
                      {r.crop_type}
                    </span>
                  </td>
                  <td style={{ textTransform: 'capitalize', color: '#475569' }}>
                    {r.growth_stage}
                  </td>
                  <td>
                    <strong style={{ color: r.soil_moisture < 30 ? '#dc2626' : '#2563eb' }}>
                      {r.soil_moisture}%
                    </strong>
                  </td>
                  <td>{r.temperature}°C</td>
                  <td>{r.rainfall} mm</td>
                  <td>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.8rem' }}>
                      <Battery size={13} color="#16a34a" /> {r.battery_level || 95}%
                    </span>
                  </td>
                  <td>
                    {r.is_anomaly ? (
                      <span className="badge badge-yellow">Anomaly</span>
                    ) : (
                      <span className="badge badge-green">Normal</span>
                    )}
                  </td>
                </tr>
              ))}
              {filteredReadings.length === 0 && (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
                    No sensor readings recorded yet. Start simulator or wait for next telemetry poll.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SensorMonitor;

import React, { useState } from 'react';
import { 
  TrendingUp, 
  AlertCircle, 
  Sparkles, 
  Scale, 
  Clock
} from 'lucide-react';
import { api } from '../services/api';

export const PredictionStudio = ({ fields = [], historicalYields = [], onPredictionDone }) => {
  const [fieldId, setFieldId] = useState(fields[0]?.field_id || 'FIELD_001');
  const [cropType, setCropType] = useState('wheat');
  const [season, setSeason] = useState('rabi');
  const [areaHa, setAreaHa] = useState(5.0);
  const [year, setYear] = useState(2024);
  const [useCustomFeatures, setUseCustomFeatures] = useState(false);
  const [demoMode] = useState(true);

  // Custom sensor overrides
  const [soilMoisture, setSoilMoisture] = useState(55);
  const [temperature, setTemperature] = useState(22);
  const [rainfall, setRainfall] = useState(450);

  const [loading, setLoading] = useState(false);
  const [predictionResult, setPredictionResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFieldChange = (fId) => {
    setFieldId(fId);
    const selected = fields.find(f => f.field_id === fId);
    if (selected) {
      setCropType(selected.crop_type);
      setSeason(selected.season || 'rabi');
      setAreaHa(selected.area_ha || 5.0);
    }
  };

  const handlePredict = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const payload = {
      field_id: fieldId,
      crop_type: cropType,
      season: season,
      area_ha: parseFloat(areaHa),
      year: parseInt(year),
      demo_mode: demoMode,
    };

    if (useCustomFeatures) {
      payload.feature_overrides = {
        avg_soil_moisture_pct: parseFloat(soilMoisture),
        avg_temperature_c: parseFloat(temperature),
        total_rainfall_mm: parseFloat(rainfall),
      };
    }

    try {
      const res = await api.createPrediction(payload);
      setPredictionResult(res);
      if (onPredictionDone) onPredictionDone();
    } catch (err) {
      console.error('Prediction failed:', err);
      setError(err.response?.data?.error || err.message || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  // Find historical records for this field/crop
  const fieldHistory = historicalYields.filter(
    h => h.field_id === fieldId || h.crop_type === cropType
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 30-Day Cutoff Requirement Explanation Alert */}
      <div className="alert-box alert-info">
        <Clock size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>The 30-Day Pre-Harvest Cutoff Principle:</strong>
          <p style={{ marginTop: '3px' }}>
            To prevent data leakage, predictions are computed approximately <strong>30 days before harvest</strong>. 
            Only soil moisture, temperature, and rainfall observed up to this cutoff date are utilized by the regression model.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1.5rem' }}>
        {/* Prediction Form */}
        <div className="section-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">
                <Sparkles size={18} color="#16a34a" /> 
                Generate Crop Yield Prediction
              </h3>
              <p className="panel-subtitle">Configure field, crop, and sensor parameters</p>
            </div>
          </div>

          <form onSubmit={handlePredict}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Select Field</label>
                <select 
                  className="form-control"
                  value={fieldId}
                  onChange={(e) => handleFieldChange(e.target.value)}
                >
                  {fields.map(f => (
                    <option key={f.field_id} value={f.field_id}>
                      {f.field_id} ({f.state || 'India'})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Crop Type</label>
                <select 
                  className="form-control"
                  value={cropType}
                  onChange={(e) => setCropType(e.target.value)}
                >
                  <option value="wheat">Wheat</option>
                  <option value="rice">Rice</option>
                  <option value="maize">Maize</option>
                  <option value="cotton">Cotton</option>
                  <option value="soybean">Soybean</option>
                  <option value="potato">Potato</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Crop Season</label>
                <select 
                  className="form-control"
                  value={season}
                  onChange={(e) => setSeason(e.target.value)}
                >
                  <option value="rabi">Rabi (Winter/Spring)</option>
                  <option value="kharif">Kharif (Monsoon/Autumn)</option>
                  <option value="zaid">Zaid (Summer)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Field Area (Hectares)</label>
                <input 
                  type="number" 
                  step="0.1" 
                  min="0.1" 
                  max="100" 
                  className="form-control"
                  value={areaHa}
                  onChange={(e) => setAreaHa(e.target.value)}
                  required 
                />
              </div>

              <div className="form-group">
                <label className="form-label">Crop Season Year</label>
                <input 
                  type="number" 
                  min="2020" 
                  max="2030" 
                  className="form-control"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  required 
                />
              </div>
            </div>

            {/* Custom Sensor Features Toggle */}
            <div style={{ marginBottom: '1.25rem', padding: '0.85rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                <input 
                  type="checkbox"
                  checked={useCustomFeatures}
                  onChange={(e) => setUseCustomFeatures(e.target.checked)}
                />
                Simulate Custom Weather/Soil Conditions for this prediction
              </label>

              {useCustomFeatures && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.85rem', marginTop: '0.85rem' }}>
                  <div className="form-group">
                    <label className="form-label">Soil Moisture (%)</label>
                    <input 
                      type="number" min="0" max="100" step="1"
                      className="form-control"
                      value={soilMoisture}
                      onChange={(e) => setSoilMoisture(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Avg Temp (°C)</label>
                    <input 
                      type="number" min="-10" max="55" step="0.5"
                      className="form-control"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Cumulative Rain (mm)</label>
                    <input 
                      type="number" min="0" max="3000" step="10"
                      className="form-control"
                      value={rainfall}
                      onChange={(e) => setRainfall(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="alert-box alert-warning">
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )}

            <button 
              type="submit" 
              className="btn-primary" 
              disabled={loading}
              style={{ width: '100%', padding: '0.85rem' }}
            >
              {loading ? 'Evaluating Model...' : 'Calculate 30-Day Ahead Prediction'}
            </button>
          </form>
        </div>

        {/* Prediction Output Card */}
        <div className="section-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header">
            <div>
              <h3 className="panel-title">
                <TrendingUp size={18} color="#2563eb" />
                Prediction Forecast Result
              </h3>
              <p className="panel-subtitle">Predicted yield & timeline analysis</p>
            </div>
          </div>

          {predictionResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ padding: '1.25rem', background: '#f0fdf4', borderRadius: '12px', border: '1px solid #bbf7d0', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#166534', textTransform: 'uppercase' }}>
                    Predicted Yield
                  </div>
                  <div style={{ fontSize: '2.4rem', fontWeight: 800, color: '#15803d', margin: '0.25rem 0' }}>
                    {predictionResult.predicted_yield}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#166534' }}>tonnes / hectare</div>
                </div>

                <div style={{ padding: '1.25rem', background: '#eff6ff', borderRadius: '12px', border: '1px solid #bfdbfe', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#1e40af', textTransform: 'uppercase' }}>
                    Total Estimated Production
                  </div>
                  <div style={{ fontSize: '2.4rem', fontWeight: 800, color: '#1d4ed8', margin: '0.25rem 0' }}>
                    {predictionResult.total_predicted_production_tonnes}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#1e40af' }}>total metric tonnes ({areaHa} ha)</div>
                </div>
              </div>

              {/* 30-Day Timeline Badge */}
              <div style={{ padding: '0.9rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.82rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span><strong>Cutoff Date (Data Limit):</strong></span>
                  <span style={{ fontFamily: 'monospace' }}>{predictionResult.prediction_cutoff_date}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span><strong>Expected Harvest Date:</strong></span>
                  <span style={{ fontFamily: 'monospace' }}>{predictionResult.expected_harvest_date}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#15803d', fontWeight: 600 }}>
                  <span>Lead Time:</span>
                  <span>~30 Days Before Harvest</span>
                </div>
              </div>

              {/* Feature Values */}
              <div>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', color: '#334155' }}>
                  Extracted Feature Vector:
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.4rem', fontSize: '0.78rem' }}>
                  <div style={{ background: '#f1f5f9', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
                    Avg Soil Moisture: <strong>{predictionResult.feature_values?.avg_soil_moisture_pct}%</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
                    Avg Temp: <strong>{predictionResult.feature_values?.avg_temperature_c}°C</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
                    Rainfall: <strong>{predictionResult.feature_values?.total_rainfall_mm} mm</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
                    Growth Days: <strong>{predictionResult.feature_values?.growth_days} days</strong>
                  </div>
                </div>
              </div>

              {/* Quality & Limitation Disclosure */}
              <div style={{ fontSize: '0.75rem', color: '#64748b', background: '#fffbeb', border: '1px solid #fde68a', padding: '0.75rem', borderRadius: '6px' }}>
                <strong>Academic Limitation Note:</strong>
                <ul style={{ paddingLeft: '1.2rem', marginTop: '0.3rem' }}>
                  {predictionResult.prediction_limitations?.map((note, idx) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: '#94a3b8', padding: '3rem 1rem' }}>
              <TrendingUp size={48} strokeWidth={1.5} style={{ marginBottom: '1rem', opacity: 0.6 }} />
              <p style={{ fontWeight: 600 }}>No prediction generated yet.</p>
              <p style={{ fontSize: '0.82rem', marginTop: '0.25rem' }}>
                Fill out the field parameters on the left and click "Calculate 30-Day Ahead Prediction".
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Historical Yield Comparison Table */}
      <div className="section-panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">
              <Scale size={18} color="#0284c7" />
              Historical Yield Benchmark Comparison
            </h3>
            <p className="panel-subtitle">Comparing forecasted yield with previous harvest seasons</p>
          </div>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Field ID</th>
                <th>Crop Type</th>
                <th>Season</th>
                <th>Harvest Year</th>
                <th>Actual Yield (t/ha)</th>
                <th>Total Area (ha)</th>
                <th>Harvest Date</th>
                <th>Data Source</th>
              </tr>
            </thead>
            <tbody>
              {fieldHistory.map((h, i) => (
                <tr key={h.id || i}>
                  <td><strong>{h.field_id}</strong></td>
                  <td style={{ textTransform: 'capitalize' }}>{h.crop_type}</td>
                  <td style={{ textTransform: 'capitalize' }}>{h.season}</td>
                  <td>{h.year}</td>
                  <td><strong style={{ color: '#0369a1' }}>{h.actual_yield} t/ha</strong></td>
                  <td>{h.area_ha} ha</td>
                  <td>{h.harvest_date || 'Historical'}</td>
                  <td><span className="badge badge-blue">{h.data_source || 'ground_truth'}</span></td>
                </tr>
              ))}
              {fieldHistory.length === 0 && (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '1.5rem', color: '#94a3b8' }}>
                    No historical harvest records found for this field/crop.
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

export default PredictionStudio;

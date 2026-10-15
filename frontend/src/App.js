import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import OverviewCards from './components/OverviewCards';
import SensorMonitor from './components/SensorMonitor';
import PredictionStudio from './components/PredictionStudio';
import ModelEvaluation from './components/ModelEvaluation';
import StorageInspector from './components/StorageInspector';
import { api } from './services/api';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [fields, setFields] = useState([]);
  const [readings, setReadings] = useState([]);
  const [historicalYields, setHistoricalYields] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [storageStatus, setStorageStatus] = useState({});
  const [predictionsCount, setPredictionsCount] = useState(0);
  const [backendHealth, setBackendHealth] = useState({ status: 'connecting' });
  const [isLivePolling] = useState(true);

  // Load initial app data
  const loadData = useCallback(async () => {
    try {
      const [hRes, fRes, sRes, yRes, mRes, stRes, pRes] = await Promise.allSettled([
        api.getHealth(),
        api.getFields(),
        api.getLatestSensors(50),
        api.getYieldHistory(),
        api.getModelMetrics(),
        api.getStorageStatus(),
        api.getPredictions(),
      ]);

      if (hRes.status === 'fulfilled') setBackendHealth(hRes.value);
      if (fRes.status === 'fulfilled') setFields(fRes.value.fields || []);
      if (sRes.status === 'fulfilled') setReadings(sRes.value.readings || []);
      if (yRes.status === 'fulfilled') setHistoricalYields(yRes.value.yields || []);
      if (mRes.status === 'fulfilled') setMetrics(mRes.value || {});
      if (stRes.status === 'fulfilled') setStorageStatus(stRes.value || {});
      if (pRes.status === 'fulfilled') setPredictionsCount(pRes.value.count || 0);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  }, []);

  // Poll sensor data periodically
  useEffect(() => {
    loadData();
    let interval = null;
    if (isLivePolling) {
      interval = setInterval(() => {
        api.getLatestSensors(50)
          .then(res => setReadings(res.readings || []))
          .catch(() => {});
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loadData, isLivePolling]);

  return (
    <div className="app-container">
      <Navbar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        systemStatus={{
          backend: backendHealth,
          storage: storageStatus,
          metrics: metrics,
        }}
      />

      <main className="main-content">
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
            <OverviewCards 
              fieldsCount={fields.length}
              readings={readings}
              predictionsCount={predictionsCount}
              storageStatus={storageStatus}
            />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem' }}>
              <div className="section-panel">
                <div className="panel-header">
                  <div>
                    <h3 className="panel-title">End-to-End Pipeline Architecture</h3>
                    <p className="panel-subtitle">Data flow across IoT, Streaming, Storage, and Machine Learning</p>
                  </div>
                </div>
                <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.86rem', lineHeight: '1.8' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#15803d', fontWeight: 700 }}>
                    1. IoT Sensor Simulator 
                    <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>→ Multi-field telemetry (moisture, temp, rain)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#0369a1', fontWeight: 700 }}>
                    2. Apache Kafka 
                    <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>→ Topic `sensor-readings` with 3 partitions</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#854d0e', fontWeight: 700 }}>
                    3. Hadoop HDFS 
                    <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>→ Batched WebHDFS JSONL partitioned by date</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#7e22ce', fontWeight: 700 }}>
                    4. Scikit-Learn Model 
                    <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>→ 30-day pre-harvest regression with no data leakage</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: '#0f172a', fontWeight: 700 }}>
                    5. Flask REST API & React Dashboard 
                    <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>→ Real-time agricultural decision support</span>
                  </div>
                </div>
              </div>

              <div className="section-panel">
                <div className="panel-header">
                  <div>
                    <h3 className="panel-title">Quick Actions</h3>
                    <p className="panel-subtitle">Key demonstration shortcuts for examiners & evaluators</p>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <button 
                    onClick={() => setActiveTab('predict')} 
                    className="btn-primary" 
                    style={{ justifyContent: 'flex-start' }}
                  >
                    Test 30-Day Yield Forecast Tool
                  </button>
                  <button 
                    onClick={() => setActiveTab('sensors')} 
                    className="btn-primary" 
                    style={{ justifyContent: 'flex-start', background: '#0284c7' }}
                  >
                    Inspect Live Sensor Streams & Anomalies
                  </button>
                  <button 
                    onClick={() => setActiveTab('model')} 
                    className="btn-primary" 
                    style={{ justifyContent: 'flex-start', background: '#7e22ce' }}
                  >
                    View Model Benchmark (LR vs RF vs GBR)
                  </button>
                </div>
              </div>
            </div>

            <SensorMonitor 
              fields={fields} 
              readings={readings.slice(0, 10)} 
              onRefresh={loadData} 
            />
          </div>
        )}

        {activeTab === 'sensors' && (
          <SensorMonitor 
            fields={fields} 
            readings={readings} 
            onRefresh={loadData} 
          />
        )}

        {activeTab === 'predict' && (
          <PredictionStudio 
            fields={fields} 
            historicalYields={historicalYields}
            onPredictionDone={loadData}
          />
        )}

        {activeTab === 'model' && (
          <ModelEvaluation metrics={metrics} />
        )}

        {activeTab === 'storage' && (
          <StorageInspector storageData={storageStatus} onRefresh={loadData} />
        )}
      </main>

      <footer className="app-footer">
        <p>
          IoT-Based Crop Yield Prediction System • Apache Kafka • Hadoop HDFS • Machine Learning
        </p>
        <p style={{ marginTop: '4px', fontSize: '0.72rem', color: '#94a3b8' }}>
          Final Year CSE Academic Project • Evaluated with Chronological Split & 30-Day Cutoff
        </p>
      </footer>
    </div>
  );
}

export default App;

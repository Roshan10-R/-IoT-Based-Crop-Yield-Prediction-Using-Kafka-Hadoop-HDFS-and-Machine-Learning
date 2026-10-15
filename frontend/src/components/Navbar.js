import React from 'react';
import { 
  Sprout, 
  Activity, 
  TrendingUp, 
  BarChart3, 
  Database,
  Radio
} from 'lucide-react';

export const Navbar = ({ activeTab, setActiveTab, systemStatus }) => {
  const isBackendOk = systemStatus.backend?.status === 'ok';
  const isHdfsOk = systemStatus.storage?.storage_status?.hdfs_available;
  const isModelLoaded = systemStatus.metrics?.model_loaded;

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand-section">
          <div className="brand-icon-wrapper">
            <Sprout size={26} strokeWidth={2.2} />
          </div>
          <div>
            <h1 className="brand-title">AgriPredict</h1>
            <p className="brand-subtitle">IoT Sensors • Apache Kafka • Hadoop HDFS • ML</p>
          </div>
        </div>

        <nav className="nav-tabs">
          <button 
            className={`nav-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Activity size={16} />
            Overview
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'sensors' ? 'active' : ''}`}
            onClick={() => setActiveTab('sensors')}
          >
            <Radio size={16} />
            IoT Telemetry
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'predict' ? 'active' : ''}`}
            onClick={() => setActiveTab('predict')}
          >
            <TrendingUp size={16} />
            Yield Prediction (30-Day)
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'model' ? 'active' : ''}`}
            onClick={() => setActiveTab('model')}
          >
            <BarChart3 size={16} />
            Model Evaluation
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'storage' ? 'active' : ''}`}
            onClick={() => setActiveTab('storage')}
          >
            <Database size={16} />
            HDFS Storage
          </button>
        </nav>

        <div className="status-badges">
          <div className={`status-pill ${isBackendOk ? 'online' : 'offline'}`} title="Flask REST API Status">
            <span className="status-dot"></span>
            API: {isBackendOk ? 'Online' : 'Offline'}
          </div>
          <div className={`status-pill ${isHdfsOk ? 'online' : 'warning'}`} title="Storage Backend">
            <span className="status-dot"></span>
            {isHdfsOk ? 'HDFS' : 'Local Fallback'}
          </div>
          <div className={`status-pill ${isModelLoaded ? 'online' : 'offline'}`} title="ML Model State">
            <span className="status-dot"></span>
            ML: {isModelLoaded ? 'Ready' : 'Not Loaded'}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;

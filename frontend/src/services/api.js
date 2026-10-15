import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

export const api = {
  // Health
  getHealth: () => client.get('/api/health').then(r => r.data),

  // Fields
  getFields: () => client.get('/api/fields').then(r => r.data),
  getField: (fieldId) => client.get(`/api/fields/${fieldId}`).then(r => r.data),

  // Sensors
  getLatestSensors: (limit = 20) =>
    client.get(`/api/sensors/latest?limit=${limit}`).then(r => r.data),
  getSensorHistory: (fieldId, limit = 50) => {
    const url = fieldId
      ? `/api/sensors/history?field_id=${fieldId}&limit=${limit}`
      : `/api/sensors/history?limit=${limit}`;
    return client.get(url).then(r => r.data);
  },

  // Predictions
  getPredictions: (fieldId) => {
    const url = fieldId
      ? `/api/predictions?field_id=${fieldId}`
      : '/api/predictions';
    return client.get(url).then(r => r.data);
  },
  createPrediction: (payload) =>
    client.post('/api/predictions', payload).then(r => r.data),

  // Model & Metrics
  getModelMetrics: () => client.get('/api/model/metrics').then(r => r.data),

  // Historical Yields
  getYieldHistory: (fieldId) => {
    const url = fieldId
      ? `/api/yields/history?field_id=${fieldId}`
      : '/api/yields/history';
    return client.get(url).then(r => r.data);
  },

  // Storage (HDFS / Local Fallback)
  getStorageStatus: () => client.get('/api/storage/status').then(r => r.data),
};

export default api;

import axios from 'axios';

// Use relative URLs to go through Vite proxy in development
// In production, the frontend and backend will be served together
const API_BASE_URL = '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const medicineAPI = {
  // Analyze medicine image
  analyzeMedicine: async (imageBase64, mimeType = 'image/jpeg') => {
    const response = await apiClient.post('/analyze', {
      image_base64: imageBase64,
      mime_type: mimeType,
    });
    return response.data;
  },

  // Upload image file
  uploadImage: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/analyze/image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export const safetyAPI = {
  // Analyze patient safety
  analyzePatientSafety: async (age, allergies, medications, conditions) => {
    const response = await apiClient.post('/patient-safety', {
      age,
      allergies,
      current_medications: medications,
      medical_conditions: conditions,
    });
    return response.data;
  },

  // Quick check
  quickCheck: async (medications, allergies) => {
    const response = await apiClient.get('/patient-safety/check', {
      params: { medications, allergies },
    });
    return response.data;
  },
};

export const dashboardAPI = {
  // Get statistics
  getStats: async () => {
    const response = await apiClient.get('/dashboard/stats');
    return response.data;
  },

  // Get scan history
  getHistory: async (limit = 20) => {
    const response = await apiClient.get('/dashboard/history', {
      params: { limit },
    });
    return response.data;
  },

  // Record a scan
  recordScan: async (verdict, medicineName, confidence) => {
    const response = await apiClient.post('/dashboard/record-scan', null, {
      params: { verdict, medicine_name: medicineName, confidence },
    });
    return response.data;
  },

  // Get verdict breakdown
  getVerdictBreakdown: async () => {
    const response = await apiClient.get('/dashboard/verdict-breakdown');
    return response.data;
  },
};

export const healthAPI = {
  // Health check
  check: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      return response.data;
    } catch (error) {
      throw new Error('Backend unavailable');
    }
  },
};

export default apiClient;

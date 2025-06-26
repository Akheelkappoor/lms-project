import api from './api';

const classService = {
  getClasses: async (params = {}) => {
    const response = await api.get('/classes', { params });
    return response.data;
  },

  getClass: async (classId) => {
    const response = await api.get(`/classes/${classId}`);
    return response.data;
  },

  createClass: async (classData) => {
    const response = await api.post('/classes', classData);
    return response.data;
  },

  updateClass: async (classId, classData) => {
    const response = await api.put(`/classes/${classId}`, classData);
    return response.data;
  },

  startClass: async (classId) => {
    const response = await api.post(`/classes/${classId}/start`);
    return response.data;
  },

  endClass: async (classId, classData) => {
    const response = await api.post(`/classes/${classId}/end`, classData);
    return response.data;
  },

  cancelClass: async (classId, reason) => {
    const response = await api.post(`/classes/${classId}/cancel`, { reason });
    return response.data;
  },

  getTodayClasses: async () => {
    const response = await api.get('/classes/today');
    return response.data;
  },
};

export default classService;
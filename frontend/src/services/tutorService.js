import api from './api';

const tutorService = {
  getTutors: async (params = {}) => {
    const response = await api.get('/tutors', { params });
    return response.data;
  },

  getTutor: async (tutorId) => {
    const response = await api.get(`/tutors/${tutorId}`);
    return response.data;
  },

  createTutor: async (tutorData) => {
    const response = await api.post('/tutors', tutorData);
    return response.data;
  },

  updateTutor: async (tutorId, tutorData) => {
    const response = await api.put(`/tutors/${tutorId}`, tutorData);
    return response.data;
  },

  uploadDocument: async (tutorId, file, documentType) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    const response = await api.post(`/tutors/${tutorId}/documents`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  verifyTutor: async (tutorId, status) => {
    const response = await api.post(`/tutors/${tutorId}/verify`, { status });
    return response.data;
  },
};

export default tutorService;
// frontend/src/services/userService.js (update)
import api from './api';

const userService = {
  getCurrentUser: async () => {
    // For now, decode user info from token or use a placeholder
    const token = localStorage.getItem('accessToken');
    if (token) {
      try {
        // Decode JWT payload (simplified)
        const payload = JSON.parse(atob(token.split('.')[1]));
        return {
          id: payload.sub,
          full_name: payload.full_name || 'User',
          role: payload.role || 'student',
          email: payload.email || 'user@example.com'
        };
      } catch (error) {
        console.error('Token decode error:', error);
      }
    }
    
    // Fallback for development
    return {
      id: '1',
      full_name: 'Demo User',
      role: 'admin',
      email: 'demo@example.com'
    };
  },

  getUsers: async (params = {}) => {
    const response = await api.get('/users', { params });
    return response.data;
  },

  createUser: async (userData) => {
    const response = await api.post('/users', userData);
    return response.data;
  },

  updateUser: async (userId, userData) => {
    const response = await api.put(`/users/${userId}`, userData);
    return response.data;
  },

  deleteUser: async (userId) => {
    const response = await api.delete(`/users/${userId}`);
    return response.data;
  },

  activateUser: async (userId) => {
    const response = await api.post(`/users/${userId}/activate`);
    return response.data;
  },

  deactivateUser: async (userId) => {
    const response = await api.post(`/users/${userId}/deactivate`);
    return response.data;
  },
};

export default userService;
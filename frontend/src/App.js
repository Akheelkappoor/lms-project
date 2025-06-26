import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { Box } from '@mui/material';

// Auth Components
import Login from './components/auth/Login';
import ForgotPassword from './components/auth/ForgotPassword';
import ResetPassword from './components/auth/ResetPassword';

// Layout Components
import Layout from './components/layout/Layout';
import ProtectedRoute from './components/auth/ProtectedRoute';

// Page Components
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import Tutors from './pages/Tutors';
import Students from './pages/Students';
import Classes from './pages/Classes';
import Attendance from './pages/Attendance';
import Finance from './pages/Finance';
import Reports from './pages/Reports';
import Profile from './pages/Profile';

// Admin Components
import TutorManagement from './pages/admin/TutorManagement';
import StudentManagement from './pages/admin/StudentManagement';
import DepartmentManagement from './pages/admin/DepartmentManagement';

function App() {
  const { isAuthenticated } = useSelector((state) => state.auth);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Routes>
        {/* Public Routes */}
        <Route 
          path="/login" 
          element={!isAuthenticated ? <Login /> : <Navigate to="/dashboard" />} 
        />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        
        {/* Protected Routes */}
        <Route path="/" element={<ProtectedRoute />}>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="users" element={<Users />} />
            <Route path="tutors" element={<Tutors />} />
            <Route path="students" element={<Students />} />
            <Route path="classes" element={<Classes />} />
            <Route path="attendance" element={<Attendance />} />
            <Route path="finance" element={<Finance />} />
            <Route path="reports" element={<Reports />} />
            <Route path="profile" element={<Profile />} />
            
            {/* Admin Routes */}
            <Route path="admin/tutors" element={<TutorManagement />} />
            <Route path="admin/students" element={<StudentManagement />} />
            <Route path="admin/departments" element={<DepartmentManagement />} />
          </Route>
        </Route>
        
        {/* Catch all route */}
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </Box>
  );
}

export default App;
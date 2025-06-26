// frontend/src/components/layout/Sidebar.js
import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  Typography,
  Avatar,
  Divider,
  Chip,
  useTheme,
} from '@mui/material';
import {
  Dashboard,
  People,
  School,
  Class,
  Assignment,
  AttachMoney,
  Assessment,
  Person,
  ExitToApp,
  SchoolOutlined,
} from '@mui/icons-material';
import { logoutUser } from '../../store/slices/authSlice';

const menuItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/dashboard', roles: ['superadmin', 'admin', 'coordinator', 'tutor', 'student'] },
  { text: 'Users', icon: <People />, path: '/users', roles: ['superadmin', 'admin'] },
  { text: 'Tutors', icon: <School />, path: '/tutors', roles: ['superadmin', 'admin', 'coordinator'] },
  { text: 'Students', icon: <Person />, path: '/students', roles: ['superadmin', 'admin', 'coordinator'] },
  { text: 'Classes', icon: <Class />, path: '/classes', roles: ['superadmin', 'admin', 'coordinator', 'tutor', 'student'] },
  { text: 'Attendance', icon: <Assignment />, path: '/attendance', roles: ['superadmin', 'admin', 'coordinator', 'tutor'] },
  { text: 'Finance', icon: <AttachMoney />, path: '/finance', roles: ['superadmin', 'admin', 'finance_coordinator'] },
  { text: 'Reports', icon: <Assessment />, path: '/reports', roles: ['superadmin', 'admin', 'coordinator'] },
  { text: 'Profile', icon: <Person />, path: '/profile', roles: ['superadmin', 'admin', 'coordinator', 'tutor', 'student'] },
];

const Sidebar = ({ open, onClose, isMobile }) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);

  const handleLogout = () => {
    dispatch(logoutUser());
    navigate('/login');
  };

  const filteredMenuItems = menuItems.filter(item => 
    item.roles.includes(user?.role || 'student')
  );

  const drawerContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo and Title */}
      <Box
        sx={{
          p: 3,
          background: 'linear-gradient(135deg, #F1A150, #C86706)',
          color: 'white',
          textAlign: 'center',
        }}
      >
        <SchoolOutlined sx={{ fontSize: 40, mb: 1 }} />
        <Typography variant="h6" fontWeight="bold">
          i2Global LMS
        </Typography>
      </Box>

      {/* User Profile */}
      <Box sx={{ p: 3, textAlign: 'center', bgcolor: 'grey.50' }}>
        <Avatar
          sx={{
            width: 64,
            height: 64,
            mx: 'auto',
            mb: 2,
            bgcolor: 'primary.main',
          }}
        >
          {user?.full_name?.charAt(0) || 'U'}
        </Avatar>
        <Typography variant="h6" gutterBottom>
          {user?.full_name || 'Demo User'}
        </Typography>
        <Chip
          label={user?.role?.replace('_', ' ').toUpperCase() || 'USER'}
          color="primary"
          size="small"
        />
      </Box>

      <Divider />

      {/* Navigation Menu */}
      <List sx={{ flexGrow: 1, py: 1 }}>
        {filteredMenuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              onClick={() => {
                navigate(item.path);
                if (isMobile) onClose();
              }}
              selected={location.pathname === item.path}
              sx={{
                mx: 1,
                my: 0.5,
                borderRadius: 2,
                '&.Mui-selected': {
                  bgcolor: 'primary.light',
                  color: 'primary.contrastText',
                  '& .MuiListItemIcon-root': {
                    color: 'primary.contrastText',
                  },
                },
                '&:hover': {
                  bgcolor: 'primary.light',
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText 
                primary={item.text} 
                sx={{ '& .MuiTypography-root': { fontWeight: 500 } }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Divider />

      {/* Logout */}
      <List>
        <ListItem disablePadding>
          <ListItemButton
            onClick={handleLogout}
            sx={{
              mx: 1,
              my: 1,
              borderRadius: 2,
              color: 'error.main',
              '&:hover': {
                bgcolor: 'error.light',
                color: 'error.contrastText',
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}>
              <ExitToApp />
            </ListItemIcon>
            <ListItemText 
              primary="Logout" 
              sx={{ '& .MuiTypography-root': { fontWeight: 500 } }}
            />
          </ListItemButton>
        </ListItem>
      </List>
    </Box>
  );

  return (
    <Drawer
      variant={isMobile ? 'temporary' : 'persistent'}
      anchor="left"
      open={open}
      onClose={onClose}
      ModalProps={{
        keepMounted: true, // Better open performance on mobile
      }}
      sx={{
        width: 280,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 280,
          boxSizing: 'border-box',
          borderRight: 'none',
          boxShadow: theme.shadows[3],
        },
      }}
    >
      {drawerContent}
    </Drawer>
  );
};

export default Sidebar;
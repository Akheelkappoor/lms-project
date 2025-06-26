// frontend/src/pages/Dashboard.js (COMPLETE UPDATED FILE)
import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Avatar,
  LinearProgress,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Chip,
  Paper,
} from '@mui/material';
import {
  People,
  Class,
  AttachMoney,
  TrendingUp,
  PlayArrow,
  Schedule,
} from '@mui/icons-material';
import { useQuery } from 'react-query';
import api from '../services/api';

const StatCard = ({ title, value, icon, color, trend }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Avatar sx={{ bgcolor: color, mr: 2 }}>
          {icon}
        </Avatar>
        <Box>
          <Typography variant="h4" component="div" fontWeight="bold">
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {title}
          </Typography>
        </Box>
      </Box>
      {trend && (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <TrendingUp sx={{ color: 'success.main', mr: 1, fontSize: 16 }} />
          <Typography variant="body2" color="success.main">
            {trend}% from last month
          </Typography>
        </Box>
      )}
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const { user } = useSelector((state) => state.auth);

  const { data: dashboardStats, isLoading } = useQuery(
    'dashboardStats',
    async () => {
      try {
        const response = await api.get('/dashboard/stats');
        return response.data;
      } catch (error) {
        console.log('Backend not available, using mock data');
        // Return mock data for development
        return {
          user_stats: {
            total_users: 150,
            total_tutors: 25,
            total_students: 120,
            total_coordinators: 5
          },
          class_stats: {
            today_classes: 8,
            classes_this_month: 240
          },
          financial_stats: {
            revenue_this_month: 125000,
            pending_fees: 25000
          },
          recent_activities: [
            {
              id: '1',
              title: 'Mathematics Class',
              subject: 'Mathematics',
              scheduled_start: new Date().toISOString(),
              status: 'completed'
            },
            {
              id: '2',
              title: 'English Class',
              subject: 'English',
              scheduled_start: new Date(Date.now() - 3600000).toISOString(),
              status: 'completed'
            },
            {
              id: '3',
              title: 'Science Class',
              subject: 'Science',
              scheduled_start: new Date(Date.now() + 3600000).toISOString(),
              status: 'scheduled'
            }
          ],
          monthly_stats: {
            total_classes: 45,
            completed_classes: 42,
            attendance_rate: 95,
            projected_earnings: 15000
          },
          performance: {
            total_classes_taught: 120,
            performance_rating: 4.8,
            verification_status: 'verified'
          },
          fee_info: {
            total_pending: 5000,
            pending_fees_count: 2
          },
          academic_info: {
            grade_level: '10th',
            educational_board: 'CBSE',
            classes_enrolled: ['Mathematics', 'Science', 'English']
          }
        };
      }
    },
    {
      retry: false, // Don't retry on failure during development
    }
  );

  const { data: todayClasses } = useQuery(
    'todayClasses',
    async () => {
      try {
        const response = await api.get('/classes/today');
        return response.data;
      } catch (error) {
        console.log('Backend not available, using mock data for today classes');
        // Return mock data for development
        return {
          classes: [
            {
              id: '1',
              title: 'Mathematics - Algebra',
              subject: 'Mathematics',
              scheduled_start: new Date(Date.now() + 1800000).toISOString(), // 30 minutes from now
              scheduled_end: new Date(Date.now() + 5400000).toISOString(), // 1.5 hours from now
              status: 'scheduled',
              meeting_url: 'https://zoom.us/j/123456789'
            },
            {
              id: '2',
              title: 'English Literature',
              subject: 'English',
              scheduled_start: new Date(Date.now() + 7200000).toISOString(), // 2 hours from now
              scheduled_end: new Date(Date.now() + 10800000).toISOString(), // 3 hours from now
              status: 'scheduled',
              meeting_url: 'https://meet.google.com/abc-defg-hij'
            },
            {
              id: '3',
              title: 'Physics - Mechanics',
              subject: 'Physics',
              scheduled_start: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
              scheduled_end: new Date(Date.now() - 1800000).toISOString(), // 30 minutes ago
              status: 'completed',
              meeting_url: 'https://zoom.us/j/987654321'
            }
          ]
        };
      }
    },
    {
      retry: false,
    }
  );

  const renderAdminDashboard = () => (
    <Grid container spacing={3}>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Total Users"
          value={dashboardStats?.user_stats?.total_users || 0}
          icon={<People />}
          color="primary.main"
          trend={12}
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Total Tutors"
          value={dashboardStats?.user_stats?.total_tutors || 0}
          icon={<People />}
          color="success.main"
          trend={8}
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Total Students"
          value={dashboardStats?.user_stats?.total_students || 0}
          icon={<People />}
          color="info.main"
          trend={15}
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Today's Classes"
          value={dashboardStats?.class_stats?.today_classes || 0}
          icon={<Class />}
          color="warning.main"
        />
      </Grid>
      
      <Grid item xs={12} md={8}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Recent Activities
            </Typography>
            <List>
              {dashboardStats?.recent_activities?.slice(0, 5).map((activity, index) => (
                <ListItem key={index}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: 'primary.main' }}>
                      <Class />
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={activity.title}
                    secondary={`${activity.subject} - ${new Date(activity.scheduled_start).toLocaleString()}`}
                  />
                  <Chip
                    label={activity.status}
                    color={
                      activity.status === 'completed' ? 'success' :
                      activity.status === 'ongoing' ? 'warning' :
                      activity.status === 'cancelled' ? 'error' : 'default'
                    }
                    size="small"
                  />
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Financial Overview
            </Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Revenue This Month
              </Typography>
              <Typography variant="h5" color="success.main" fontWeight="bold">
                ₹{dashboardStats?.financial_stats?.revenue_this_month?.toLocaleString() || 0}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Pending Fees
              </Typography>
              <Typography variant="h5" color="warning.main" fontWeight="bold">
                ₹{dashboardStats?.financial_stats?.pending_fees?.toLocaleString() || 0}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const renderTutorDashboard = () => (
    <Grid container spacing={3}>
      <Grid item xs={12} md={8}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Today's Classes
            </Typography>
            {todayClasses?.classes?.length > 0 ? (
              <List>
                {todayClasses.classes.map((cls) => (
                  <ListItem
                    key={cls.id}
                    sx={{
                      bgcolor: 'background.default',
                      borderRadius: 2,
                      mb: 1,
                    }}
                  >
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: 'primary.main' }}>
                        <Class />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={cls.title}
                      secondary={`${cls.subject} - ${new Date(cls.scheduled_start).toLocaleTimeString()}`}
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      {cls.status === 'scheduled' && (
                        <Button
                          variant="contained"
                          size="small"
                          startIcon={<PlayArrow />}
                          onClick={() => window.open(cls.meeting_url, '_blank')}
                        >
                          Join Class
                        </Button>
                      )}
                      <Chip
                        label={cls.status}
                        color={
                          cls.status === 'completed' ? 'success' :
                          cls.status === 'ongoing' ? 'warning' :
                          cls.status === 'scheduled' ? 'info' : 'default'
                        }
                        size="small"
                      />
                    </Box>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                No classes scheduled for today
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={4}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <StatCard
              title="Classes This Month"
              value={dashboardStats?.monthly_stats?.total_classes || 0}
              icon={<Class />}
              color="primary.main"
            />
          </Grid>
          <Grid item xs={12}>
            <StatCard
              title="Attendance Rate"
              value={`${Math.round(dashboardStats?.monthly_stats?.attendance_rate || 0)}%`}
              icon={<Schedule />}
              color="success.main"
            />
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  This Month's Earnings
                </Typography>
                <Typography variant="h4" color="success.main" fontWeight="bold">
                  ₹{dashboardStats?.monthly_stats?.projected_earnings?.toLocaleString() || 0}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={75}
                  sx={{ mt: 2 }}
                />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  75% of expected earnings
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );

  const renderStudentDashboard = () => (
    <Grid container spacing={3}>
      <Grid item xs={12} md={8}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Today's Classes
            </Typography>
            {todayClasses?.classes?.length > 0 ? (
              <List>
                {todayClasses.classes.map((cls) => (
                  <ListItem
                    key={cls.id}
                    sx={{
                      bgcolor: 'background.default',
                      borderRadius: 2,
                      mb: 1,
                    }}
                  >
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: 'primary.main' }}>
                        <Class />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={cls.title}
                      secondary={`${cls.subject} - ${new Date(cls.scheduled_start).toLocaleTimeString()}`}
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      {cls.status === 'scheduled' && (
                        <Button
                          variant="contained"
                          size="small"
                          startIcon={<PlayArrow />}
                          onClick={() => window.open(cls.meeting_url, '_blank')}
                        >
                          Join Class
                        </Button>
                      )}
                    </Box>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                No classes scheduled for today
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>
      
      <Grid item xs={12} md={4}>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <StatCard
              title="Attendance Rate"
              value={`${Math.round(dashboardStats?.monthly_stats?.attendance_rate || 0)}%`}
              icon={<Schedule />}
              color="success.main"
            />
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Fee Status
                </Typography>
                <Typography variant="h5" color="warning.main" fontWeight="bold">
                  ₹{dashboardStats?.fee_info?.total_pending?.toLocaleString() || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Pending Amount
                </Typography>
                {dashboardStats?.fee_info?.total_pending > 0 && (
                  <Button variant="contained" size="small" sx={{ mt: 2 }}>
                    Pay Now
                  </Button>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <LinearProgress sx={{ width: '50%' }} />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        Welcome back, {user?.full_name || 'User'}!
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Here's what's happening with your account today.
      </Typography>
      
      <Box sx={{ mt: 3 }}>
        {user?.role === 'superadmin' || user?.role === 'admin' ? renderAdminDashboard() :
         user?.role === 'tutor' ? renderTutorDashboard() :
         user?.role === 'student' ? renderStudentDashboard() :
         renderAdminDashboard()}
      </Box>
    </Box>
  );
};

export default Dashboard;
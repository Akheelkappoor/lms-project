import React from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Container,
  Paper,
  Avatar,
  Alert,
} from '@mui/material';
import { EmailOutlined, ArrowBack } from '@mui/icons-material';
import { useForm } from 'react-hook-form';

const ForgotPassword = () => {
  const [submitted, setSubmitted] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  const onSubmit = async (data) => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
    }, 1000);
  };

  return (
    <Container component="main" maxWidth="sm">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #F1A150 0%, #C86706 100%)',
        }}
      >
        <Paper
          elevation={10}
          sx={{
            padding: 4,
            borderRadius: 3,
            width: '100%',
            maxWidth: 400,
            backgroundColor: 'white',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              mb: 3,
            }}
          >
            <Avatar
              sx={{
                m: 1,
                bgcolor: 'primary.main',
                width: 56,
                height: 56,
              }}
            >
              <EmailOutlined fontSize="large" />
            </Avatar>
            <Typography component="h1" variant="h4" fontWeight="bold">
              Forgot Password
            </Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center">
              Enter your email address to reset your password
            </Typography>
          </Box>

          {submitted ? (
            <Alert severity="success" sx={{ mb: 2 }}>
              Password reset instructions have been sent to your email address.
            </Alert>
          ) : (
            <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
              <TextField
                margin="normal"
                required
                fullWidth
                id="email"
                label="Email Address"
                name="email"
                autoComplete="email"
                autoFocus
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address',
                  },
                })}
                error={!!errors.email}
                helperText={errors.email?.message}
              />
              <Button
                type="submit"
                fullWidth
                variant="contained"
                sx={{
                  mt: 3,
                  mb: 2,
                  py: 1.5,
                  fontSize: '1.1rem',
                  fontWeight: 600,
                }}
                disabled={loading}
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </Button>
            </Box>
          )}

          <Box textAlign="center">
            <Link
              to="/login"
              style={{
                color: '#F1A150',
                textDecoration: 'none',
                fontSize: '0.9rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <ArrowBack fontSize="small" />
              Back to Login
            </Link>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
};

export default ForgotPassword;
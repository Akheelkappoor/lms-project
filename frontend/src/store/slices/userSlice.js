import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import userService from '../../services/userService';

export const fetchUsers = createAsyncThunk(
  'user/fetchUsers',
  async (params = {}, { rejectWithValue }) => {
    try {
      const response = await userService.getUsers(params);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data?.error || 'Failed to fetch users');
    }
  }
);

export const createUser = createAsyncThunk(
  'user/createUser',
  async (userData, { rejectWithValue }) => {
    try {
      const response = await userService.createUser(userData);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data?.error || 'Failed to create user');
    }
  }
);

const initialState = {
  users: [],
  currentUser: null,
  loading: false,
  error: null,
  pagination: {
    total: 0,
    pages: 0,
    current_page: 1,
  },
};

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setCurrentUser: (state, action) => {
      state.currentUser = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch users
      .addCase(fetchUsers.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchUsers.fulfilled, (state, action) => {
        state.loading = false;
        state.users = action.payload.users;
        state.pagination = {
          total: action.payload.total,
          pages: action.payload.pages,
          current_page: action.payload.current_page,
        };
      })
      .addCase(fetchUsers.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      // Create user
      .addCase(createUser.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createUser.fulfilled, (state, action) => {
        state.loading = false;
        state.users.push(action.payload.user);
      })
      .addCase(createUser.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { clearError, setCurrentUser } = userSlice.actions;
export default userSlice.reducer;
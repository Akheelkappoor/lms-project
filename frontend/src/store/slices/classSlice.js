import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import classService from '../../services/classService';

export const fetchClasses = createAsyncThunk(
  'classes/fetchClasses',
  async (params = {}, { rejectWithValue }) => {
    try {
      const response = await classService.getClasses(params);
      return response;
    } catch (error) {
      return rejectWithValue(error.response?.data?.error || 'Failed to fetch classes');
    }
  }
);

const initialState = {
  classes: [],
  todayClasses: [],
  loading: false,
  error: null,
  pagination: {
    total: 0,
    pages: 0,
    current_page: 1,
  },
};

const classSlice = createSlice({
  name: 'classes',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchClasses.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchClasses.fulfilled, (state, action) => {
        state.loading = false;
        state.classes = action.payload.classes;
        state.pagination = {
          total: action.payload.total,
          pages: action.payload.pages,
          current_page: action.payload.current_page,
        };
      })
      .addCase(fetchClasses.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { clearError } = classSlice.actions;
export default classSlice.reducer;
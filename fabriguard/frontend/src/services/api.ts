import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const authData = localStorage.getItem('fabriguard-auth')
    if (authData) {
      const { state } = JSON.parse(authData)
      if (state?.token) {
        config.headers.Authorization = `Bearer ${state.token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth and redirect to login
      localStorage.removeItem('fabriguard-auth')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// API endpoints
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  me: () => api.get('/auth/me'),
}

export const assetsApi = {
  list: (params?: Record<string, any>) => api.get('/assets', { params }),
  get: (id: string) => api.get(`/assets/${id}`),
  create: (data: any) => api.post('/assets', data),
  update: (id: string, data: any) => api.put(`/assets/${id}`, data),
  delete: (id: string) => api.delete(`/assets/${id}`),
  healthSummary: () => api.get('/assets/health-summary'),
}

export const sensorsApi = {
  list: (params?: Record<string, any>) => api.get('/sensors', { params }),
  get: (id: string) => api.get(`/sensors/${id}`),
  create: (data: any) => api.post('/sensors', data),
  update: (id: string, data: any) => api.put(`/sensors/${id}`, data),
}

export const alertsApi = {
  list: (params?: Record<string, any>) => api.get('/alerts', { params }),
  get: (id: string) => api.get(`/alerts/${id}`),
  acknowledge: (id: string) => api.post(`/alerts/${id}/acknowledge`),
  resolve: (id: string, data: any) => api.post(`/alerts/${id}/resolve`, data),
  dismiss: (id: string, data: any) => api.post(`/alerts/${id}/dismiss`, data),
  summary: () => api.get('/alerts/summary'),
}

export const workOrdersApi = {
  list: (params?: Record<string, any>) => api.get('/work-orders', { params }),
  get: (id: string) => api.get(`/work-orders/${id}`),
  create: (data: any) => api.post('/work-orders', data),
  update: (id: string, data: any) => api.put(`/work-orders/${id}`, data),
  start: (id: string) => api.post(`/work-orders/${id}/start`),
  complete: (id: string, data: any) => api.post(`/work-orders/${id}/complete`, data),
  summary: () => api.get('/work-orders/summary'),
}

export const dashboardApi = {
  overview: () => api.get('/dashboard/overview'),
  healthTrends: (days?: number) => api.get('/dashboard/health-trends', { params: { days } }),
  alertTrends: (days?: number) => api.get('/dashboard/alert-trends', { params: { days } }),
}

export const predictionsApi = {
  forAsset: (assetId: string, params?: Record<string, any>) =>
    api.get(`/predictions/asset/${assetId}`, { params }),
  latest: (assetId: string, type?: string) =>
    api.get(`/predictions/latest/${assetId}`, { params: { prediction_type: type } }),
  rulSummary: () => api.get('/predictions/rul-summary'),
  trends: (assetId: string, days?: number) =>
    api.get(`/predictions/trends/${assetId}`, { params: { days } }),
}

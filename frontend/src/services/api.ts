import axios from 'axios'
import type { AxiosAdapter } from 'axios'
import {
  clearAccessToken,
  getAccessToken,
  setNeedLoginNotice,
} from '../utils/authStorage'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

export const passthroughAdapter: AxiosAdapter = (config) => {
  return axios.getAdapter(axios.defaults.adapter)(config)
}

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      const isLogin = url.includes('/auth/login')
      if (!isLogin) {
        clearAccessToken()
        setNeedLoginNotice()
        if (window.location.pathname !== '/login') {
          window.location.replace('/login')
        }
      }
    }
    return Promise.reject(error)
  },
)

export default api

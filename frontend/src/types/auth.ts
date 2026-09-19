export interface AuthUser {
  id: number
  username: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginData {
  access_token: string
  token_type: 'bearer'
  user: AuthUser
}

export interface LogoutData {
  logged_out: true
}

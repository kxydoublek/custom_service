import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../hooks/useAuth'
import { getApiErrorMessage } from '../utils/apiError'
import { clearAuthNotice, peekAuthNotice } from '../utils/authStorage'

const LOGIN_UNAUTHORIZED_TEXT = '账号或密码不正确'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(() => peekAuthNotice())
  const [passwordInvalid, setPasswordInvalid] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = Boolean(username.trim() && password) && !submitting

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSubmit) return
    clearAuthNotice()
    setError(null)
    setPasswordInvalid(false)
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate('/employee', { replace: true })
    } catch (err) {
      setError(getApiErrorMessage(err, LOGIN_UNAUTHORIZED_TEXT))
      setPasswordInvalid(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={(event) => void handleSubmit(event)}>
        <h1 className="page-title">智能客服系统</h1>
        {error ? (
          <div className="error-bar" role="alert">
            {error}
          </div>
        ) : null}
        <label htmlFor="username">用户名</label>
        <input
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(event) => {
            setUsername(event.target.value)
            setPasswordInvalid(false)
          }}
        />
        <label htmlFor="password">密码</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          className={passwordInvalid ? 'field-error' : undefined}
          value={password}
          onChange={(event) => {
            setPassword(event.target.value)
            setPasswordInvalid(false)
          }}
        />
        <div className="login-actions">
          <button className="btn btn-primary" type="submit" disabled={!canSubmit}>
            登录
          </button>
        </div>
      </form>
    </div>
  )
}

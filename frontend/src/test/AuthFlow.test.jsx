import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { useState } from 'react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../contexts/AuthContext'
import Navigation from '../components/Navigation'
import AuthCallback from '../components/AuthCallback'
import PublicPage from '../components/PublicPage'
import AdminPage from '../components/AdminPage'
import DashboardPage from '../components/DashboardPage'
import ProfilePage from '../components/ProfilePage'
import NotFoundPage from '../components/NotFoundPage'
import ProtectedRoute from '../components/ProtectedRoute'

// Mock AWS Amplify
vi.mock('aws-amplify', () => ({
  Amplify: {
    configure: vi.fn(),
  },
}))

vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
  getCurrentUser: vi.fn(),
}))

vi.mock('aws-amplify/utils', () => ({
  Hub: {
    listen: vi.fn(),
    remove: vi.fn(),
  },
}))

// Mock aws-exports
vi.mock('../aws-exports', () => ({
  default: {
    Auth: {
      region: 'ap-southeast-2',
      userPoolId: 'test-pool-id',
      userPoolWebClientId: 'test-client-id',
      identityPoolId: 'test-identity-pool-id',
      oauth: {
        domain: 'test-domain.auth.ap-southeast-2.amazoncognito.com',
        scope: ['email', 'openid', 'profile'],
        redirectSignIn: 'https://test.cloudfront.net/',
        redirectSignOut: 'https://test.cloudfront.net/',
        responseType: 'code',
        pkce: true,
      },
    },
  },
}))

// Create a test component that wraps the App content without BrowserRouter
const AppContent = () => {
  const [count, setCount] = useState(0)

  return (
    <AuthProvider>
      <div className="App">
        <Navigation />

        <main className="main-content">
          <Routes>
            <Route
              path="/"
              element={
                <div className="home-page">
                  <h1>Welcome to SFLT</h1>
                  <p>Static React site deployed with AWS CDK to CloudFront + S3</p>
                  <div className="card">
                    <button onClick={() => setCount((count) => count + 1)}>Count is {count}</button>
                  </div>
                  <p className="description">
                    This site is hosted on S3 and served through CloudFront using Origin Access
                    Control (OAC).
                  </p>
                </div>
              }
            />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/public" element={<PublicPage />} />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <AdminPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  )
}

const renderApp = (initialPath = '/') => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppContent />
    </MemoryRouter>
  )
}

describe('Authentication Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('should render home page without authentication', async () => {
    const { getCurrentUser } = await import('aws-amplify/auth')
    getCurrentUser.mockRejectedValue(new Error('No current user'))

    renderApp()

    await waitFor(() => {
      expect(screen.getByText('Welcome to SFLT')).toBeInTheDocument()
    })
  })

  test('should show sign-in button for unauthenticated users accessing protected routes', async () => {
    const { getCurrentUser } = await import('aws-amplify/auth')
    getCurrentUser.mockRejectedValue(new Error('No current user'))

    renderApp('/admin')

    await waitFor(() => {
      expect(screen.getByText('Authentication Required')).toBeInTheDocument()
      expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
    })
  })

  test('should call signInWithRedirect when sign-in button is clicked', async () => {
    const { getCurrentUser, signInWithRedirect } = await import('aws-amplify/auth')
    getCurrentUser.mockRejectedValue(new Error('No current user'))
    signInWithRedirect.mockResolvedValue()

    renderApp('/admin')

    await waitFor(() => {
      expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
    })

    // Click sign in button
    fireEvent.click(screen.getByText('Sign in with Google'))

    await waitFor(() => {
      expect(signInWithRedirect).toHaveBeenCalledWith({ provider: 'Google' })
    })
  })

  test('should show protected content for authenticated users', async () => {
    const { getCurrentUser } = await import('aws-amplify/auth')
    getCurrentUser.mockResolvedValue({
      userId: 'test-user-id',
      username: 'test-user',
      attributes: {
        email: 'test@example.com',
      },
    })

    renderApp('/admin')

    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument()
      expect(
        screen.getByText('This is a protected admin page that requires authentication.')
      ).toBeInTheDocument()
    })
  })

  test('should show user email in navigation when authenticated', async () => {
    const { getCurrentUser } = await import('aws-amplify/auth')
    getCurrentUser.mockResolvedValue({
      userId: 'test-user-id',
      username: 'test-user',
      attributes: {
        email: 'test@example.com',
      },
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
      expect(screen.getByText('Sign Out')).toBeInTheDocument()
    })
  })

  test('should call signOut when sign out button is clicked', async () => {
    const { getCurrentUser, signOut } = await import('aws-amplify/auth')
    getCurrentUser.mockResolvedValue({
      userId: 'test-user-id',
      username: 'test-user',
      attributes: {
        email: 'test@example.com',
      },
    })
    signOut.mockResolvedValue()

    renderApp()

    await waitFor(() => {
      expect(screen.getByText('Sign Out')).toBeInTheDocument()
    })

    // Click sign out button
    fireEvent.click(screen.getByText('Sign Out'))

    await waitFor(() => {
      expect(signOut).toHaveBeenCalled()
    })
  })
})

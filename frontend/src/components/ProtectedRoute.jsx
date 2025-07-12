import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'

const ProtectedRoute = ({ children }) => {
  const { user, loading, signInWithGoogle } = useAuth()

  // Show loading spinner while checking auth state
  if (loading) {
    return (
      <div className="protected-route-loading">
        <h2>Loading...</h2>
        <p>Checking authentication status...</p>
      </div>
    )
  }

  // If not authenticated, show sign-in prompt
  if (!user) {
    return (
      <div className="protected-route-signin">
        <h1>Authentication Required</h1>
        <p>You need to sign in to access this page.</p>
        <button
          onClick={signInWithGoogle}
          className="signin-button"
          style={{
            padding: '12px 24px',
            backgroundColor: '#4285f4',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '16px',
            marginTop: '16px',
          }}
        >
          Sign in with Google
        </button>
      </div>
    )
  }

  // If authenticated, render the protected content
  return children
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
}

export default ProtectedRoute

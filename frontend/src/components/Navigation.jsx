import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const Navigation = () => {
  const { isAuthenticated, user, signInWithGoogle, signOut, loading } = useAuth()

  return (
    <nav className="navigation">
      <div className="nav-links">
        <Link to="/">Home</Link>
        <Link to="/public">Public</Link>

        {/* Show protected links only when authenticated */}
        {isAuthenticated && (
          <>
            <Link to="/admin">Admin</Link>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/profile">Profile</Link>
          </>
        )}
      </div>

      <div className="nav-auth">
        {loading ? (
          <span>Loading...</span>
        ) : isAuthenticated ? (
          <div className="auth-info">
            <span className="user-email">
              {user?.attributes?.email || user?.username || 'User'}
            </span>
            <button
              onClick={signOut}
              className="auth-button signout-button"
              style={{
                padding: '8px 16px',
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                marginLeft: '12px',
              }}
            >
              Sign Out
            </button>
          </div>
        ) : (
          <button
            onClick={signInWithGoogle}
            className="auth-button signin-button"
            style={{
              padding: '8px 16px',
              backgroundColor: '#4285f4',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Sign In with Google
          </button>
        )}
      </div>
    </nav>
  )
}

export default Navigation

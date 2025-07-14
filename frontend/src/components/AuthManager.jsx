import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'

/**
 * AuthManager handles OAuth callback processing when Lambda@Edge redirects to root
 * with OAuth parameters (code, state, etc.)
 */
const AuthManager = ({ children }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const { loading } = useAuth()

  useEffect(() => {
    const handleOAuthCallback = async () => {
      try {
        // Check if this is an OAuth callback (has code parameter)
        const urlParams = new URLSearchParams(location.search)
        const code = urlParams.get('code')
        const state = urlParams.get('state')

        if (code && state) {
          console.log('OAuth callback detected, processing...')

          // AWS Amplify will automatically handle the OAuth callback
          // We just need to parse the state and redirect to target
          const stateData = JSON.parse(decodeURIComponent(state))
          const targetUrl = stateData.target

          console.log(`Target URL from state: ${targetUrl}`)

          // Wait for Amplify to process the callback
          // The auth state will be updated via Hub listener in AuthContext
          setTimeout(() => {
            if (targetUrl && targetUrl !== '/') {
              console.log(`Redirecting to target URL: ${targetUrl}`)
              navigate(targetUrl, { replace: true })
            } else {
              console.log('No target URL, staying on home page')
              navigate('/', { replace: true })
            }
          }, 2000) // Give Amplify time to process

          return
        }

        // Not an OAuth callback, proceed normally
        console.log('No OAuth callback parameters detected')
      } catch (error) {
        console.error('Error handling OAuth callback:', error)
        // On error, clear query parameters and stay on current page
        navigate(location.pathname, { replace: true })
      }
    }

    // Only process if we have search parameters
    if (location.search) {
      handleOAuthCallback()
    }
  }, [location, navigate])

  // Show loading state during OAuth callback processing
  if (
    location.search &&
    (location.search.includes('code=') || location.search.includes('error='))
  ) {
    return (
      <div className="auth-callback">
        <h2>Completing sign in...</h2>
        <p>Please wait while we process your authentication.</p>
        {loading && <div className="loading-spinner">Loading...</div>}
      </div>
    )
  }

  // Normal rendering
  return children
}

AuthManager.propTypes = {
  children: PropTypes.node.isRequired
}

export default AuthManager

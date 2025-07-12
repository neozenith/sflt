import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

const AuthCallback = () => {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const handleAuthCallback = () => {
      try {
        // Parse the query parameters
        const urlParams = new URLSearchParams(location.search)
        const state = urlParams.get('state')

        if (state) {
          // Decode the state parameter to get the target URL
          const stateData = JSON.parse(decodeURIComponent(state))
          const targetUrl = stateData.target

          if (targetUrl && targetUrl !== '/') {
            console.log(`Redirecting to target URL: ${targetUrl}`)
            // Redirect to the original target URL
            navigate(targetUrl, { replace: true })
            return
          }
        }

        // Default redirect to home if no target specified
        console.log('No target URL found, redirecting to home')
        navigate('/', { replace: true })
      } catch (error) {
        console.error('Error handling auth callback:', error)
        // Fallback to home page
        navigate('/', { replace: true })
      }
    }

    // Small delay to ensure Amplify has processed the callback
    const timer = setTimeout(handleAuthCallback, 1000)

    return () => clearTimeout(timer)
  }, [location, navigate])

  return (
    <div className="auth-callback">
      <h2>Completing sign in...</h2>
      <p>Please wait while we redirect you.</p>
    </div>
  )
}

export default AuthCallback

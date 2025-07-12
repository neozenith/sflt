import { createContext, useContext, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { Amplify } from 'aws-amplify'
import { fetchAuthSession, signInWithRedirect, signOut, getCurrentUser } from 'aws-amplify/auth'
import { Hub } from 'aws-amplify/utils'
import awsconfig from '../aws-exports'

// Configure Amplify
Amplify.configure(awsconfig)

const AuthContext = createContext()

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Check current authentication state
  const checkAuthState = async () => {
    try {
      setLoading(true)
      const currentUser = await getCurrentUser()
      setUser(currentUser)
      setError(null)
    } catch (err) {
      setUser(null)
      // Don't set error for "No current user" - this is expected when not logged in
      if (err.name !== 'UserUnauthorizedException') {
        setError(err.message || 'Authentication error')
      }
    } finally {
      setLoading(false)
    }
  }

  // Sign in with Google (Hosted UI)
  const signInWithGoogle = async () => {
    try {
      setError(null)
      await signInWithRedirect({ provider: 'Google' })
    } catch (err) {
      setError(err.message || 'Failed to sign in with Google')
      throw err
    }
  }

  // Sign out
  const signOutUser = async () => {
    try {
      setError(null)
      await signOut()
      setUser(null)
    } catch (err) {
      setError(err.message || 'Failed to sign out')
      throw err
    }
  }

  // Get user attributes (including Google tokens)
  const getUserAttributes = async () => {
    try {
      if (!user) return null
      // In v6, attributes are included in the user object
      return user.signInDetails || null
    } catch (err) {
      setError(err.message || 'Failed to get user attributes')
      return null
    }
  }

  // Get current session (includes tokens)
  const getCurrentSession = async () => {
    try {
      if (!user) return null
      const session = await fetchAuthSession()
      return session
    } catch (err) {
      setError(err.message || 'Failed to get current session')
      return null
    }
  }

  // Listen for auth events
  useEffect(() => {
    // Check initial auth state
    checkAuthState()

    // Listen for auth state changes
    const listener = (data) => {
      const { payload } = data

      switch (payload.event) {
        case 'signIn':
        case 'cognitoHostedUI':
          setUser(payload.data)
          setError(null)
          break
        case 'signOut':
          setUser(null)
          setError(null)
          break
        case 'signIn_failure':
        case 'cognitoHostedUI_failure':
          setError(payload.data?.message || 'Authentication failed')
          setUser(null)
          break
        default:
          break
      }
    }

    Hub.listen('auth', listener)

    // Cleanup
    return () => Hub.remove('auth', listener)
  }, [])

  const value = {
    user,
    loading,
    error,
    signInWithGoogle,
    signOut: signOutUser,
    getUserAttributes,
    getCurrentSession,
    isAuthenticated: !!user,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
}

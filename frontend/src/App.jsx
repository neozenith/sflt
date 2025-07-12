import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import AdminPage from './components/AdminPage'
import DashboardPage from './components/DashboardPage'
import ProfilePage from './components/ProfilePage'
import PublicPage from './components/PublicPage'
import NotFoundPage from './components/NotFoundPage'
import ProtectedRoute from './components/ProtectedRoute'
import Navigation from './components/Navigation'
import AuthCallback from './components/AuthCallback'
import AuthManager from './components/AuthManager'
import { AuthProvider } from './contexts/AuthContext'
import './App.css'

function HomePage() {
  const [count, setCount] = useState(0)

  return (
    <div className="home-page">
      <h1>Welcome to SFLT</h1>
      <p>Static React site deployed with AWS CDK to CloudFront + S3</p>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>Count is {count}</button>
      </div>
      <p className="description">
        This site is hosted on S3 and served through CloudFront using Origin Access Control (OAC).
      </p>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <AuthManager>
            <Navigation />

            <main className="main-content">
              <Routes>
                <Route path="/" element={<HomePage />} />
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
          </AuthManager>
        </div>
      </Router>
    </AuthProvider>
  )
}

export default App

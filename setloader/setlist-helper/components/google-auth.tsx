"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { LogIn, LogOut, User, Mail, Calendar } from "lucide-react"
import { apiService, getApiAuthHeaders } from "@/lib/api"

interface UserInfo {
  user_id: string
  google_id: string
  email: string
  name: string
  picture: string
  created_at: string
  last_login: string
}

interface GoogleAuthProps {
  onAuthChange?: (isAuthenticated: boolean, user?: UserInfo) => void
}

export function GoogleAuth({ onAuthChange }: GoogleAuthProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<UserInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Check authentication status on component mount
  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        const response = await apiService.getUserStatus()
        if (response.ok && response.data) {
          const data = response.data
          if (data.authenticated && data.user_email) {
            setIsAuthenticated(true)
            setUser({
              user_id: data.user_id || `user_${data.user_email.split('@')[0]}`,
              google_id: data.google_id || `user_${data.user_email.split('@')[0]}`,
              email: data.user_email,
              name: data.user_email.split('@')[0],
              picture: data.picture || '',
              created_at: data.created_at || new Date().toISOString(),
              last_login: data.last_login || new Date().toISOString()
            })
          } else {
            setIsAuthenticated(false)
            setUser(null)
          }
        } else {
          setIsAuthenticated(false)
          setUser(null)
        }
      } catch (error) {
        console.error('Auth check failed:', error)
        setIsAuthenticated(false)
        setUser(null)
      }
    }
    
    checkAuthStatus()
  }, [])

  const handleGoogleLogin = async () => {
    setError(null)
    try {
      // First, try to get Google OAuth URL
      const response = await fetch(`${apiService.getBaseUrl()}/auth/google`, {
        method: 'GET',
        headers: getApiAuthHeaders(),
      })
      
      if (response.ok) {
        const data = await response.json()
        if (data.authorization_url) {
          window.location.href = data.authorization_url
          return
        }
      }
      
      // Fallback to development login if Google OAuth is not configured
      const loginResponse = await apiService.login()
      if (loginResponse.ok && loginResponse.data) {
        const { user_id, session_token, user_email, user_name } = loginResponse.data
        
        // Store session token for future requests
        if (session_token) {
          localStorage.setItem('session_token', session_token)
        }
        
        // Re-check authentication status
        const authResponse = await apiService.getUserStatus()
        if (authResponse.ok && authResponse.data?.authenticated) {
          setIsAuthenticated(true)
          setUser({
            user_id: authResponse.data.user_id || user_id,
            google_id: authResponse.data.user_id || user_id,
            email: authResponse.data.user_email || user_email,
            name: authResponse.data.user_email?.split('@')[0] || user_name,
            picture: '',
            created_at: authResponse.data.session_created || new Date().toISOString(),
            last_login: new Date().toISOString()
          })
          if (onAuthChange) {
            onAuthChange(true, user)
          }
        }
      }
    } catch (error) {
      console.error('Login failed:', error)
      setError('Login failed')
    }
  }

  const handleLogout = async () => {
    try {
      await apiService.logout()
      setIsAuthenticated(false)
      setUser(null)
      // Clear localStorage to remove session data
      localStorage.removeItem('session_id')
      // Call onAuthChange to notify parent component of logout
      if (onAuthChange) {
        onAuthChange(false)
      }
      // Reload the page to clear all session data
      window.location.reload()
    } catch (error) {
      console.error('Logout failed:', error)
      setError('Failed to logout')
    }
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-red-600 text-center">
            <p className="font-semibold">Authentication Error</p>
            <p className="text-sm mt-1">{error}</p>
            <Button 
              onClick={() => setError(null)} 
              variant="outline" 
              className="mt-2"
            >
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!isAuthenticated) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LogIn className="h-5 w-5" />
            Sign In
          </CardTitle>
          <CardDescription>
            Sign in with your Google account to access your setlists and backups
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button 
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 shadow-sm h-12"
          >
            <div className="flex items-center justify-center w-5 h-5">
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            </div>
            <span className="font-medium text-gray-700">Sign In</span>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" />
          Welcome, {user?.name}
        </CardTitle>
        <CardDescription>
          You are signed in with your Google account
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {user?.picture && (
          <div className="flex items-center gap-3">
            <img 
              src={user.picture} 
              alt={user.name} 
              className="w-12 h-12 rounded-full"
            />
            <div>
              <p className="font-medium">{user.name}</p>
              <p className="text-sm text-gray-600">{user.email}</p>
            </div>
          </div>
        )}
        
        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            <span>{user?.email}</span>
          </div>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            <span>Member since {new Date(user?.created_at || '').toLocaleDateString()}</span>
          </div>
        </div>

        <Button 
          onClick={handleLogout}
          variant="outline"
          className="w-full"
        >
          <LogOut className="h-4 w-4 mr-2" />
          Sign Out
        </Button>
      </CardContent>
    </Card>
  )
}
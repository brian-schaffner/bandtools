"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { LogIn, LogOut, User, Mail, Calendar } from "lucide-react"
import { apiService } from "@/lib/api"

interface UserInfo {
  user_id: string
  email: string
  name: string
  created_at: string
  last_login: string
}

interface SimpleAuthProps {
  onAuthChange?: (isAuthenticated: boolean, user?: UserInfo) => void
}

export function SimpleAuth({ onAuthChange }: SimpleAuthProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<UserInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
              email: data.user_email,
              name: data.user_email.split('@')[0],
              created_at: data.session_created || new Date().toISOString(),
              last_login: new Date().toISOString()
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

  const handleLogin = async () => {
    setError(null)
    setLoading(true)
    try {
      // Call the login endpoint to create a session
      const response = await apiService.login()
      if (response.ok && response.data) {
        const { user_id, session_token } = response.data
        
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
            email: authResponse.data.user_email,
            name: authResponse.data.user_email.split('@')[0],
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
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await apiService.logout()
      setIsAuthenticated(false)
      setUser(null)
      if (onAuthChange) {
        onAuthChange(false)
      }
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  if (isAuthenticated && user) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Welcome Back
          </CardTitle>
          <CardDescription>
            You are signed in to your account
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">{user.email}</span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Member since {new Date(user.created_at).toLocaleDateString()}
              </span>
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

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LogIn className="h-5 w-5" />
          Sign In
        </CardTitle>
        <CardDescription>
          Sign in to access your setlists and backups
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
        <Button 
          onClick={handleLogin}
          disabled={loading}
          className="w-full"
        >
          <LogIn className="h-4 w-4 mr-2" />
          {loading ? "Signing in..." : "Sign In"}
        </Button>
      </CardContent>
    </Card>
  )
}

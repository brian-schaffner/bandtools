"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { getApiAuthHeaders, getApiBaseUrl } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, CheckCircle, XCircle } from "lucide-react"

function GoogleCallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const error = searchParams.get('error')

      if (error) {
        setStatus('error')
        setMessage(`Authentication failed: ${error}`)
        return
      }

      if (!code) {
        setStatus('error')
        setMessage('No authorization code received')
        return
      }

      try {
        const response = await fetch(`${getApiBaseUrl()}/auth/google/callback?code=${code}&state=${state || ''}`, {
          method: 'GET',
          headers: getApiAuthHeaders(),
        })

        if (response.ok) {
          const data = await response.json()

          if (data.session_token) {
            localStorage.setItem('session_token', data.session_token)
          }

          setStatus('success')
          setMessage('Authentication successful! Redirecting...')

          setTimeout(() => {
            router.push('/')
          }, 2000)
        } else {
          const errorData = await response.json().catch(() => ({}))
          setStatus('error')
          setMessage(errorData.detail || `Authentication failed (HTTP ${response.status})`)
        }
      } catch (error) {
        console.error('Callback error:', error)
        setStatus('error')
        setMessage('Network error during authentication')
      }
    }

    handleCallback()
  }, [searchParams, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {status === 'loading' && <Loader2 className="h-5 w-5 animate-spin" />}
            {status === 'success' && <CheckCircle className="h-5 w-5 text-green-600" />}
            {status === 'error' && <XCircle className="h-5 w-5 text-red-600" />}
            Google Authentication
          </CardTitle>
          <CardDescription>
            {status === 'loading' && 'Processing your authentication...'}
            {status === 'success' && 'Successfully authenticated with Google'}
            {status === 'error' && (message || 'Authentication failed')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status === 'loading' && (
            <div className="text-center">
              <p className="text-sm text-gray-600">Please wait while we complete your authentication.</p>
            </div>
          )}

          {status === 'success' && (
            <div className="text-center">
              <p className="text-sm text-green-600 mb-4">{message}</p>
              <Button onClick={() => router.push('/')} className="w-full">
                Continue to App
              </Button>
            </div>
          )}

          {status === 'error' && (
            <div className="text-center">
              <p className="text-sm text-red-600 mb-4">{message}</p>
              <div className="space-y-2">
                <Button onClick={() => router.push('/')} className="w-full">
                  Back to Login
                </Button>
                <Button
                  onClick={() => window.location.reload()}
                  variant="outline"
                  className="w-full"
                >
                  Try Again
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function CallbackLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  )
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={<CallbackLoading />}>
      <GoogleCallbackContent />
    </Suspense>
  )
}

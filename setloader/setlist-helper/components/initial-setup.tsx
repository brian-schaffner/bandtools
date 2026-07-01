"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FileUploadZone } from "@/components/file-upload-zone"
import { CheckCircle2, Database, AlertCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { apiService, type UserStatus } from "@/lib/api"

export function InitialSetup() {
  const [backupFile, setBackupFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [setupComplete, setSetupComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [userStatus, setUserStatus] = useState<UserStatus | null>(null)

  useEffect(() => {
    loadUserStatus()
  }, [])

  const loadUserStatus = async () => {
    try {
      const response = await apiService.getUserStatus()
      if (response.ok && response.data) {
        setUserStatus(response.data)
        setSetupComplete(response.data.backup_uploaded)
      }
    } catch (err) {
      console.error('Failed to load user status:', err)
    }
  }

  const handleBackupUpload = async (file: File) => {
    setError(null)
    setBackupFile(file)
    setIsProcessing(true)

    try {
      const response = await apiService.verifyBackup(file)
      if (response.ok && response.data) {
        setIsProcessing(false)
        setSetupComplete(true)
        await loadUserStatus() // Refresh user status
      } else {
        setError(response.error || 'Failed to verify backup file')
        setIsProcessing(false)
        setBackupFile(null)
      }
    } catch (err) {
      setError('Network error: Failed to verify backup file')
      setIsProcessing(false)
      setBackupFile(null)
    }
  }

  const handleReset = () => {
    setBackupFile(null)
    setSetupComplete(false)
    setError(null)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Initial Setup</CardTitle>
        <CardDescription>Upload your Song Book Pro database backup to enable set list conversion</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Alert>
          <Database className="h-4 w-4" />
          <AlertDescription>
            This backup file contains your complete song database and is required for the app to match set list songs
            with your Song Book Pro library.
          </AlertDescription>
        </Alert>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-4">
          <div>
            <h3 className="mb-2 text-lg font-semibold text-foreground">Upload Your Database Backup</h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Export a backup from Song Book Pro and upload it here. This only needs to be done once, or when you want
              to update your song database.
            </p>
            <FileUploadZone
              onFileSelect={handleBackupUpload}
              accept=".backup,.sbp,.zip,.sbpbackup"
              label="Drop your Song Book Pro backup here"
              disabled={setupComplete || isProcessing}
            />
          </div>

          {isProcessing && (
            <div className="flex items-center gap-2 rounded-lg bg-muted p-4">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span className="text-sm font-medium text-foreground">Processing your backup file...</span>
            </div>
          )}

          {setupComplete && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 rounded-lg bg-primary/10 p-4 text-primary">
                <CheckCircle2 className="h-5 w-5" />
                <div className="flex-1">
                  <p className="font-semibold">Setup Complete!</p>
                  <p className="text-sm">Your song database has been successfully imported.</p>
                </div>
              </div>
              <Button variant="outline" onClick={handleReset}>
                Upload New Backup
              </Button>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h4 className="mb-2 font-semibold text-foreground">How to export from Song Book Pro:</h4>
          <ol className="space-y-1 text-sm text-muted-foreground">
            <li>1. Open Song Book Pro on your device</li>
            <li>2. Go to Settings → Backup & Restore</li>
            <li>3. Tap "Create Backup"</li>
            <li>4. Share or export the backup file</li>
            <li>5. Upload it here</li>
          </ol>
        </div>
      </CardContent>
    </Card>
  )
}

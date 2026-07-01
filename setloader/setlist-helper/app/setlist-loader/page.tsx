"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Music2, FileText, Upload, Download, CheckCircle2, AlertCircle, Archive, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FileUploadZone } from "@/components/file-upload-zone"

import { SongTitleMapping } from "@/components/song-title-mapping"
import CatalogBasedMapping from "@/components/catalog-based-mapping"
import { ProcessingStatus } from "@/components/processing-status"
import ArchiveManager from "@/components/archive-manager"
import { GoogleAuth } from "@/components/google-auth"
import { StepByStepProcessor } from "@/components/step-by-step-processor"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { apiService, type UserStatus } from "@/lib/api"

export default function SetlistLoaderPage() {
  const [activeTab, setActiveTab] = useState("upload")
  const [backupUploaded, setBackupUploaded] = useState(false)
  const [backupAcknowledged, setBackupAcknowledged] = useState(false)
  const [setListUploaded, setSetListUploaded] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [downloadReady, setDownloadReady] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [downloadStageActive, setDownloadStageActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processingStages, setProcessingStages] = useState<Array<{
    id: string;
    name: string;
    status: 'pending' | 'running' | 'completed' | 'error';
    message?: string;
    details?: string;
    duration?: number;
  }>>([])
  const [userStatus, setUserStatus] = useState<UserStatus | null>(null)
  const [songCount, setSongCount] = useState<number>(0)
  const [processingResults, setProcessingResults] = useState<{
    songCount: number;
    successfulMappings: number;
    unfoundTitles: string[];
    allTitles: string[];
  } | null>(null)
  const [prefillMappingTitle, setPrefillMappingTitle] = useState<string | undefined>(undefined)
  const [userCatalog, setUserCatalog] = useState<string[]>([])
  const [catalogSongs, setCatalogSongs] = useState<Array<{id: number, name: string}>>([])
  const [userMappings, setUserMappings] = useState<Record<string, string>>({})
  const [selectedSetListFile, setSelectedSetListFile] = useState<File | null>(null)
  const [mappingsUpdated, setMappingsUpdated] = useState(false)

  // Load user status on component mount
  useEffect(() => {
    loadUserStatus()
  }, [])

  // Debug userCatalog state changes
  useEffect(() => {
    console.log('userCatalog state changed:', userCatalog?.length || 0, 'songs')
  }, [userCatalog])

  const loadUserStatus = async () => {
    try {
      console.log('Loading user status...')
      const response = await apiService.getUserStatus()
      console.log('User status response:', response)
      if (response.ok && response.data) {
        setUserStatus(response.data)
        setBackupUploaded(response.data.backup_uploaded)
        setBackupAcknowledged(response.data.backup_uploaded)
        setSongCount(response.data.song_count)
        console.log('User status loaded:', response.data)
        console.log('Backup uploaded:', response.data.backup_uploaded)
        console.log('Backup acknowledged set to:', response.data.backup_uploaded)
        
        // If backup is uploaded, also load the catalog
        if (response.data.backup_uploaded) {
          console.log('Backup is uploaded, loading catalog...')
          await loadUserCatalog()
        }
      } else {
        console.error('Failed to load user status:', response.error)
      }
    } catch (err) {
      console.error('Failed to load user status:', err)
    }
  }

  const handleBackupUpload = async (file: File) => {
    setError(null)
    setBackupUploaded(true)
    setProcessing(true)

    try {
      const response = await apiService.verifyBackup(file)
      if (response.ok && response.data) {
      setBackupAcknowledged(true)
        setProcessing(false)
        setSongCount(response.data.song_count || 0)
        
        // Check for empty content warnings
        if (response.data.empty_content_info && response.data.empty_content_info.empty_count > 0) {
          const emptySongs = response.data.empty_content_info.empty_songs.slice(0, 5)
          const emptySongNames = emptySongs.map((song: any) => song.name).join(', ')
          const warningMessage = `${response.data.empty_content_info.empty_count} songs have empty content (${emptySongNames}${response.data.empty_content_info.empty_count > 5 ? ' and more' : ''}). These may cause issues in Song Book Pro.`
          setError(warningMessage)
        }
        
        await loadUserStatus() // Refresh user status
        await loadUserCatalog() // Load catalog for quick picks
      } else {
        setError(response.error || 'Failed to verify backup file')
        setBackupUploaded(false)
        setProcessing(false)
      }
    } catch (err) {
      setError('Network error: Failed to verify backup file')
      setBackupUploaded(false)
      setProcessing(false)
    }
  }

  const loadUserCatalog = async () => {
    try {
      console.log('Loading user catalog...')
      const response = await apiService.getUserCatalog()
      console.log('Catalog response:', response)
      if (response.ok && response.data) {
        setUserCatalog(response.data.catalog)
        console.log(`Catalog loaded: ${response.data.catalog?.length || 0} songs`)
        
        // Also load catalog songs and mappings for the new mapping UI
        await loadCatalogSongs()
        await loadUserMappings()
      } else {
        console.error('Failed to load catalog:', response.error)
      }
    } catch (err) {
      console.error('Failed to load user catalog:', err)
    }
  }

  const loadCatalogSongs = async () => {
    try {
      console.log('Loading catalog songs...')
      const response = await apiService.getUserCatalog()
      if (response.ok && response.data) {
        const titles = response.data.catalog || []
        const songsArr = (titles as any[]).map((t, idx) => typeof t === 'string' ? ({ id: idx, name: t }) : ({ id: t.id ?? idx, name: t.name ?? '' }))
        setCatalogSongs(songsArr)
        console.log(`Catalog songs loaded: ${songsArr.length} songs`)
      }
    } catch (err) {
      console.error('Failed to load catalog songs:', err)
    }
  }

  const loadUserMappings = async () => {
    try {
      console.log('Loading user mappings...')
      const response = await apiService.getTitleMappings()
      if (response.ok && response.data) {
        setUserMappings(response.data.mappings || response.data)
        console.log(`User mappings loaded: ${Object.keys(response.data.mappings || response.data).length} mappings`)
      }
    } catch (err) {
      console.error('Failed to load user mappings:', err)
    }
  }

  const getQuickPickSuggestions = (title: string): string[] => {
    console.log(`Getting quick picks for "${title}" - catalog length: ${userCatalog.length}`)
    if (userCatalog.length === 0) {
      console.log('No user catalog available for quick picks')
      return []
    }
    
    console.log(`Generating quick picks for "${title}" from ${userCatalog.length} songs`)
    
    // Normalize function to handle punctuation differences
    const normalize = (str: string): string => {
      return str.toLowerCase()
        .replace(/[''`]/g, '') // Remove apostrophes and similar characters
        .replace(/[&]/g, 'and') // Replace & with 'and'
        .replace(/[^a-z0-9\s]/g, '') // Remove other punctuation
        .replace(/\s+/g, ' ') // Normalize whitespace
        .trim()
    }
    
    const normalizedTitle = normalize(title)
    const titleWords = normalizedTitle.split(/\s+/).filter(word => word.length > 2)
    const suggestions: { song: string; score: number }[] = []
    
    for (const song of userCatalog) {
      let score = 0
      const songLower = song.toLowerCase()
      const normalizedSong = normalize(song)
      
      // Exact match gets highest score
      if (songLower.includes(title.toLowerCase())) {
        score += 100
      }
      
      // Normalized exact match gets very high score
      if (normalizedSong.includes(normalizedTitle)) {
        score += 90
      }
      
      // Word matches (original)
      for (const word of titleWords) {
        if (songLower.includes(word)) {
          score += 10
        }
      }
      
      // Normalized word matches
      const songWords = normalizedSong.split(/\s+/)
      for (const word of titleWords) {
        for (const songWord of songWords) {
          if (songWord.includes(word) || word.includes(songWord)) {
            score += 8
          }
        }
      }
      
      // Partial word matches
      for (const word of titleWords) {
        if (word.length > 3) {
          const partial = word.substring(0, 3)
          if (songLower.includes(partial)) {
            score += 3
          }
        }
      }
      
      if (score > 0) {
        suggestions.push({ song, score })
      }
    }
    
    // Sort by score and return top 3
    const results = suggestions
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map(s => s.song)
    
    console.log(`Quick pick results for "${title}":`, results)
    return results
  }

  const handleMappingComplete = (downloadUrl: string) => {
    setDownloadUrl(downloadUrl)
    setActiveTab('upload')
    setPrefillMappingTitle(undefined)
    // Refresh user status to get updated processing results
    loadUserStatus()
  }

  const handleMappingUpdate = async (newMappings: Record<string, string>) => {
    try {
      console.log('Updating mappings:', Object.keys(newMappings).length, 'mappings')
      const response = await apiService.saveTitleMappings(newMappings)
      if (response.ok) {
        setUserMappings(newMappings)
        console.log('Mappings updated successfully')
        
        // Refresh user status to get updated validation results
        await loadUserStatus()
        
        // Signal that mappings have been updated
        setMappingsUpdated(true)
        
        // Reset the flag after a short delay
        setTimeout(() => {
          setMappingsUpdated(false)
        }, 100)
        
        // Reprocess setlist if there's a download ready
        if (downloadReady && selectedSetListFile) {
          console.log('Reprocessing setlist with updated mappings...')
          // Re-run the entire processing pipeline with updated mappings
          setProcessing(true)
          setDownloadReady(false)
          setDownloadUrl(null)
          
          // The StepByStepProcessor will automatically re-run with the updated mappings
          // since the mappings are now saved to the backend
        }
      } else {
        console.error('Failed to update mappings:', response.error)
      }
    } catch (err) {
      console.error('Failed to update mappings:', err)
    }
  }

  const handleQuickMapping = async (userTitle: string, actualTitle: string) => {
    try {
      console.log('Creating quick mapping:', userTitle, '->', actualTitle)
      
      // Get current mappings
      const response = await apiService.getTitleMappings()
      if (response.ok && response.data) {
        const currentMappings = response.data.mappings || {}
        
        // Add new mapping
        const newMappings = {
          ...currentMappings,
          [userTitle.toLowerCase().trim()]: actualTitle
        }
        
        // Save mappings
        const saveResponse = await apiService.saveTitleMappings(newMappings)
        if (saveResponse.ok) {
          console.log('Quick mapping saved successfully')
          
          // Refresh user status to get updated validation results
          await loadUserStatus()
          
          // Signal that mappings have been updated
          setMappingsUpdated(true)
          
          // Reset the flag after a short delay
          setTimeout(() => {
            setMappingsUpdated(false)
          }, 100)
          
          // Reprocess the setlist with updated mappings
          console.log('Reprocessing setlist with updated mappings...')
          // Re-run the entire processing pipeline with updated mappings
          if (downloadReady && selectedSetListFile) {
            setProcessing(true)
            setDownloadReady(false)
            setDownloadUrl(null)
            
            // The StepByStepProcessor will automatically re-run with the updated mappings
            // since the mappings are now saved to the backend
          }
        } else {
          console.error('Failed to save quick mapping:', saveResponse.error)
        }
      }
    } catch (err) {
      console.error('Failed to create quick mapping:', err)
    }
  }

  const handleSetListUpload = async (file: File) => {
    setError(null)
    setSetListUploaded(true)
    setSelectedSetListFile(file)
    console.log('Setlist file selected:', file.name)

    // File is now selected and ready for step-by-step processing
  }

  const handleDownload = async () => {
    if (downloadUrl) {
      // Extract file ID from the download URL
      const fileId = downloadUrl.split('/').pop()
      if (fileId) {
        try {
          // Use the API service to get the authenticated download URL
          const authenticatedUrl = await apiService.downloadFile(fileId)
          window.open(authenticatedUrl, '_blank')
        } catch (error) {
          console.error('Failed to get download URL:', error)
          // Fallback to original URL
          window.open(downloadUrl, '_blank')
        }
      }
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" />
                Band Tools
              </Link>
              <div className="hidden h-6 w-px bg-border sm:block" />
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
                  <Music2 className="h-6 w-6 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground">Setlist Loader</h1>
                  <p className="text-sm text-muted-foreground">
                    {userStatus?.user_email ? `${userStatus.user_email} • ${songCount} songs in backup` : `Guest session • ${songCount} songs in backup`}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {userStatus?.latest_backup && (
                <div className="text-right text-sm text-muted-foreground">
                  <div>Latest backup: {userStatus.latest_backup.filename}</div>
                  <div>{new Date(userStatus.latest_backup.uploaded_at).toLocaleDateString()}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Google Auth - show for both authenticated and non-authenticated users */}
      <div className="container mx-auto px-4 py-4">
        <GoogleAuth onAuthChange={(isAuthenticated, user) => {
          console.log('Auth status changed:', isAuthenticated, user)
          // Reload the page to refresh user status
          if (isAuthenticated) {
            window.location.reload()
          }
        }} />
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full max-w-lg grid-cols-3">
            <TabsTrigger value="upload" className="gap-2">
              <Upload className="h-4 w-4" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="mapping" className="gap-2">
              <FileText className="h-4 w-4" />
              Song Mapping
            </TabsTrigger>
            <TabsTrigger value="archive" className="gap-2">
              <Archive className="h-4 w-4" />
              Archive
            </TabsTrigger>
          </TabsList>

          {/* Upload Tab */}
          <TabsContent value="upload" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl">Convert Your Set List</CardTitle>
                <CardDescription>
                  Follow these steps to convert your set list into a Song Book Pro backup file
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Error Display */}
                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}

                {/* Step 1: Upload Backup */}
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                      1
                    </div>
                    <div className="flex-1 space-y-3">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Upload Recent Backup File</h3>
                        <p className="text-sm text-muted-foreground">
                          Upload your most recent Song Book Pro backup file to ensure we have your latest song database
                        </p>
                      </div>
                      
                      {userStatus?.latest_backup ? (
                        <div className="space-y-3">
                          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                            <div className="flex items-center gap-2 text-green-800">
                              <CheckCircle2 className="h-5 w-5" />
                              <span className="font-medium">Backup already uploaded</span>
                            </div>
                            <div className="mt-2 text-sm text-green-700">
                              <div><strong>File:</strong> {userStatus.latest_backup.filename}</div>
                              <div><strong>Uploaded:</strong> {new Date(userStatus.latest_backup.uploaded_at).toLocaleString()}</div>
                              <div><strong>Songs found:</strong> {userStatus.latest_backup.song_count}</div>
                              {userStatus.latest_backup.empty_content_info && userStatus.latest_backup.empty_content_info.empty_count > 0 && (
                                <div className="mt-2 text-amber-700">
                                  <div className="flex items-center gap-1">
                                    <AlertCircle className="h-4 w-4" />
                                    <strong>Warning:</strong> {userStatus.latest_backup.empty_content_info.empty_count} songs have empty content
                                  </div>
                                  <div className="ml-5 text-xs">
                                    {userStatus.latest_backup.empty_content_info.empty_songs.slice(0, 3).map((song: any) => song.name).join(', ')}
                                    {userStatus.latest_backup.empty_content_info.empty_count > 3 && ' and more...'}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            You can upload a new backup file to replace the current one.
                          </div>
                        </div>
                      ) : null}
                      
                      <FileUploadZone
                        onFileSelect={handleBackupUpload}
                        accept=".backup,.sbp,.zip,.sbpbackup"
                        label={userStatus?.latest_backup ? "Drop a new backup file here or click to browse" : "Drop your backup file here or click to browse"}
                        disabled={processing}
                      />
                      {processing && !backupAcknowledged && (
                        <div className="flex items-center gap-2 rounded-lg bg-muted p-3 text-sm">
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                          <span className="font-medium">Verifying backup file...</span>
                        </div>
                      )}
                      {backupAcknowledged && !userStatus?.latest_backup && (
                        <div className="flex items-center gap-2 rounded-lg bg-primary/10 p-3 text-sm text-primary">
                          <CheckCircle2 className="h-5 w-5" />
                          <span className="font-medium">Backup file verified successfully</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Step 2: Upload Set List */}
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                      2
                    </div>
                    <div className="flex-1 space-y-3">
                      <div>
                        <h3 className="text-lg font-semibold text-foreground">Upload Your Set List</h3>
                        <p className="text-sm text-muted-foreground">
                          Upload a PDF, image, or text file containing your set list
                        </p>
                        {!backupAcknowledged && (
                          <Alert className="mt-2">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>
                              You must upload a backup file first before processing set lists.
                            </AlertDescription>
                          </Alert>
                        )}
                      </div>
                      <FileUploadZone
                        onFileSelect={handleSetListUpload}
                        accept=".pdf,.png,.jpg,.jpeg,.txt"
                        label="Drop your set list here or click to browse"
                        disabled={!backupAcknowledged || downloadReady || processing}
                      />
                      {selectedSetListFile && (
                        <StepByStepProcessor 
                          key={selectedSetListFile?.name}
                          setlistFile={selectedSetListFile}
                          mappingsUpdated={mappingsUpdated}
                          onComplete={(result) => {
                            console.log('Processing complete callback triggered:', result)
                            if (result.downloadId) {
                              console.log('Setting download URL:', result.downloadId)
                              // Set the download URL using the download ID
                              const downloadUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002'}/download_file/${result.downloadId}`
                              setDownloadUrl(downloadUrl)
                              setDownloadReady(true)
                              setProcessing(false)
                              console.log('Download state updated - ready:', true, 'url:', downloadUrl)
                            } else {
                              console.log('No downloadId in result:', result)
                            }
                          }}
                          onProcessingChange={(isProcessing) => {
                            console.log('StepByStepProcessor processing state changed:', isProcessing)
                            setProcessing(isProcessing)
                          }}
                          onStageChange={(stageId, status) => {
                            console.log('Stage changed:', stageId, status)
                            if (stageId === 'download') {
                              setDownloadStageActive(status === 'running' || status === 'completed')
                            }
                          }}
                        />
                      )}
                    </div>
                  </div>
                </div>

                {/* Step 3: Processing Results */}
                {processingResults && (
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                        3
                      </div>
                      <div className="flex-1 space-y-3">
                        <div>
                          <h3 className="text-lg font-semibold text-foreground">Processing Results</h3>
                          <p className="text-sm text-muted-foreground">
                            Your set list has been processed and analyzed
                          </p>
                        </div>
                        
                        {/* Processing Summary */}
                        <div className="grid gap-4 md:grid-cols-3">
                          <div className="rounded-lg border border-border bg-card p-4">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-2 rounded-full bg-green-500" />
                              <span className="text-sm font-medium text-foreground">Songs Found</span>
                            </div>
                            <p className="text-2xl font-bold text-foreground">{processingResults.songCount}</p>
                          </div>
                          
                          <div className="rounded-lg border border-border bg-card p-4">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-2 rounded-full bg-blue-500" />
                              <span className="text-sm font-medium text-foreground">Successfully Mapped</span>
                            </div>
                            <p className="text-2xl font-bold text-foreground">{processingResults.successfulMappings}</p>
                          </div>
                          
                          <div className="rounded-lg border border-border bg-card p-4">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-2 rounded-full bg-orange-500" />
                              <span className="text-sm font-medium text-foreground">Need Mapping</span>
                            </div>
                            <p className="text-2xl font-bold text-foreground">{processingResults.unfoundTitles.length}</p>
                          </div>
                        </div>

                        {/* Unfound Titles */}
                        {console.log('Checking unfound titles:', processingResults.unfoundTitles, 'Length:', processingResults.unfoundTitles.length)}
                        {processingResults.unfoundTitles.length > 0 && (
                          <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                            <div className="flex items-center gap-2 mb-3">
                              <AlertCircle className="h-5 w-5 text-orange-600" />
                              <h4 className="font-medium text-orange-800">Titles That Need Mapping</h4>
                            </div>
                            <div className="space-y-3">
                              {processingResults.unfoundTitles.map((title, index) => (
                                <div key={index} className="rounded bg-white p-3">
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium text-orange-700">{title}</span>
                                    <Button 
                                      size="sm" 
                                      variant="outline" 
                                      className="text-orange-600 border-orange-300 hover:bg-orange-100"
                                      onClick={() => {
                                        console.log('Map Title button clicked for:', title);
                                        // Set the title to prefill and switch to mapping tab
                                        setPrefillMappingTitle(title);
                                        console.log('Set prefill title to:', title);
                                        setActiveTab('mapping');
                                        console.log('Switched to mapping tab');
                                      }}
                                    >
                                      Map Title
                                    </Button>
                                  </div>
                                  {/* Quick Pick Suggestions */}
                                  <div className="space-y-1">
                                    <p className="text-xs text-orange-600 font-medium">Quick Pick Suggestions:</p>
                                    {userCatalog.length > 0 ? (
                                      <div className="flex flex-wrap gap-1">
                                        {getQuickPickSuggestions(title).map((suggestion, suggestionIndex) => (
                                          <Button
                                            key={suggestionIndex}
                                            size="sm"
                                            variant="secondary"
                                            className="text-xs h-6 px-2 bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
                                            onClick={() => {
                                              console.log('Quick pick selected:', title, '->', suggestion);
                                              handleQuickMapping(title, suggestion);
                                            }}
                                          >
                                            {suggestion}
                                          </Button>
                                        ))}
                                      </div>
                                    ) : (
                                      <p className="text-xs text-orange-500 italic">
                                        Upload a backup file to enable quick pick suggestions
                                      </p>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                            <p className="mt-3 text-sm text-orange-700">
                              Click "Map Title" for full mapping options, or use Quick Pick suggestions for common matches.
                            </p>
                          </div>
                        )}

                        {/* Success Message */}
                        {processingResults.unfoundTitles.length === 0 && (
                          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-4">
                            <CheckCircle2 className="h-5 w-5 text-green-600" />
                            <div className="flex-1">
                              <p className="font-medium text-green-800">All Titles Successfully Mapped!</p>
                              <p className="text-sm text-green-700">All {processingResults.songCount} songs were found in your catalog</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Step 4: Download */}
                {downloadStageActive && downloadReady && (
                  <div className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                        {processingResults ? '4' : '3'}
                      </div>
                      <div className="flex-1 space-y-3">
                        <div>
                          <h3 className="text-lg font-semibold text-foreground">Download Your Processed Setlist</h3>
                          <p className="text-sm text-muted-foreground">
                            Your processed setlist file is ready to download
                          </p>
                        </div>
                        <Button onClick={handleDownload} size="lg" className="gap-2">
                          <Download className="h-5 w-5" />
                          Download Processed Setlist
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>



          {/* Song Title Mapping Tab */}
          <TabsContent value="mapping">
            {catalogSongs.length > 0 ? (
              <>
                {console.log('Rendering CatalogBasedMapping with:', {
                  catalogSongs: catalogSongs.length,
                  userMappings: Object.keys(userMappings).length
                })}
                <CatalogBasedMapping
                  userCatalog={catalogSongs}
                  userMappings={userMappings}
                  onMappingUpdate={handleMappingUpdate}
                  onMappingComplete={handleMappingComplete}
                />
              </>
            ) : (
              <div className="text-center py-8">
                <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Catalog Available</h3>
                <p className="text-muted-foreground">
                  Please upload a backup file first to access the song mapping interface.
                </p>
              </div>
            )}
          </TabsContent>

          {/* Archive Tab */}
          <TabsContent value="archive">
            <ArchiveManager />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}


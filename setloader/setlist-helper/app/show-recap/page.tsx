"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { 
  Music2, 
  Upload, 
  Download, 
  CheckCircle2, 
  AlertCircle, 
  Clock,
  Loader2,
  FileAudio,
  Scissors,
  ArrowLeft,
  RefreshCw,
  Play,
  Trash2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Slider } from "@/components/ui/slider"
import { getApiBaseUrl } from "@/lib/api"

interface SetInfo {
  set_number: number
  start_time: number
  end_time: number
  duration: number
}

interface JobStatus {
  job_id: string
  status: string
  message: string
  progress: number
  created_at: string
  updated_at: string
  show_name?: string
  show_date?: string
  analysis?: {
    total_duration: number
    sets: SetInfo[]
    silence_regions?: Array<{ start: number; end: number; duration: number }>
  }
  output_files: string[]
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default function ShowRecapPage() {
  const [files, setFiles] = useState<File[]>([])
  const [showName, setShowName] = useState("")
  const [showDate, setShowDate] = useState(new Date().toISOString().split('T')[0])
  const [silenceThreshold, setSilenceThreshold] = useState(-40)
  const [minSilenceDuration, setMinSilenceDuration] = useState(10)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentJob, setCurrentJob] = useState<JobStatus | null>(null)
  const [jobs, setJobs] = useState<JobStatus[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  const apiBase = getApiBaseUrl().replace('/api', '/show-recap')

  const loadJobs = useCallback(async () => {
    try {
      const response = await fetch(`${apiBase}/jobs`)
      if (response.ok) {
        const data = await response.json()
        setJobs(data)
      }
    } catch (err) {
      console.error('Failed to load jobs:', err)
    }
  }, [apiBase])

  const loadJobStatus = useCallback(async (jobId: string) => {
    try {
      const response = await fetch(`${apiBase}/jobs/${jobId}`)
      if (response.ok) {
        const data = await response.json()
        setCurrentJob(data)
        return data
      }
    } catch (err) {
      console.error('Failed to load job status:', err)
    }
    return null
  }, [apiBase])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  useEffect(() => {
    if (currentJob && ['pending', 'analyzing', 'processing'].includes(currentJob.status)) {
      const interval = setInterval(async () => {
        const updated = await loadJobStatus(currentJob.job_id)
        if (updated && ['complete', 'error'].includes(updated.status)) {
          loadJobs()
        }
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [currentJob, loadJobStatus, loadJobs])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
      setError(null)
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setError("Please select at least one audio file")
      return
    }
    if (!showName.trim()) {
      setError("Please enter a show name")
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      files.forEach(file => formData.append('files', file))
      formData.append('show_name', showName)
      formData.append('show_date', showDate)
      formData.append('silence_threshold_db', silenceThreshold.toString())
      formData.append('min_silence_duration', minSilenceDuration.toString())

      const response = await fetch(`${apiBase}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await response.json()
      setCurrentJob({
        job_id: data.job_id,
        status: 'pending',
        message: data.message,
        progress: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        output_files: [],
      })
      
      setFiles([])
      setShowName("")
      loadJobs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'complete':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-500" />
      case 'analyzing':
      case 'processing':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
      default:
        return <Clock className="h-5 w-5 text-gray-400" />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="mb-6">
          <Link href="/" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Band Tools
          </Link>
        </div>

        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-purple-100 mb-4">
            <Scissors className="h-8 w-8 text-purple-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Show Recap</h1>
          <p className="text-gray-600 mt-2">
            Upload your multitrack recording and automatically split it into sets
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Upload Recording
              </CardTitle>
              <CardDescription>
                Upload WAV files from your A&H Qu-16 or other multitrack recorder
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="showName">Show Name</Label>
                  <Input
                    id="showName"
                    placeholder="e.g., Friday Night at The Venue"
                    value={showName}
                    onChange={(e) => setShowName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="showDate">Show Date</Label>
                  <Input
                    id="showDate"
                    type="date"
                    value={showDate}
                    onChange={(e) => setShowDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="files">Audio Files</Label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-purple-400 transition-colors">
                  <input
                    id="files"
                    type="file"
                    multiple
                    accept="audio/*,.wav,.mp3,.aiff,.flac"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <label htmlFor="files" className="cursor-pointer">
                    <FileAudio className="h-10 w-10 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600">
                      {files.length > 0 
                        ? `${files.length} file(s) selected: ${files.map(f => f.name).join(', ')}`
                        : 'Click to select audio files or drag and drop'}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      Supports WAV, MP3, AIFF, FLAC
                    </p>
                  </label>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-sm text-purple-600 hover:text-purple-700"
                >
                  {showAdvanced ? '▼ Hide' : '▶ Show'} Advanced Settings
                </button>
              </div>

              {showAdvanced && (
                <div className="space-y-4 pt-2 border-t">
                  <div className="space-y-2">
                    <Label>Silence Threshold: {silenceThreshold} dB</Label>
                    <Slider
                      value={[silenceThreshold]}
                      onValueChange={(v) => setSilenceThreshold(v[0])}
                      min={-60}
                      max={-20}
                      step={1}
                    />
                    <p className="text-xs text-gray-500">
                      Audio below this level is considered silence. Lower = more sensitive.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Minimum Break Duration: {minSilenceDuration} seconds</Label>
                    <Slider
                      value={[minSilenceDuration]}
                      onValueChange={(v) => setMinSilenceDuration(v[0])}
                      min={5}
                      max={60}
                      step={1}
                    />
                    <p className="text-xs text-gray-500">
                      Silence must last this long to be detected as a set break.
                    </p>
                  </div>
                </div>
              )}

              <Button 
                onClick={handleUpload} 
                disabled={uploading || files.length === 0}
                className="w-full"
              >
                {uploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload and Process
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {currentJob && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {getStatusIcon(currentJob.status)}
                  Current Job
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{currentJob.message}</span>
                  <span className="font-medium">{currentJob.status}</span>
                </div>
                <Progress value={currentJob.progress} />
                
                {currentJob.analysis && currentJob.analysis.sets.length > 0 && (
                  <div className="space-y-2 pt-4 border-t">
                    <h4 className="font-medium">Detected Sets</h4>
                    <div className="space-y-2">
                      {currentJob.analysis.sets.map((set) => (
                        <div 
                          key={set.set_number}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                        >
                          <div>
                            <span className="font-medium">Set {set.set_number}</span>
                            <span className="text-sm text-gray-500 ml-2">
                              {formatTimestamp(set.start_time)} - {formatTimestamp(set.end_time)}
                            </span>
                          </div>
                          <span className="text-sm text-gray-600">
                            {formatDuration(set.duration)}
                          </span>
                        </div>
                      ))}
                    </div>
                    {currentJob.analysis.total_duration && (
                      <p className="text-sm text-gray-500">
                        Total recording: {formatDuration(currentJob.analysis.total_duration)}
                      </p>
                    )}
                  </div>
                )}

                {currentJob.output_files.length > 0 && (
                  <div className="space-y-2 pt-4 border-t">
                    <h4 className="font-medium flex items-center gap-2">
                      <Download className="h-4 w-4" />
                      Download Sets
                    </h4>
                    <div className="space-y-2">
                      {currentJob.output_files.map((file) => (
                        <a
                          key={file}
                          href={`${apiBase}/jobs/${currentJob.job_id}/download/${file}`}
                          className="flex items-center justify-between p-3 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
                          download
                        >
                          <span className="flex items-center gap-2">
                            <Music2 className="h-4 w-4 text-green-600" />
                            {file}
                          </span>
                          <Download className="h-4 w-4 text-green-600" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {jobs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Clock className="h-5 w-5" />
                    Recent Jobs
                  </span>
                  <Button variant="ghost" size="sm" onClick={loadJobs}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {jobs.slice(0, 10).map((job) => (
                    <button
                      key={job.job_id}
                      onClick={() => loadJobStatus(job.job_id)}
                      className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors text-left"
                    >
                      <div className="flex items-center gap-3">
                        {getStatusIcon(job.status)}
                        <div>
                          <p className="font-medium">{job.show_name || job.job_id}</p>
                          <p className="text-sm text-gray-500">{job.show_date}</p>
                        </div>
                      </div>
                      <span className="text-sm text-gray-500">
                        {new Date(job.created_at).toLocaleDateString()}
                      </span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

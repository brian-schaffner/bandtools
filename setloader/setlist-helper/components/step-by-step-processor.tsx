"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { 
  FileText, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Play, 
  Pause, 
  RotateCcw,
  Download,
  Eye,
  Loader2
} from "lucide-react"
import CatalogBasedMapping from "./catalog-based-mapping"
import { TitleValidationComponent } from "./shared/TitleValidationComponent"
import { apiService, API_SECRET, getApiBaseUrl } from "@/lib/api"
import { GigNameField } from "@/components/gig-name-field"

interface ProcessingStage {
  id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  result?: any
  error?: string
  duration?: number
}

interface StepByStepProcessorProps {
  setlistFile: File | null
  onComplete?: (result: any) => void
  onProcessingChange?: (isProcessing: boolean) => void
  onStageChange?: (stageId: string, status: string) => void
  mappingsUpdated?: boolean  // Signal when mappings are updated
}

export function StepByStepProcessor({ setlistFile, onComplete, onProcessingChange, onStageChange, mappingsUpdated }: StepByStepProcessorProps) {
  const [stages, setStages] = useState<ProcessingStage[]>([
    {
      id: 'pdf_extraction',
      name: 'PDF Extraction',
      description: 'Extract song titles from PDF using AI',
      status: 'pending'
    },
    {
      id: 'title_validation',
      name: 'Title Validation',
      description: 'Match extracted titles to your song catalog',
      status: 'pending'
    },
    {
      id: 'song_extraction',
      name: 'Song Extraction',
      description: 'Create SBP file with matched songs',
      status: 'pending'
    },
    {
      id: 'download',
      name: 'Download',
      description: 'Download your processed setlist file',
      status: 'pending'
    }
  ])

  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [overallProgress, setOverallProgress] = useState(0)
  const [finalResult, setFinalResult] = useState<any>(null)
  const [authStatus, setAuthStatus] = useState<{authenticated: boolean, backupUploaded: boolean} | null>(null)
  const [showMappingInterface, setShowMappingInterface] = useState(false)
  const [userCatalog, setUserCatalog] = useState<any[]>([])
  const [userMappings, setUserMappings] = useState<Record<string, string>>({})
  const [quickPicks, setQuickPicks] = useState<Record<string, string[]>>({})
  const stagedValidationDataRef = useRef<any>(null)
  const pdfResultRef = useRef<any>(null)
  const stagesRef = useRef(stages)
  const processingLockRef = useRef(false)
  const autoFlowActiveRef = useRef(false)
  const autoContinueTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [outputBaseName, setOutputBaseName] = useState("")
  const [pdfFallbackName, setPdfFallbackName] = useState("")
  const [autoFlowActive, setAutoFlowActive] = useState(false)

  useEffect(() => {
    stagesRef.current = stages
  }, [stages])

  const isFullyValidated = (validationData: any): boolean => {
    if (!validationData) return false
    const counts = validationData.counts || {}
    if ((counts.missing_total || 0) > 0) return false
    if (counts.total > 0 && (counts.validated_total || 0) < counts.total) return false

    for (const set of validationData.sets || []) {
      for (const song of set.songs || []) {
        if (!song.validated) return false
      }
    }
    for (const song of validationData.extras || []) {
      if (!song.validated) return false
    }
    return true
  }

  useEffect(() => {
    autoFlowActiveRef.current = autoFlowActive
  }, [autoFlowActive])

  const scheduleAutoContinue = () => {
    if (!autoFlowActiveRef.current) return
    if (autoContinueTimerRef.current) {
      clearTimeout(autoContinueTimerRef.current)
    }
    autoContinueTimerRef.current = setTimeout(() => {
      autoContinueTimerRef.current = null
      startNextStage()
    }, 200)
  }

  const startPipeline = () => {
    if (processingLockRef.current || isProcessing) return
    const nextStage = stagesRef.current.find((stage) => stage.status === 'pending')
    if (!nextStage) return
    autoFlowActiveRef.current = true
    setAutoFlowActive(true)
    startNextStage()
  }

  const openFullMapper = async () => {
    try {
      const [catalogResponse, mappingsResponse] = await Promise.all([
        apiService.getUserCatalog(),
        apiService.getUserTitleMappings?.() ?? apiService.getTitleMappings()
      ])
      if (catalogResponse.ok && catalogResponse.data) {
        setUserCatalog(catalogResponse.data.catalog || [])
      }
      if (mappingsResponse.ok && mappingsResponse.data) {
        setUserMappings(mappingsResponse.data.mappings || {})
      }
    } catch (e) {
      console.warn('Failed to load catalog/mappings for mapper:', e)
    } finally {
      setShowMappingInterface(true)
    }
  }

  // Generate quick pick suggestions for a single title from the user's catalog
  const generateQuickPicksForTitle = (title: string, catalog: any[]): string[] => {
    if (!title || !catalog || catalog.length === 0) return []
    const catalogTitles: string[] = catalog.map((c: any) => typeof c === 'string' ? c : (c?.name || ''))
    const titleWords = title.toLowerCase().split(/\s+/).filter(w => w.length > 2)
    const suggestions: { song: string, score: number }[] = []

    for (const song of catalogTitles) {
      if (!song) continue
      let score = 0
      const songLower = song.toLowerCase()

      if (songLower.includes(title.toLowerCase())) {
        score += 100
      }

      for (const word of titleWords) {
        if (songLower.includes(word)) score += 10
      }

      for (const word of titleWords) {
        if (word.length > 3) {
          // simple partial scoring: prefix/suffix/substring
          if (songLower.startsWith(word)) score += 4
          if (songLower.endsWith(word)) score += 3
          if (songLower.indexOf(word.slice(0, Math.max(2, Math.floor(word.length / 2)))) >= 0) score += 2
        }
      }

      if (score > 0) suggestions.push({ song, score })
    }

    // Unique top 5 by score
    const unique: string[] = []
    for (const s of suggestions.sort((a, b) => b.score - a.score)) {
      if (!unique.includes(s.song)) unique.push(s.song)
      if (unique.length >= 5) break
    }
    return unique
  }

  // Re-run validation when mappings are updated from the catalog mapper (not inline quick-picks)
  useEffect(() => {
    if (!mappingsUpdated || processingLockRef.current) return

    const currentStages = stagesRef.current
    const validationStage = currentStages.find((s) => s.id === 'title_validation')
    const songStage = currentStages.find((s) => s.id === 'song_extraction')

    // Only refresh validation when paused before song extraction
    if (validationStage?.status !== 'completed' || songStage?.status !== 'pending') {
      return
    }

    console.log('Mappings updated, re-running title validation...')

    setTimeout(() => {
      runTitleValidation().then((result) => {
        updateStage('title_validation', {
          status: 'completed',
          result,
          duration: 0,
        })
        stagedValidationDataRef.current = result.validationData

        if (autoFlowActiveRef.current && isFullyValidated(result.validationData)) {
          scheduleAutoContinue()
          return
        }

        autoFlowActiveRef.current = false
        setAutoFlowActive(false)
        setIsProcessing(false)
        setCurrentStage(null)
        if (onProcessingChange) {
          onProcessingChange(false)
        }
        if (onStageChange) {
          onStageChange('title_validation', 'completed')
        }
      }).catch((error) => {
        updateStage('title_validation', {
          status: 'error',
          error: error.message,
          duration: 0,
        })
        autoFlowActiveRef.current = false
        setAutoFlowActive(false)
        setIsProcessing(false)
        setCurrentStage(null)
        if (onProcessingChange) {
          onProcessingChange(false)
        }
      })
    }, 100)
  }, [mappingsUpdated])

  // Reset stages when component mounts (for key changes)
  useEffect(() => {
    console.log('StepByStepProcessor component mounted, resetting stages...')
    const initialStages: ProcessingStage[] = [
      {
        id: 'pdf_extraction',
        name: 'PDF Extraction',
        description: 'Extract song titles from PDF using AI',
        status: 'pending'
      },
      {
        id: 'title_validation',
        name: 'Title Validation',
        description: 'Match extracted titles to your song catalog',
        status: 'pending'
      },
      {
        id: 'song_extraction',
        name: 'Song Extraction',
        description: 'Create SBP file with matched songs',
        status: 'pending'
      },
      {
        id: 'download',
        name: 'Download',
        description: 'Download your processed setlist file',
        status: 'pending'
      }
    ]
    stagesRef.current = initialStages
    setStages(initialStages)
    setIsProcessing(false)
  }, []) // Empty dependency array means this runs only on mount

  // Check authentication status and load data on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await apiService.getUserStatus()
        if (response.ok && response.data) {
          setAuthStatus({
            authenticated: response.data.authenticated || false,
            backupUploaded: response.data.backup_uploaded || false
          })
          
          // Load user catalog and mappings if authenticated
          if (response.data.authenticated) {
            try {
              const catalogResponse = await apiService.getUserCatalog()
              if (catalogResponse.ok && catalogResponse.data) {
                const raw = catalogResponse.data.catalog || []
                const normalized = raw.map((c: any, idx: number) => (
                  typeof c === 'string' ? { id: idx, name: c } : { id: c.id ?? idx, name: c.name ?? '' }
                ))
                setUserCatalog(normalized)
              }
              
              const mappingsResponse = await apiService.getUserTitleMappings()
              if (mappingsResponse.ok && mappingsResponse.data) {
                setUserMappings(mappingsResponse.data.mappings || {})
              }
              // Build simple quick picks by fuzzy substring search on catalog
              const titles = (catalogResponse.data?.catalog || []).map((c: any) => typeof c === 'string' ? c : c.name || '')
              const qp: Record<string, string[]> = {}
              Object.keys(mappingsResponse.data?.mappings || {}).forEach(() => {})
              // No-op; quick picks only for missing titles; computed later per title
              setQuickPicks(prev => prev) // keep stable
            } catch (error) {
              console.error('Failed to load user data:', error)
            }
          }
        }
      } catch (error) {
        console.error('Failed to check auth status:', error)
        setAuthStatus({ authenticated: false, backupUploaded: false })
      }
    }
    checkAuth()
  }, [])

  const updateStage = (stageId: string, updates: Partial<ProcessingStage>) => {
    setStages((prev) => {
      const next = prev.map((stage) =>
        stage.id === stageId ? { ...stage, ...updates } : stage
      )
      stagesRef.current = next
      return next
    })

    if (onStageChange && updates.status) {
      onStageChange(stageId, updates.status)
    }
  }

  const updateStagedValidationData = async (newValidationData: any) => {
    console.log('🔄 updateStagedValidationData called with:', newValidationData.counts)
    stagedValidationDataRef.current = newValidationData
    // Update the staged data in the title validation stage
    const validationStage = stagesRef.current.find((s) => s.id === 'title_validation')
    if (validationStage?.result) {
      console.log('🔄 Updating staged data for title_validation stage')
      updateStage('title_validation', {
        result: {
          ...validationStage.result,
          stagedData: newValidationData,
          validationData: newValidationData,
          validatedSongs: newValidationData.counts?.validated_total || 0,
          message: `Validated ${newValidationData.counts?.validated_total || 0} out of ${newValidationData.counts?.total || 0} songs`
        }
      })
    } else {
      console.warn('⚠️ No title_validation stage found or no result')
    }
  }

  const getStageStatusIcon = (status: ProcessingStage['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />
      case 'running':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-400" />
    }
  }

  const getNextPendingStage = () => {
    return stagesRef.current.find((stage) => stage.status === 'pending')
  }

  const canProceed = () => {
    const nextStage = getNextPendingStage()
    return nextStage && !processingLockRef.current && !isProcessing && authStatus?.authenticated && authStatus?.backupUploaded
  }

  const startNextStage = async () => {
    const nextStage = getNextPendingStage()
    if (!nextStage || processingLockRef.current) return

    processingLockRef.current = true
    setIsProcessing(true)
    setCurrentStage(nextStage.id)
    updateStage(nextStage.id, { status: 'running' })
    
    if (onProcessingChange) {
      onProcessingChange(true)
    }

    const startTime = Date.now()

    try {
      let result
      
      switch (nextStage.id) {
        case 'pdf_extraction':
          result = await runPDFExtraction()
          break
        case 'title_validation':
          result = await runTitleValidation()
          break
        case 'song_extraction':
          result = await runSongExtraction()
          break
        case 'download':
          result = { message: 'Download ready' }
          break
        default:
          throw new Error(`Unknown stage: ${nextStage.id}`)
      }

      const duration = Date.now() - startTime
      updateStage(nextStage.id, { 
        status: 'completed', 
        result, 
        duration 
      })

      if (nextStage.id === 'pdf_extraction') {
        pdfResultRef.current = result
      }
      if (nextStage.id === 'title_validation') {
        stagedValidationDataRef.current = result.validationData
      }

      const completedStages = stagesRef.current.filter((s) => s.status === 'completed').length
      const totalStages = stagesRef.current.length - 1
      setOverallProgress((completedStages / totalStages) * 100)

      if (nextStage.id === 'song_extraction') {
        setFinalResult(result)
        setAutoFlowActive(false)
        autoFlowActiveRef.current = false
        if (onComplete && result.downloadId) {
          onComplete({ ...result, downloadId: result.downloadId })
        }
        setTimeout(() => {
          updateStage('download', { status: 'running' })
          setCurrentStage('download')
          setTimeout(() => {
            updateStage('download', { status: 'completed' })
            setCurrentStage(null)
            processingLockRef.current = false
            setIsProcessing(false)
            if (onProcessingChange) {
              onProcessingChange(false)
            }
          }, 100)
        }, 100)
        return
      }
      
      if (autoFlowActiveRef.current && nextStage.id === 'pdf_extraction') {
        scheduleAutoContinue()
        return
      }

      if (autoFlowActiveRef.current && nextStage.id === 'title_validation') {
        if (!isFullyValidated(result.validationData)) {
          // Paused for mapping — keep auto-flow so quick-picks can resume the pipeline
          return
        }
        scheduleAutoContinue()
        return
      }

    } catch (error) {
      autoFlowActiveRef.current = false
      setAutoFlowActive(false)
      const duration = Date.now() - startTime
      updateStage(nextStage.id, { 
        status: 'error', 
        error: error instanceof Error ? error.message : 'Unknown error',
        duration 
      })
    } finally {
      const continuing = autoContinueTimerRef.current !== null
      processingLockRef.current = false
      if (!continuing) {
        setIsProcessing(false)
        setCurrentStage(null)
        if (onProcessingChange) {
          onProcessingChange(false)
        }
      }
    }
  }

  const extractTitlesFromPdfData = (data: any): string[] => {
    const titles: string[] = []
    for (const set of data?.sets || []) {
      for (const song of set?.songs || []) {
        if (song?.title) titles.push(song.title)
      }
    }
    for (const extra of data?.extras || []) {
      if (extra?.title) titles.push(extra.title)
    }
    return titles
  }

  const buildValidationInputFromExtraction = (extractionData: any) => {
    const sets = extractionData?.sets || []
    const extras = extractionData?.extras || []
    const totalFromSets = sets.reduce(
      (sum: number, set: any) => sum + (set.songs?.length || 0),
      0
    )

    return {
      sets,
      extras,
      errors: extractionData?.errors || [],
      counts: extractionData?.counts || {
        total: totalFromSets + extras.length,
        validated_total: 0,
        missing_total: totalFromSets + extras.length,
      },
    }
  }

  const runPDFExtraction = async () => {
    if (!setlistFile) throw new Error('No setlist file provided')
    
    // Check if user is authenticated first
    const userStatus = await apiService.getUserStatus()
    if (!userStatus.ok || !userStatus.data?.authenticated) {
      throw new Error('User not authenticated. Please sign in first.')
    }
    
    if (!userStatus.data.backup_uploaded) {
      throw new Error('No backup file uploaded. Please upload a backup file first.')
    }
    
    // Generate cleaned up name from filename
    const cleanedName = setlistFile.name
      .replace(/\.(pdf|png|jpg|jpeg|txt)$/i, '')
      .replace(/[^a-zA-Z0-9\s-]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 50)
      || 'Set'
    
    // PDF extraction only — do not run validation/song extraction yet (user maps first)
    const formData = new FormData()
    formData.append('pdf', setlistFile)
    formData.append('secret', API_SECRET)
    formData.append('name', cleanedName)
    
    updateStage('pdf_extraction', {
      message: 'Extracting songs from PDF...',
      details: 'Progress: 10%'
    })

    const response = await fetch(`${getApiBaseUrl()}/standalone/pdf-extraction`, {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const payload = await response.json()
    if (!payload.success) {
      throw new Error(payload.error || 'PDF extraction failed')
    }

    const allTitles = extractTitlesFromPdfData(payload.data)
    const extractedSongs = allTitles.length

    setPdfFallbackName(cleanedName)
    setOutputBaseName((prev) => prev || cleanedName)

    return {
      success: true,
      extractedSongs,
      allTitles,
      extractionData: payload.data,
      pdfFallbackName: cleanedName,
      message: `Extracted ${extractedSongs} songs from PDF`,
    }
  }

  const runTitleValidation = async () => {
    const pdfStage = stagesRef.current.find((s) => s.id === 'pdf_extraction')
    const pdfResult = pdfStage?.result || pdfResultRef.current

    if (!pdfResult?.extractionData) {
      throw new Error('PDF extraction must be completed first')
    }

    const extractionData = pdfResult.extractionData
    if (!extractionData?.sets?.length) {
      throw new Error('No sets extracted from PDF')
    }

    const extractedCount =
      pdfResult.extractedSongs ||
      extractTitlesFromPdfData(extractionData).length

    if (extractedCount === 0) {
      throw new Error('No titles extracted from PDF')
    }

    // Preserve multi-set structure from PDF extraction (Set 1, Set 2, extras, etc.)
    const validationData = buildValidationInputFromExtraction(extractionData)

    // Create a temporary JSON file for upload
    const jsonBlob = new Blob([JSON.stringify(validationData)], { type: 'application/json' })
    const formData = new FormData()
    formData.append('json_file', jsonBlob, 'validation_input.json')
    formData.append('secret', API_SECRET)

    const response = await fetch(`${getApiBaseUrl()}/standalone/title-validation`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`Validation failed: ${response.status} ${response.statusText}`)
    }

    const validationResult = await response.json()
    
    if (!validationResult.success) {
      throw new Error(`Validation failed: ${validationResult.error || 'Unknown error'}`)
    }

    // Store the validation data for use by the shared component and subsequent stages
    const result = {
      success: true,
      validatedSongs: validationResult.data.counts?.validated_total || 0,
      unfoundTitles: [], // Will be populated by the shared component
      extractedSongs: validationResult.data.counts?.total || 0,
      message: `Validated ${validationResult.data.counts?.validated_total || 0} out of ${validationResult.data.counts?.total || 0} songs`,
      validationData: validationResult.data,
      stagedData: validationResult.data
    }

    stagedValidationDataRef.current = validationResult.data
    return result
  }

  const runSongExtraction = async () => {
    const pdfStage = stagesRef.current.find((s) => s.id === 'pdf_extraction')
    const validationStage = stagesRef.current.find((s) => s.id === 'title_validation')
    const pdfResult = pdfStage?.result || pdfResultRef.current

    if (!pdfResult || !validationStage?.result) {
      throw new Error('Previous stages must be completed first')
    }

    // Use the latest staged validation data (mappings may have been saved after validation)
    const validationData =
      stagedValidationDataRef.current ||
      validationStage.result.stagedData ||
      validationStage.result.validationData
    
    if (!validationData) {
      throw new Error('No validation data available for song extraction')
    }
    console.log('🎵 Using staged validation data for song extraction:', validationData.counts)
    console.log('🎵 Validation data source:', validationStage.result.stagedData ? 'stagedData' : 'validationData')
    
    // Check if "Party Started" is in the validation data
    for (const set of validationData.sets || []) {
      for (const song of set.songs || []) {
        if (song.title === 'Party Started') {
          console.log('🎵 Party Started song in validation data:', {
            title: song.title,
            validated: song.validated,
            validated_title: song.validated_title,
            song_id: song.song_id,
            status: song.status
          })
        }
      }
    }


    const chosenName = outputBaseName || pdfResult.pdfFallbackName || pdfResult.outputBaseName || 'Set'

    // Create a temporary JSON file for song extraction
    console.log('🎵 Sending validation data to song extraction:', JSON.stringify(validationData, null, 2))
    const jsonBlob = new Blob([JSON.stringify(validationData)], { type: 'application/json' })
    const formData = new FormData()
    formData.append('json_file', jsonBlob, 'validated_input.json')
    formData.append('secret', API_SECRET)
    formData.append('set_name', chosenName)

    const response = await fetch(`${getApiBaseUrl()}/standalone/song-extraction`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`Song extraction failed: ${response.status} ${response.statusText}`)
    }

    const extractionResult = await response.json()
    
    if (!extractionResult.success) {
      throw new Error(`Song extraction failed: ${extractionResult.error || 'Unknown error'}`)
    }

    const stats = extractionResult.data?.statistics || {}
    const fileSize = extractionResult.data?.file_size || 0

    return {
      success: true,
      downloadId: extractionResult.data?.download_id,
      downloadUrl: extractionResult.data?.download_url || '#',
      filename: `${chosenName.replace(/ /g, '_')}.sbp`,
      fileSize: fileSize,
      message: `SBP file created with ${stats.extracted_songs || 0} songs (${fileSize} bytes)`,
      stagedData: extractionResult.data
    }
  }

  const resetProcessing = () => {
    if (autoContinueTimerRef.current) {
      clearTimeout(autoContinueTimerRef.current)
      autoContinueTimerRef.current = null
    }
    processingLockRef.current = false
    autoFlowActiveRef.current = false
    setAutoFlowActive(false)
    stagedValidationDataRef.current = null
    pdfResultRef.current = null
    setOutputBaseName("")
    setPdfFallbackName("")
    setStages((prev) => {
      const next = prev.map((stage) => ({ ...stage, status: 'pending' as const, result: undefined, error: undefined, duration: undefined }))
      stagesRef.current = next
      return next
    })
    setCurrentStage(null)
    setIsProcessing(false)
    setOverallProgress(0)
    setFinalResult(null)
  }


  return (
    <div className="space-y-6">
      {/* Authentication Status Warning */}
      {authStatus && (!authStatus.authenticated || !authStatus.backupUploaded) && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {!authStatus.authenticated 
              ? "Please sign in first to start processing." 
              : "Please upload a backup file first before processing setlists."
            }
          </AlertDescription>
        </Alert>
      )}

      {/* Gig-based output naming */}
      <GigNameField
        fallbackName={pdfFallbackName}
        value={outputBaseName}
        onChange={setOutputBaseName}
      />

      {/* Progress Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Processing Pipeline
          </CardTitle>
          <CardDescription>
            {autoFlowActive
              ? 'Running — will pause only if song mapping is needed'
              : 'Review the gig name above, then click Process Setlist to start'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Overall Progress</span>
              <span className="text-sm text-muted-foreground">{Math.round(overallProgress)}%</span>
            </div>
            <Progress value={overallProgress} className="w-full" />
          </div>
        </CardContent>
      </Card>

      {/* Processing Stages */}
      <div className="space-y-4">
        {stages.map((stage, index) => (
          <Card key={stage.id} className={`transition-all ${
            stage.status === 'running' ? 'ring-2 ring-blue-500' : 
            stage.status === 'completed' ? 'ring-2 ring-green-500' :
            stage.status === 'error' ? 'ring-2 ring-red-500' : ''
          }`}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getStageStatusIcon(stage.status)}
                  <div>
                    <CardTitle className="text-lg">{stage.name}</CardTitle>
                    <CardDescription>{stage.description}</CardDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {stage.duration && (
                    <Badge variant="outline">
                      {stage.duration}ms
                    </Badge>
                  )}
                  <Badge variant={
                    stage.status === 'completed' ? 'default' :
                    stage.status === 'error' ? 'destructive' :
                    stage.status === 'running' ? 'secondary' :
                    'outline'
                  }>
                    {stage.status}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            
            {stage.result && (
              <CardContent>
                <Alert>
                  <CheckCircle className="h-4 w-4" />
                  <AlertDescription>
                    {stage.result.message}
                    {stage.result.extractedSongs && (
                      <div className="mt-2 text-sm">
                        <strong>Songs extracted:</strong> {stage.result.extractedSongs}
                      </div>
                    )}
                    {stage.result.validatedSongs !== undefined && (
                      <div className="mt-2 text-sm">
                        <strong>Songs validated:</strong> {stage.result.validatedSongs}
                      </div>
                    )}
                  </AlertDescription>
                </Alert>
                
                {/* Use shared TitleValidationComponent for title validation stage */}
                {stage.id === 'title_validation' && stage.status === 'completed' && (
                  <div className="mt-4">
           <TitleValidationComponent
             onComplete={(result) => {
               console.log('Title validation completed with result:', result)
               stagedValidationDataRef.current = result
               // Update the stage with the new result and staged data
               updateStage('title_validation', {
                 status: 'completed',
                 result: {
                   success: true,
                   validatedSongs: result.counts?.validated_total || 0,
                   unfoundTitles: [], // Will be populated by the component
                   extractedSongs: result.counts?.total || 0,
                   message: `Validated ${result.counts?.validated_total || 0} out of ${result.counts?.total || 0} songs`,
                   validationData: result,
                   stagedData: result // Store staged data for subsequent stages
                 }
               })
             }}
             onError={(error) => {
               console.error('Title validation error:', error)
               updateStage('title_validation', {
                 status: 'error',
                 error: error
               })
             }}
             onMappingSaved={(newValidationData) => {
               console.log('🔔 onMappingSaved callback called with:', newValidationData.counts)
               updateStagedValidationData(newValidationData)
               if (
                 autoFlowActiveRef.current &&
                 isFullyValidated(newValidationData) &&
                 stagesRef.current.find((s) => s.id === 'song_extraction')?.status === 'pending'
               ) {
                 scheduleAutoContinue()
               }
             }}
             showFileUpload={false}
             showInstructions={false}
             className="border-0 p-0"
             preloadedValidationData={stage.result?.validationData}
           />
                  </div>
                )}
              </CardContent>
            )}

            {stage.error && (
              <CardContent>
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertDescription>
                    <strong>Error:</strong> {stage.error}
                  </AlertDescription>
                </Alert>
              </CardContent>
            )}
          </Card>
        ))}
      </div>

      {/* Control Buttons */}
      <div className="flex items-center gap-4">
        <Button 
          onClick={startPipeline}
          disabled={!canProceed()}
          className="flex items-center gap-2"
        >
          {isProcessing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              {getNextPendingStage()
                ? getNextPendingStage()?.id === 'song_extraction'
                  ? 'Continue to Song Extraction'
                  : stages.every((s) => s.status === 'pending')
                    ? 'Process Setlist'
                    : `Start ${getNextPendingStage()?.name}`
                : 'All Complete'}
            </>
          )}
        </Button>

        <Button 
          variant="outline" 
          onClick={resetProcessing}
          disabled={isProcessing}
          className="flex items-center gap-2"
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </Button>

      </div>

      {/* Final Results */}
      {finalResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              Processing Complete
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Alert>
              <CheckCircle className="h-4 w-4" />
              <AlertDescription>
                All stages completed successfully! Your SBP file is ready for download.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

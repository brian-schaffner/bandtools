"use client"

import { useState, useRef, useEffect } from 'react'
import { API_SECRET, getApiAuthHeaders, getApiBaseUrl } from '@/lib/api'

interface TitleValidationComponentProps {
  onComplete: (result: any) => void
  onError: (error: string) => void
  // Optional props for different contexts
  selectedFile?: File | null
  onFileSelect?: (file: File | null) => void
  showFileUpload?: boolean
  showInstructions?: boolean
  className?: string
  // Pre-loaded validation data (for main UI integration)
  preloadedValidationData?: any
  // Callback when mappings are saved (for main UI integration)
  onMappingSaved?: (newValidationData: any) => void
}

export function TitleValidationComponent({ 
  onComplete, 
  onError,
  selectedFile: externalSelectedFile,
  onFileSelect,
  showFileUpload = true,
  showInstructions = true,
  className = "",
  preloadedValidationData,
  onMappingSaved
}: TitleValidationComponentProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(externalSelectedFile || null)
  const [validationResult, setValidationResult] = useState<any>(null)
  const [userCatalog, setUserCatalog] = useState<any[]>([])
  const [userMappings, setUserMappings] = useState<Record<string, string>>({})
  const [quickPicks, setQuickPicks] = useState<Record<string, string[]>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Sync with external selectedFile prop
  useEffect(() => {
    if (externalSelectedFile !== undefined) {
      setSelectedFile(externalSelectedFile)
    }
  }, [externalSelectedFile])

  // Handle preloaded validation data (for main UI integration)
  useEffect(() => {
    if (preloadedValidationData) {
      setValidationResult(preloadedValidationData)
      setProgress(100)
      setStatus('Validation data loaded')
    }
  }, [preloadedValidationData])

  // Load user catalog and mappings on component mount
  useEffect(() => {
    const loadUserData = async () => {
      try {
        console.log('Loading user data for title validation component...')
        
        // Load catalog from standalone endpoint
        const catalogResponse = await fetch(`${getApiBaseUrl()}/standalone/user-catalog`, {
          headers: getApiAuthHeaders(),
        })
        if (catalogResponse.ok) {
          const catalogData = await catalogResponse.json()
          setUserCatalog(catalogData.songs || [])
          console.log(`Loaded ${catalogData.songs?.length || 0} songs from catalog`)
        } else {
          console.error('Failed to load catalog:', catalogResponse.status)
        }

        // Load mappings from standalone endpoint (we'll use empty for now)
        setUserMappings({})
        
        console.log('User data loaded for title validation')
      } catch (error) {
        console.error('Error loading user data:', error)
      }
    }

    loadUserData()
  }, [])

  // Generate quick pick suggestions
  const generateQuickPicks = (title: string) => {
    if (userCatalog.length === 0) return []

    const titleWords = title.toLowerCase().split(/\s+/).filter(word => word.length > 2)
    const suggestions: { song: string; score: number }[] = []
    
    for (const song of userCatalog) {
      let score = 0
      const songName = song.name || song
      const songLower = songName.toLowerCase()
      
      // Exact match gets highest score
      if (songLower.includes(title.toLowerCase())) {
        score += 100
      }
      
      // Word matches
      for (const word of titleWords) {
        if (songLower.includes(word)) {
          score += 10
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
        suggestions.push({ song: songName, score })
      }
    }
    
    // Sort by score and return top 5
    return suggestions
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map(s => s.song)
  }

  // Update quick picks when validation result changes
  useEffect(() => {
    // Extract unfound titles from the validation result
    const unfoundTitles: string[] = []
    
    if (validationResult?.sets) {
      validationResult.sets.forEach((set: any) => {
        if (set.songs) {
          set.songs.forEach((song: any) => {
            if (!song.validated) {
              unfoundTitles.push(song.title)
            }
          })
        }
      })
    }
    
    if (validationResult?.extras) {
      validationResult.extras.forEach((song: any) => {
        if (!song.validated) {
          unfoundTitles.push(song.title)
        }
      })
    }
    
    if (unfoundTitles.length > 0) {
      const newQuickPicks: Record<string, string[]> = {}
      unfoundTitles.forEach((title: string) => {
        newQuickPicks[title] = generateQuickPicks(title)
      })
      setQuickPicks(newQuickPicks)
    }
  }, [validationResult, userCatalog])

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file && (file.type === 'application/json' || file.name.endsWith('.json'))) {
      setSelectedFile(file)
      if (onFileSelect) {
        onFileSelect(file)
      }
    } else {
      onError('Please select a valid JSON file from PDF extraction')
    }
  }

  const handleValidate = async () => {
    // If we have preloaded validation data or existing validation result, we don't need a file
    if (!selectedFile && !preloadedValidationData && !validationResult) {
      onError('Please select a JSON file first')
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setStatus('Starting title validation...')

    try {
      const formData = new FormData()
      
      // If we have preloaded data, create a temporary file from it
      if (preloadedValidationData && !selectedFile) {
        const jsonBlob = new Blob([JSON.stringify(preloadedValidationData)], { type: 'application/json' })
        formData.append('json_file', jsonBlob, 'validation_input.json')
      } else if (validationResult && !selectedFile) {
        const jsonBlob = new Blob([JSON.stringify(validationResult)], { type: 'application/json' })
        formData.append('json_file', jsonBlob, 'validation_input.json')
      } else {
        formData.append('json_file', selectedFile)
      }
      
      formData.append('secret', API_SECRET)

      const response = await fetch(`${getApiBaseUrl()}/standalone/title-validation`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      
      if (result.success) {
        setProgress(100)
        setStatus('Validation completed successfully!')
        setValidationResult(result.data)
        if (onMappingSaved) {
          onMappingSaved(result.data)
        }
      } else {
        throw new Error(result.error || 'Validation failed')
      }

    } catch (error) {
      console.error('Title validation error:', error)
      onError(error instanceof Error ? error.message : 'Unknown error occurred')
    } finally {
      setIsProcessing(false)
    }
  }

  const applyMappingToValidationResult = (updatedResult: any, title: string, mappedTitle: string): boolean => {
    let mapped = false

    const markSong = (song: any) => {
      if (song.title !== title) return
      song.validated = true
      song.validated_title = mappedTitle
      song.status = 'Found through mapping'
      song.song_id = song.song_id ?? null
      mapped = true
    }

    for (const set of updatedResult.sets || []) {
      for (const song of set.songs || []) {
        markSong(song)
      }
    }
    for (const song of updatedResult.extras || []) {
      markSong(song)
    }

    if (mapped && updatedResult.counts) {
      updatedResult.counts.validated_total = (updatedResult.counts.validated_total || 0) + 1
      updatedResult.counts.missing_total = Math.max(0, (updatedResult.counts.missing_total || 0) - 1)
    }

    return mapped
  }

  const handleQuickMapping = async (title: string, mappedTitle: string) => {
    try {
      console.log(`Mapping "${title}" to "${mappedTitle}"`)
      
      // Save mapping to standalone backend endpoint
      const response = await fetch(`${getApiBaseUrl()}/standalone/save-mapping`, {
        method: 'POST',
        headers: {
          ...getApiAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          pdf_title: title,
          catalog_title: mappedTitle
        })
      })

      if (response.ok) {
        console.log(`Successfully saved mapping: "${title}" -> "${mappedTitle}"`)
        
        // Update local state
        setUserMappings(prev => ({ ...prev, [title]: mappedTitle }))
        
        // Remove from quick picks (but don't reprocess yet)
        setQuickPicks(prev => {
          const newQuickPicks = { ...prev }
          delete newQuickPicks[title]
          return newQuickPicks
        })
        
        // Update validation result to show the song as validated
        if (validationResult) {
          const updatedResult = JSON.parse(JSON.stringify(validationResult))
          applyMappingToValidationResult(updatedResult, title, mappedTitle)
          
          setValidationResult(updatedResult)
          
          // Notify parent component of the updated validation data
          if (onMappingSaved) {
            console.log('🔔 Calling onMappingSaved with updated result:', updatedResult.counts)
            onMappingSaved(updatedResult)
          } else {
            console.warn('⚠️ onMappingSaved callback not provided')
          }
        }
        
        console.log('Mapping saved. Other quick picks remain available for mapping.')
      } else {
        const errorData = await response.json()
        console.error('Failed to save mapping:', errorData)
        onError(`Failed to save mapping: ${errorData.detail || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Error saving mapping:', error)
      onError('Failed to save mapping')
    }
  }

  const handleDownload = () => {
    if (validationResult) {
      onComplete(validationResult)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setProgress(0)
    setStatus('')
    setValidationResult(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    if (onFileSelect) {
      onFileSelect(null)
    }
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* File Upload - only show if enabled */}
      {showFileUpload && (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
          <div className="text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <div className="mt-4">
              <label htmlFor="json-upload" className="cursor-pointer">
                <span className="mt-2 block text-sm font-medium text-gray-900">
                  {selectedFile ? selectedFile.name : 'Click to upload JSON file from PDF extraction'}
                </span>
                <input
                  ref={fileInputRef}
                  id="json-upload"
                  type="file"
                  accept=".json,application/json"
                  onChange={handleFileSelect}
                  className="sr-only"
                  disabled={isProcessing}
                />
              </label>
              <p className="mt-1 text-xs text-gray-500">
                JSON files from PDF extraction only
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      {isProcessing && (
        <div className="space-y-4">
          <div className="bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm text-gray-600 text-center">{status}</p>
        </div>
      )}

      {/* Validation Results */}
      {validationResult && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-lg font-medium text-green-800 mb-2">Validation Results</h3>
            <p className="text-green-700">
              Validated {validationResult.counts?.validated_total || 0} out of {validationResult.counts?.total || 0} songs 
              ({validationResult.counts?.missing_total || 0} need mapping)
            </p>
          </div>

          {/* Unfound Titles Mapping */}
          {(() => {
            // Extract unfound titles from the validation result
            const unfoundTitles: string[] = []
            
            if (validationResult.sets) {
              validationResult.sets.forEach((set: any) => {
                if (set.songs) {
                  set.songs.forEach((song: any) => {
                    if (!song.validated) {
                      unfoundTitles.push(song.title)
                    }
                  })
                }
              })
            }
            
            if (validationResult.extras) {
              validationResult.extras.forEach((song: any) => {
                if (!song.validated) {
                  unfoundTitles.push(song.title)
                }
              })
            }
            
            return unfoundTitles.length > 0 ? (
              <div className="space-y-4">
                <h3 className="text-lg font-medium text-gray-900">Map Missing Titles</h3>
                <div className="space-y-3">
                  {unfoundTitles.map((title: string) => (
                    <div key={title} className="border rounded-lg p-4 bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-900">{title}</span>
                        <span className="text-sm text-gray-500">Quick picks</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {(quickPicks[title] || []).map((suggestion) => (
                          <button
                            key={suggestion}
                            onClick={() => handleQuickMapping(title, suggestion)}
                            className="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded-full hover:bg-blue-200 transition-colors"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-blue-700">🎉 All songs validated successfully! No mapping needed.</p>
              </div>
            )
          })()}

          {/* Download Button */}
          <div className="flex space-x-4">
            <button
              onClick={handleDownload}
              className="flex-1 bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Download Validated JSON
            </button>
            <button
              onClick={handleValidate}
              disabled={isProcessing}
              className="px-6 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {isProcessing ? 'Re-validating...' : 'Re-validate After Mapping'}
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex space-x-4">
        <button
          onClick={handleValidate}
          disabled={!selectedFile || isProcessing}
          className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {isProcessing ? 'Validating...' : 'Validate Titles'}
        </button>
        
        <button
          onClick={handleReset}
          disabled={isProcessing}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Instructions - only show if enabled */}
      {showInstructions && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-yellow-800 mb-2">Instructions</h3>
          <ul className="text-sm text-yellow-700 space-y-1">
            <li>• Upload the JSON file from PDF extraction</li>
            <li>• System will validate against brian@schaffner.net's backup</li>
            <li>• Uses existing title mappings for corrections</li>
            <li>• Map any missing titles using quick pick suggestions</li>
            <li>• Download validated JSON for song extraction</li>
          </ul>
        </div>
      )}
    </div>
  )
}

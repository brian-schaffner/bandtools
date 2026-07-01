"use client"

import { useState, useRef } from 'react'
import { API_BASE_URL, API_SECRET } from '@/lib/api'

interface SongExtractionComponentProps {
  onComplete: (result: any) => void
  onError: (error: string) => void
}

export function SongExtractionComponent({ onComplete, onError }: SongExtractionComponentProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [setName, setSetName] = useState<string>('Extracted Set')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file && (file.type === 'application/json' || file.name.endsWith('.json'))) {
      setSelectedFile(file)
    } else {
      onError('Please select a valid JSON file from title validation')
    }
  }

  const handleExtract = async () => {
    if (!selectedFile) {
      onError('Please select a JSON file first')
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setStatus('Starting song extraction...')

    try {
      const formData = new FormData()
      formData.append('json_file', selectedFile)
      formData.append('secret', API_SECRET)
      formData.append('set_name', setName)

      const response = await fetch(`${API_BASE_URL}/standalone/song-extraction`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      
      if (result.success) {
        setProgress(100)
        setStatus('SBP file created successfully!')
        onComplete(result.data)
      } else {
        throw new Error(result.error || 'Song extraction failed')
      }

    } catch (error) {
      console.error('Song extraction error:', error)
      onError(error instanceof Error ? error.message : 'Unknown error occurred')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setSetName('Extracted Set')
    setProgress(0)
    setStatus('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      {/* Set Name Input */}
      <div>
        <label htmlFor="set-name" className="block text-sm font-medium text-gray-700 mb-2">
          Set Name
        </label>
        <input
          id="set-name"
          type="text"
          value={setName}
          onChange={(e) => setSetName(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="Enter name for the set"
          disabled={isProcessing}
        />
      </div>

      {/* File Upload */}
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div className="mt-4">
            <label htmlFor="json-upload" className="cursor-pointer">
              <span className="mt-2 block text-sm font-medium text-gray-900">
                {selectedFile ? selectedFile.name : 'Click to upload JSON file from title validation'}
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
              JSON files from title validation only
            </p>
          </div>
        </div>
      </div>

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

      {/* Actions */}
      <div className="flex space-x-4">
        <button
          onClick={handleExtract}
          disabled={!selectedFile || isProcessing}
          className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {isProcessing ? 'Creating SBP...' : 'Create SBP File'}
        </button>
        
        <button
          onClick={handleReset}
          disabled={isProcessing}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Instructions */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-yellow-800 mb-2">Instructions</h3>
        <ul className="text-sm text-yellow-700 space-y-1">
          <li>• Upload the validated JSON file from title validation</li>
          <li>• Enter a name for your set</li>
          <li>• System will create SBP file from brian@schaffner.net's backup</li>
          <li>• Download the final SBP file for use in SongbookPro</li>
        </ul>
      </div>
    </div>
  )
}

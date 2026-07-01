"use client"

import { useState, useRef } from 'react'
import { API_BASE_URL, API_SECRET } from '@/lib/api'

interface PDFExtractionComponentProps {
  onComplete: (result: any) => void
  onError: (error: string) => void
}

export function PDFExtractionComponent({ onComplete, onError }: PDFExtractionComponentProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file)
    } else {
      onError('Please select a valid PDF file')
    }
  }

  const handleExtract = async () => {
    if (!selectedFile) {
      onError('Please select a PDF file first')
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setStatus('Starting PDF extraction...')

    try {
      const formData = new FormData()
      formData.append('pdf', selectedFile)
      formData.append('secret', API_SECRET)
      formData.append('name', 'Standalone Extraction')

      const response = await fetch(`${API_BASE_URL}/standalone/pdf-extraction`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      
      if (result.success) {
        setProgress(100)
        setStatus('Extraction completed successfully!')
        onComplete(result.data)
      } else {
        throw new Error(result.error || 'Extraction failed')
      }

    } catch (error) {
      console.error('PDF extraction error:', error)
      onError(error instanceof Error ? error.message : 'Unknown error occurred')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setProgress(0)
    setStatus('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      {/* File Upload */}
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div className="mt-4">
            <label htmlFor="pdf-upload" className="cursor-pointer">
              <span className="mt-2 block text-sm font-medium text-gray-900">
                {selectedFile ? selectedFile.name : 'Click to upload PDF file'}
              </span>
              <input
                ref={fileInputRef}
                id="pdf-upload"
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="sr-only"
                disabled={isProcessing}
              />
            </label>
            <p className="mt-1 text-xs text-gray-500">
              PDF files only
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
          {isProcessing ? 'Extracting...' : 'Extract Songs'}
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
          <li>• Upload a PDF file containing song titles</li>
          <li>• The AI will extract and organize song titles</li>
          <li>• Download the JSON result for the next stage</li>
          <li>• Use the JSON file as input for Title Validation</li>
        </ul>
      </div>
    </div>
  )
}

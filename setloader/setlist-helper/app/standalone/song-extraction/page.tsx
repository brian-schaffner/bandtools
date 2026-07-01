"use client"

import { useState } from 'react'
import { SongExtractionComponent } from './song-extraction-component'
import { API_BASE_URL, API_SECRET } from '@/lib/api'

export default function SongExtractionPage() {
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleComplete = (extractionResult: any) => {
    setResult(extractionResult)
    setError(null)
  }

  const handleError = (errorMessage: string) => {
    setError(errorMessage)
    setResult(null)
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Song Extraction Tool
            </h1>
            <p className="text-gray-600">
              Create SBP file from validated song titles
            </p>
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>User:</strong> brian@schaffner.net<br/>
                <strong>Purpose:</strong> Stage 3 of 3 - Create final SBP file
              </p>
            </div>
          </div>

          <SongExtractionComponent 
            onComplete={handleComplete}
            onError={handleError}
          />

          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <h3 className="text-lg font-semibold text-red-800 mb-2">Error</h3>
              <p className="text-red-700">{error}</p>
            </div>
          )}

          {result && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <h3 className="text-lg font-semibold text-green-800 mb-2">SBP File Created</h3>
              <div className="space-y-2">
                <p><strong>File Size:</strong> {result.file_size?.toLocaleString()} bytes</p>
                <p><strong>Total Songs:</strong> {result.statistics?.total_songs || 0}</p>
                <p><strong>Extracted:</strong> {result.statistics?.extracted_songs || 0}</p>
                <p><strong>Missing:</strong> {result.statistics?.missing_songs || 0}</p>
                <p><strong>Sets Created:</strong> {result.statistics?.sets_created || 0}</p>
                {result.sets && result.sets.length > 0 && (
                  <div>
                    <p><strong>Sets:</strong></p>
                    <ul className="ml-4 space-y-1">
                      {result.sets.map((set: any, index: number) => (
                        <li key={index} className="text-sm">• {set.name}: {set.song_count} songs</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="mt-4">
                <a
                  href={`${API_BASE_URL}${result.download_url}&X-Secret=${encodeURIComponent(API_SECRET)}`}
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Download SBP File
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

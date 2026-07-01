"use client"

import { useState } from 'react'
import { PDFExtractionComponent } from './pdf-extraction-component'

export default function PDFExtractionPage() {
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
              PDF Extraction Tool
            </h1>
            <p className="text-gray-600">
              Extract song titles from PDF files using AI
            </p>
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>User:</strong> brian@schaffner.net<br/>
                <strong>Purpose:</strong> Stage 1 of 3 - Extract song titles from PDF
              </p>
            </div>
          </div>

          <PDFExtractionComponent 
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
              <h3 className="text-lg font-semibold text-green-800 mb-2">Extraction Complete</h3>
              <div className="space-y-2">
                <p><strong>Total Songs:</strong> {result.counts?.total || 0}</p>
                {result.counts?.per_set && Object.entries(result.counts.per_set).map(([setName, count]) => (
                  <p key={setName}><strong>{setName}:</strong> {count} songs</p>
                ))}
                {result.counts?.extras > 0 && (
                  <p><strong>Extras:</strong> {result.counts.extras} songs</p>
                )}
              </div>
              <div className="mt-4">
                <a
                  href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(result, null, 2))}`}
                  download="extracted_titles.json"
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Download JSON Result
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

"use client"

import { useState } from 'react'
import { TitleValidationComponent } from '../../../components/shared/TitleValidationComponent'

export default function TitleValidationPage() {
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleComplete = (validationResult: any) => {
    setResult(validationResult)
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
              Title Validation Tool
            </h1>
            <p className="text-gray-600">
              Validate extracted song titles against your catalog
            </p>
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>User:</strong> brian@schaffner.net<br/>
                <strong>Purpose:</strong> Stage 2 of 3 - Validate titles against backup
              </p>
            </div>
          </div>

          <TitleValidationComponent 
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
              <h3 className="text-lg font-semibold text-green-800 mb-2">Validation Complete</h3>
              <div className="space-y-2">
                <p><strong>Total Songs:</strong> {result.counts?.total || 0}</p>
                <p><strong>Validated:</strong> {result.counts?.validated_total || 0}</p>
                <p><strong>Missing:</strong> {result.counts?.missing_total || 0}</p>
                {result.counts?.per_set && Object.entries(result.counts.per_set).map(([setName, setCounts]: [string, any]) => (
                  <p key={setName}><strong>{setName}:</strong> {setCounts.validated}/{setCounts.total} validated</p>
                ))}
              </div>
              <div className="mt-4">
                <a
                  href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(result, null, 2))}`}
                  download="validated_titles.json"
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Download Validated JSON
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

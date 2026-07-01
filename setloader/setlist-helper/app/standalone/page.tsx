"use client"

import Link from 'next/link'

export default function StandaloneToolsPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            SetLoader Standalone Tools
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Independent processing components for testing and development
          </p>
          <div className="p-6 bg-blue-50 rounded-lg max-w-2xl mx-auto">
            <p className="text-sm text-blue-800">
              <strong>User:</strong> brian@schaffner.net<br/>
              <strong>Purpose:</strong> Test each processing stage independently
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* PDF Extraction */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">PDF Extraction</h2>
              <p className="text-gray-600 mb-4">
                Extract song titles from PDF files using AI
              </p>
              <div className="space-y-2 text-sm text-gray-500 mb-6">
                <p>• Input: PDF file</p>
                <p>• Output: JSON with song titles</p>
                <p>• Uses OpenAI for extraction</p>
              </div>
              <Link
                href="/standalone/pdf-extraction"
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                Open PDF Extraction
              </Link>
            </div>
          </div>

          {/* Title Validation */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Title Validation</h2>
              <p className="text-gray-600 mb-4">
                Validate extracted titles against your catalog
              </p>
              <div className="space-y-2 text-sm text-gray-500 mb-6">
                <p>• Input: JSON from PDF extraction</p>
                <p>• Output: Validated JSON</p>
                <p>• Uses backup and mappings</p>
              </div>
              <Link
                href="/standalone/title-validation"
                className="inline-flex items-center px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                Open Title Validation
              </Link>
            </div>
          </div>

          {/* Song Extraction */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Song Extraction</h2>
              <p className="text-gray-600 mb-4">
                Create SBP file from validated titles
              </p>
              <div className="space-y-2 text-sm text-gray-500 mb-6">
                <p>• Input: JSON from title validation</p>
                <p>• Output: SBP file</p>
                <p>• Ready for SongbookPro</p>
              </div>
              <Link
                href="/standalone/song-extraction"
                className="inline-flex items-center px-6 py-3 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition-colors"
              >
                Open Song Extraction
              </Link>
            </div>
          </div>
        </div>

        {/* Workflow Diagram */}
        <div className="mt-12 bg-white rounded-lg shadow-lg p-8">
          <h3 className="text-2xl font-bold text-gray-900 mb-6 text-center">Processing Workflow</h3>
          <div className="flex items-center justify-center space-x-8">
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-blue-600 font-bold">1</span>
              </div>
              <p className="text-sm font-medium text-gray-900">PDF Extraction</p>
              <p className="text-xs text-gray-500">PDF → JSON</p>
            </div>
            
            <div className="flex-1 h-0.5 bg-gray-300"></div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-green-600 font-bold">2</span>
              </div>
              <p className="text-sm font-medium text-gray-900">Title Validation</p>
              <p className="text-xs text-gray-500">JSON → JSON</p>
            </div>
            
            <div className="flex-1 h-0.5 bg-gray-300"></div>
            
            <div className="text-center">
              <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-purple-600 font-bold">3</span>
              </div>
              <p className="text-sm font-medium text-gray-900">Song Extraction</p>
              <p className="text-xs text-gray-500">JSON → SBP</p>
            </div>
          </div>
        </div>

        {/* Back to Main App */}
        <div className="mt-8 text-center">
          <Link
            href="/"
            className="inline-flex items-center px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            ← Back to Main Application
          </Link>
        </div>
      </div>
    </div>
  )
}

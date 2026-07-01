export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-md p-6 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold text-center mb-4">404 - Page Not Found</h1>
        <div className="text-center">
          <p className="text-gray-600 mb-4">The page you're looking for doesn't exist.</p>
          <a
            href="/"
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Go Home
          </a>
        </div>
      </div>
    </div>
  )
}

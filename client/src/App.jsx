import { useState, useEffect } from "react"

const App = () => {
  const [agencies, setAgencies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch("/api/agencies")
      .then((res) => {
        if (!res.ok) throw new Error(`API error: ${res.status}`)
        return res.json()
      })
      .then((data) => setAgencies(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading)
    return <p className="p-8 text-gray-500">Loading agency data...</p>
  if (error) return <p className="p-8 text-red-600">Error: {error}</p>

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">eCFR Analyzer</h1>
        <p className="text-sm text-gray-500">
          {agencies.length} agencies loaded
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: agency table (Step 9) */}
        <div className="lg:col-span-1 bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-3">Agencies</h2>
          <p className="text-sm text-gray-400">
            AgencyTable component goes here
          </p>
        </div>

        {/* Right column: charts (Step 9) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">Word Count by Agency</h2>
            <p className="text-sm text-gray-400">
              WordCountChart component goes here
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">Changes Over Time</h2>
            <p className="text-sm text-gray-400">
              ChangesChart component goes here
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">
              Net Regulatory Growth
            </h2>
            <p className="text-sm text-gray-400">
              RegGrowthChart component goes here
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

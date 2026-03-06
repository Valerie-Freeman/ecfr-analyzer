import { useState, useEffect } from "react"
import AgencyTable from "./components/AgencyTable"
import WordCountChart from "./components/WordCountChart"
import ChangesChart from "./components/ChangesChart"
import RegGrowthChart from "./components/RegGrowthChart"

const App = () => {
  const [agencies, setAgencies] = useState([])
  const [selectedSlug, setSelectedSlug] = useState(null)
  const [agencyDetail, setAgencyDetail] = useState(null)
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

  useEffect(() => {
    if (!selectedSlug) return
    fetch(`/api/agencies/${selectedSlug}`)
      .then((res) => {
        if (!res.ok) throw new Error(`API error: ${res.status}`)
        return res.json()
      })
      .then((data) => setAgencyDetail(data))
      .catch((err) => setError(err.message))
  }, [selectedSlug])

  const handleSelect = (slug) => {
    setSelectedSlug(slug)
    if (!slug) setAgencyDetail(null)
  }

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
        {/* Left column: agency table */}
        <div className="lg:col-span-1 bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-3">Agencies</h2>
          <AgencyTable
            agencies={agencies}
            selectedSlug={selectedSlug}
            onSelect={handleSelect}
          />
        </div>

        {/* Right column: charts */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">
              Word Count by Agency
            </h2>
            <WordCountChart agencies={agencies} />
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">
              Changes Over Time
              {agencyDetail &&
                ` - ${agencyDetail.short_name || agencyDetail.name}`}
            </h2>
            <ChangesChart
              changeHistory={agencyDetail?.change_history}
            />
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-3">
              DOGE-Era Regulatory Activity
              {agencyDetail &&
                ` - ${agencyDetail.short_name || agencyDetail.name}`}
            </h2>
            <RegGrowthChart
              changeHistory={agencyDetail?.change_history}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

import { useState, useEffect } from "react"
import AgencyTable from "./components/AgencyTable"
import WordCountChart from "./components/WordCountChart"
import ChangesChart from "./components/ChangesChart"
import RegGrowthChart from "./components/RegGrowthChart"
import ChangeIndicator from "./components/ChangeIndicator"
import { card, sectionHeading } from "./styles"

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
    <div className="min-h-screen p-6 bg-page-bg">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-medium text-gray-900 bg-white rounded-xl p-3 shadow">
          eCFR Analyzer
        </h1>
        <p className="text-sm text-gray-500 mr-3">
          {agencies.length} agencies loaded
          {agencies[0]?.computed_at &&
            (() => {
              const utc = new Date(agencies[0].computed_at + "Z")
              return (
                <span className="ml-2">
                  · Last updated{" "}
                  {utc.toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}{" "}
                  at{" "}
                  {utc.toLocaleTimeString(undefined, {
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              )
            })()}
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: agency table */}
        <div className={`${card} lg:col-span-1 flex flex-col lg:max-h-[calc(100vh-6rem)] lg:sticky lg:top-6`}>
          <h2 className={sectionHeading}>Agencies</h2>
          <AgencyTable
            agencies={agencies}
            selectedSlug={selectedSlug}
            onSelect={handleSelect}
          />
        </div>

        {/* Right column: charts */}
        <div className="lg:col-span-2 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className={`${card} lg:col-span-2`}>
            <h2 className={sectionHeading}>
              Top 10 Agencies by Word Count
            </h2>
            <WordCountChart agencies={agencies} />
          </div>

          <div className="lg:col-span-2">
            <ChangeIndicator agencyDetail={agencyDetail} />
          </div>

          <div className={`${card} min-h-[380px]`}>
            <h2 className={sectionHeading}>
              Changes Over Time (Last 5 Years)
              {agencyDetail && ` - ${agencyDetail.name}`}
            </h2>
            <ChangesChart changeHistory={agencyDetail?.change_history} />
          </div>

          <div className={`${card} min-h-[380px]`}>
            <h2 className={sectionHeading}>
              Removal Deficit (Last 12 Months)
              {agencyDetail && ` - ${agencyDetail.name}`}
            </h2>
            <RegGrowthChart changeHistory={agencyDetail?.change_history} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

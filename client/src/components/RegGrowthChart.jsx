import { useMemo } from "react"

const DOGE_START = "2025-01"

const RegGrowthChart = ({ changeHistory }) => {
  const stats = useMemo(() => {
    if (!changeHistory || changeHistory.length === 0) return null

    const recent = changeHistory.filter((e) => e.period >= DOGE_START)
    if (recent.length === 0) return null

    const substantive = recent.reduce((s, e) => s + e.substantive, 0)
    const nonSubstantive = recent.reduce((s, e) => s + e.non_substantive, 0)
    const removals = recent.reduce((s, e) => s + e.removals, 0)
    const total = substantive + nonSubstantive + removals
    if (total === 0) return null

    const ratio = (substantive - removals) / total

    return { substantive, nonSubstantive, removals, total, ratio }
  }, [changeHistory])

  if (!changeHistory || changeHistory.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        Select an agency to view DOGE-era regulatory activity
      </p>
    )
  }

  if (!stats) {
    return (
      <p className="text-sm text-gray-400">
        No regulatory changes recorded since January 2025
      </p>
    )
  }

  const pct = (stats.ratio * 100).toFixed(1)
  const isGrowth = stats.ratio > 0
  const color = isGrowth ? "text-red-600" : "text-green-600"
  const barColor = isGrowth ? "bg-red-400" : "bg-green-400"
  const label = isGrowth ? "Net Growth" : "Net Reduction"

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold ${color}`}>{pct}%</span>
        <span className="text-sm text-gray-500">{label}</span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-3">
        <div
          className={`h-3 rounded-full ${barColor}`}
          style={{ width: `${Math.min(Math.abs(stats.ratio) * 100, 100)}%` }}
        />
      </div>

      <p className="text-sm text-gray-600">
        Since DOGE (Jan 2025): {stats.total.toLocaleString()} changes
        {" "}({stats.substantive} substantive, {stats.removals} removals)
      </p>

      <p className="text-xs text-gray-400">
        (substantive - removals) / total changes. Positive = net growth, negative = net reduction.
      </p>
    </div>
  )
}

export default RegGrowthChart

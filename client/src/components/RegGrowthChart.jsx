import { useMemo } from "react"

const RegGrowthChart = ({ changeHistory }) => {
  const stats = useMemo(() => {
    if (!changeHistory || changeHistory.length === 0) return null

    // Rolling 12-month window; "YYYY-MM" format matches period strings
    const cutoff = new Date()
    cutoff.setMonth(cutoff.getMonth() - 12)
    const cutoffPeriod = cutoff.toISOString().slice(0, 7)

    const recent = changeHistory.filter((e) => e.period >= cutoffPeriod)
    if (recent.length === 0) return null

    // "substantive" = published in Federal Register (not editorial fixes)
    const substantive = recent.reduce((s, e) => s + e.substantive, 0)
    const nonSubstantive = recent.reduce((s, e) => s + e.non_substantive, 0)
    // "removals" = sections/parts deleted from the CFR
    const removals = recent.reduce((s, e) => s + e.removals, 0)
    const total = substantive + nonSubstantive + removals
    if (total === 0) return null

    // "substantive regulatory activity" = substantive + removals (disjoint in our DB)
    const regulatoryActivity = substantive + removals

    // Guard: can't compute ratio with zero substantive regulatory activity
    if (regulatoryActivity === 0) {
      return { substantive, nonSubstantive, removals, total, deficit: null }
    }

    // Removal Deficit: fraction of regulatory activity that is NOT removals
    // 0% = all removals (deregulatory), 100% = no removals
    const deficit = 1 - removals / regulatoryActivity

    return { substantive, nonSubstantive, removals, total, deficit }
  }, [changeHistory])

  if (!changeHistory || changeHistory.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        Select an agency to view removal deficit
      </p>
    )
  }

  if (!stats) {
    return (
      <p className="text-sm text-gray-400">
        No regulatory changes recorded in the last 12 months
      </p>
    )
  }

  if (stats.deficit === null) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-500">
          No substantive regulatory changes in the last 12 months
        </p>
        <p className="text-sm text-gray-600">
          {stats.total.toLocaleString()} non-substantive (editorial) changes recorded
        </p>
      </div>
    )
  }

  const pct = (stats.deficit * 100).toFixed(1)
  // Green = low deficit (more deregulatory), Red = high deficit (few removals)
  const color = stats.deficit > 0.5 ? "text-red-600" : "text-green-600"
  const barColor = stats.deficit > 0.5 ? "bg-red-400" : "bg-green-400"

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold ${color}`}>{pct}%</span>
        <span className="text-sm text-gray-500">Removal Deficit</span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-3">
        <div
          className={`h-3 rounded-full ${barColor}`}
          style={{ width: `${Math.min(stats.deficit * 100, 100)}%` }}
        />
      </div>

      <p className="text-sm text-gray-600">
        Last 12 months: {stats.total.toLocaleString()} changes
        {" "}({stats.substantive} substantive, {stats.removals} removals)
      </p>

      <p className="text-xs text-gray-400">
        1 - (removals / (substantive + removals)). 0% = all removals, 100% = no removals.
        Aligned with EO 13771 deregulatory ratio framework.
      </p>
    </div>
  )
}

export default RegGrowthChart

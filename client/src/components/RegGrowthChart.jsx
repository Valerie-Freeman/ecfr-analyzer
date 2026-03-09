import { useMemo } from "react"
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts"
import { CHART_COLORS } from "../styles"

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
      <div className="flex items-center justify-center h-full pb-16">
        <p className="text-sm text-gray-400">
          Select an agency to view removal deficit
        </p>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full pb-16">
        <p className="text-sm text-gray-400">
          No regulatory changes recorded in the last 12 months
        </p>
      </div>
    )
  }

  if (stats.deficit === null) {
    return (
      <div className="flex items-center justify-center h-full pb-16">
        <div className="space-y-3 text-center">
          <p className="text-sm text-gray-500">
            No substantive regulatory changes in the last 12 months
          </p>
          <p className="text-sm text-gray-600">
            {stats.total.toLocaleString()} non-substantive (editorial) changes recorded
          </p>
        </div>
      </div>
    )
  }

  const pct = (stats.deficit * 100).toFixed(1)

  const pieData = [
    { name: "Substantive", value: stats.substantive },
    { name: "Non-substantive", value: stats.nonSubstantive },
    { name: "Removals", value: stats.removals },
  ].filter((d) => d.value > 0)

  const colorMap = { Substantive: CHART_COLORS.substantive, "Non-substantive": CHART_COLORS.non_substantive, Removals: CHART_COLORS.removals }

  return (
    <div className="space-y-4">
      <div className="relative" style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={85}
              dataKey="value"
              strokeWidth={2}
            >
              {pieData.map((entry) => (
                <Cell key={entry.name} fill={colorMap[entry.name]} />
              ))}
            </Pie>
            <Tooltip formatter={(v) => v.toLocaleString()} />
            <Legend wrapperStyle={{ paddingTop: 12 }} />
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ marginBottom: 24 }}>
          <div className="text-center leading-tight">
            <span className="text-2xl font-bold text-gray-800">{pct}%</span>
            <p className="text-xs text-gray-400 mt-0.5">deficit</p>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-600 text-center">
        {stats.total.toLocaleString()} changes: {stats.substantive} substantive, {stats.removals} removals, {stats.nonSubstantive} editorial
      </p>

      <p className="text-xs text-gray-400 text-center">
        1 - (removals / (substantive + removals)). 0% = all removals, 100% = no removals.
      </p>
    </div>
  )
}

export default RegGrowthChart

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

const COLORS = {
  substantive: "#3b82f6",
  non_substantive: "#94a3b8",
  removals: "#ef4444",
}

const YEARS = 5

const ChangesChart = ({ changeHistory }) => {
  if (!changeHistory || changeHistory.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        Select an agency to view changes over time
      </p>
    )
  }

  const cutoff = `${new Date().getFullYear() - YEARS}-01`
  const filtered = changeHistory.filter((e) => e.period >= cutoff)

  if (filtered.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        No changes in the last {YEARS} years
      </p>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={filtered} margin={{ left: 0, right: 10, bottom: 20 }}>
        <XAxis
          dataKey="period"
          fontSize={11}
          angle={-45}
          textAnchor="end"
          height={60}
          dy={10}
          interval="preserveStartEnd"
        />
        <YAxis fontSize={12} />
        <Tooltip />
        <Legend />
        <Bar
          dataKey="substantive"
          stackId="changes"
          fill={COLORS.substantive}
          name="Substantive"
        />
        <Bar
          dataKey="non_substantive"
          stackId="changes"
          fill={COLORS.non_substantive}
          name="Non-substantive"
        />
        <Bar
          dataKey="removals"
          stackId="changes"
          fill={COLORS.removals}
          name="Removals"
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default ChangesChart

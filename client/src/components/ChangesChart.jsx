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

const ChangesChart = ({ changeHistory }) => {
  if (!changeHistory || changeHistory.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        Select an agency to view changes over time
      </p>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={changeHistory} margin={{ left: 0, right: 10 }}>
        <XAxis
          dataKey="period"
          fontSize={11}
          angle={-45}
          textAnchor="end"
          height={60}
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

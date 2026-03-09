import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import { CHART_COLORS } from "../styles"

const YEARS = 5

const ChangesChart = ({ changeHistory }) => {
  if (!changeHistory || changeHistory.length === 0) {
    return (
      <div className="flex items-center justify-center h-full pb-16">
        <p className="text-sm text-gray-400">
          Select an agency to view changes over time
        </p>
      </div>
    )
  }

  const cutoff = `${new Date().getFullYear() - YEARS}-01`
  const filtered = changeHistory.filter((e) => e.period >= cutoff)

  if (filtered.length === 0) {
    return (
      <div className="flex items-center justify-center h-full pb-16">
        <p className="text-sm text-gray-400">
          No changes in the last {YEARS} years
        </p>
      </div>
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
          fill={CHART_COLORS.substantive}
          name="Substantive"
        />
        <Bar
          dataKey="non_substantive"
          stackId="changes"
          fill={CHART_COLORS.non_substantive}
          name="Non-substantive"
        />
        <Bar
          dataKey="removals"
          stackId="changes"
          fill={CHART_COLORS.removals}
          name="Removals"
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default ChangesChart

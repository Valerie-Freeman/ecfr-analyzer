import { useMemo } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts"

const TOP_N = 10

const WordCountChart = ({ agencies }) => {
  const data = useMemo(() => {
    return agencies
      .filter((a) => a.word_count)
      .sort((a, b) => b.word_count - a.word_count)
      .slice(0, TOP_N)
      .map((a) => ({ name: a.short_name || a.name, longName: a.name, word_count: a.word_count }))
  }, [agencies])

  const ticks = useMemo(() => {
    if (data.length === 0) return []
    const max = data[0].word_count
    const step = Math.ceil(max / 12 / 1_000_000) * 1_000_000 || 500_000
    const result = []
    for (let v = 0; v <= max; v += step) result.push(v)
    return result
  }, [data])

  if (data.length === 0) {
    return <p className="text-sm text-gray-400">No word count data available</p>
  }

  return (
    <ResponsiveContainer width="100%" height={TOP_N * 32}>
      <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
        <XAxis
          type="number"
          ticks={ticks}
          tickFormatter={(v) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          fontSize={12}
        />
        <YAxis type="category" dataKey="name" width={60} fontSize={11} />
        <Tooltip
          formatter={(v) => v.toLocaleString()}
          labelFormatter={(_, payload) => payload[0]?.payload?.longName || _}
        />
        <Bar dataKey="word_count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default WordCountChart

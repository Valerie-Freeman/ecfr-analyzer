import { useState, useMemo } from "react"

const COLUMNS = [
  { key: "name", label: "Agency" },
  { key: "word_count", label: "Words", numeric: true },
  { key: "checksum", label: "Checksum" },
  { key: "computed_at", label: "Updated" },
]

const AgencyTable = ({ agencies, selectedSlug, onSelect }) => {
  const [sortField, setSortField] = useState("name")
  const [sortDir, setSortDir] = useState("asc")

  const handleSort = (key) => {
    if (sortField === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortField(key)
      setSortDir("asc")
    }
  }

  const sorted = useMemo(() => {
    const copy = [...agencies]
    copy.sort((a, b) => {
      let aVal = a[sortField]
      let bVal = b[sortField]
      if (aVal == null) return 1
      if (bVal == null) return -1
      if (typeof aVal === "string") aVal = aVal.toLowerCase()
      if (typeof bVal === "string") bVal = bVal.toLowerCase()
      if (aVal < bVal) return sortDir === "asc" ? -1 : 1
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1
      return 0
    })
    return copy
  }, [agencies, sortField, sortDir])

  const formatDate = (dateStr) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleDateString()
  }

  const arrow = (key) => {
    if (sortField !== key) return ""
    return sortDir === "asc" ? " \u25B2" : " \u25BC"
  }

  return (
    <div className="overflow-y-auto max-h-[70vh]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="text-left px-2 py-2 cursor-pointer hover:text-blue-600 whitespace-nowrap"
              >
                {col.label}{arrow(col.key)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr
              key={a.slug}
              onClick={() => onSelect(a.slug)}
              className={`cursor-pointer border-t hover:bg-blue-50 ${
                a.slug === selectedSlug ? "bg-blue-100" : ""
              }`}
            >
              <td className="px-2 py-1.5">{a.short_name || a.name}</td>
              <td className="px-2 py-1.5 tabular-nums">
                {a.word_count?.toLocaleString() ?? "-"}
              </td>
              <td className="px-2 py-1.5 font-mono text-xs">
                {a.checksum?.slice(0, 8) ?? "-"}
              </td>
              <td className="px-2 py-1.5 whitespace-nowrap">
                {formatDate(a.computed_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default AgencyTable

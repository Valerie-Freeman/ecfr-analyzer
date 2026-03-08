const formatDate = (dateStr) => {
  const [year, month, day] = dateStr.split("-")
  const date = new Date(year, month - 1, day)
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

const ChangeIndicator = ({ agencyDetail }) => {
  if (!agencyDetail || agencyDetail.checksum_changed === null) {
    return (
      <div className="bg-white rounded-xl shadow p-4 text-sm text-gray-400">
        Select an agency to view change status
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow p-4 flex items-center gap-4 text-base">
      <span className="font-normal">{agencyDetail.name}</span>
      <span className={`px-2 py-0.5 rounded-full text-sm font-medium ${
        agencyDetail.checksum_changed
          ? "bg-amber-100 text-amber-800"
          : "bg-green-100 text-green-800"
      }`}>
        {agencyDetail.checksum_changed ? "Changed" : "Unchanged"}
      </span>
      {agencyDetail.word_count_change !== null && (
        <span className={`text-sm ${
          agencyDetail.word_count_change > 0 ? "text-blue-600"
          : agencyDetail.word_count_change < 0 ? "text-red-600"
          : "text-gray-500"
        }`}>
          {agencyDetail.word_count_change > 0 ? "+" : ""}
          {agencyDetail.word_count_change.toLocaleString()} words
        </span>
      )}
      {agencyDetail.previous_data_date && agencyDetail.current_data_date && (
        <span className="text-sm text-gray-400">
          {formatDate(agencyDetail.previous_data_date)} vs {formatDate(agencyDetail.current_data_date)}
        </span>
      )}
    </div>
  )
}

export default ChangeIndicator

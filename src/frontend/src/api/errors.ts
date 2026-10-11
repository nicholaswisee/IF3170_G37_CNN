function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function formatApiError(status: number, detail: unknown): string {
  if (typeof detail === 'string' && detail.length > 0) return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!isRecord(item) || typeof item.msg !== 'string') return []
      const location = Array.isArray(item.loc)
        ? item.loc.filter((part): part is string | number => typeof part === 'string' || typeof part === 'number').slice(1).join('.')
        : ''
      return [location ? `${location}: ${item.msg}` : item.msg]
    })
    if (messages.length > 0) return messages.join('; ')
  }
  return `Request failed with status ${status}`
}

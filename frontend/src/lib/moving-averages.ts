export interface DatedValue {
  date: string
  value: number | null
}

export interface MovingAveragePoint {
  date: string
  value: number
}


export function parseIndicatorLengths(input: string): number[] {
  return Array.from(new Set(
    input
      .split(/[\s,;]+/)
      .map(value => Number(value))
      .filter(value => Number.isInteger(value) && value > 0 && value <= 10_000)
  )).sort((left, right) => left - right)
}


export function simpleMovingAverage(
  values: DatedValue[],
  length: number,
): MovingAveragePoint[] {
  if (!Number.isInteger(length) || length < 1) return []

  const result: MovingAveragePoint[] = []
  const window: number[] = []
  let sum = 0

  for (const point of values) {
    if (point.value == null || !Number.isFinite(point.value)) {
      window.length = 0
      sum = 0
      continue
    }

    window.push(point.value)
    sum += point.value
    if (window.length > length) sum -= window.shift() ?? 0
    if (window.length === length) {
      result.push({ date: point.date, value: sum / length })
    }
  }
  return result
}


export function exponentialMovingAverage(
  values: DatedValue[],
  length: number,
): MovingAveragePoint[] {
  if (!Number.isInteger(length) || length < 1) return []

  const valid = values.filter(
    (point): point is { date: string; value: number } => (
      point.value != null && Number.isFinite(point.value)
    )
  )
  if (valid.length < length) return []

  const seed = valid.slice(0, length).reduce((sum, point) => sum + point.value, 0) / length
  const result: MovingAveragePoint[] = [{ date: valid[length - 1].date, value: seed }]
  const multiplier = 2 / (length + 1)
  let previous = seed

  for (const point of valid.slice(length)) {
    previous = ((point.value - previous) * multiplier) + previous
    result.push({ date: point.date, value: previous })
  }
  return result
}

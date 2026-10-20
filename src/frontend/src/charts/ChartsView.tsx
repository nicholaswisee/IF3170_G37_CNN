import { useMemo, type ReactNode } from 'react'
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCompact } from '../copy/format'
import { palette } from '../theme'
import type { ExperimentResult } from '../types/experiment'
import { Icon } from '../ui/Icon'
import { bestScorePerRestart, progressLabel, restartStarts, toAnnealingSeries, toObjectiveSeries } from './chartData'

interface Series {
  name: string
  color: string
}

function ChartCard({ title, series, onExpand, children }: { title: string; series: Series[]; onExpand?: () => void; children: ReactNode }) {
  return (
    <figure className="chart-card">
      <figcaption className="chart-head">
        <b>{title}</b>
        {onExpand && <button className="icon-btn small" type="button" aria-label="Open larger charts" title="Open larger charts" onClick={onExpand}><Icon name="expand" size={16} /></button>}
      </figcaption>
      <ul className="legend">
        {series.map((item) => <li key={item.name}><i style={{ background: item.color }} aria-hidden="true" />{item.name}</li>)}
      </ul>
      {children}
    </figure>
  )
}

const tooltipStyle = {
  background: 'rgba(255, 255, 255, 0.92)',
  border: 'none',
  borderRadius: 14,
  boxShadow: '0 6px 20px rgba(30, 40, 60, 0.14)',
  fontSize: 12,
}

const formatValue = (value: unknown) => typeof value === 'number' ? formatCompact(value) : String(value)

interface ChartsViewProps {
  experiment: ExperimentResult
  /** Iteration number under the replay cursor. */
  cursor: number | null
  large?: boolean
  onExpand?: () => void
}

export function ChartsView({ experiment, cursor, large = false, onExpand }: ChartsViewProps) {
  const objective = useMemo(() => toObjectiveSeries(experiment.history, experiment.algorithm), [experiment])
  const annealing = useMemo(() => toAnnealingSeries(experiment.history), [experiment])
  const restarts = useMemo(() => restartStarts(experiment.history), [experiment])
  const perRestart = useMemo(() => bestScorePerRestart(experiment.metadata), [experiment])
  const worseCandidates = useMemo(() => annealing.filter((point) => point.probability !== null && point.probability < 1), [annealing])
  const dotRadius = large ? 2.2 : 1.6
  const probabilityDot = (props: unknown) => {
    const { cx, cy } = props as { cx?: number; cy?: number }
    return <circle cx={cx} cy={cy} r={dotRadius} fill={palette.teal} fillOpacity={0.55} />
  }
  const unit = progressLabel(experiment.algorithm)
  const height = large ? 260 : 150
  const isGenetic = experiment.algorithm === 'genetic_algorithm'
  const cursorPoint = cursor === null ? undefined : objective.find((point) => point.iteration === cursor)
  const xAxis = <XAxis dataKey="iteration" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: palette.inkMuted }} tickLine={false} axisLine={false} allowDecimals={false} />
  const yAxis = (domain?: [number, number]) => <YAxis width={44} domain={domain} tick={{ fontSize: 11, fill: palette.inkMuted }} tickLine={false} axisLine={false} tickFormatter={formatCompact} />
  const grid = <CartesianGrid vertical={false} stroke={palette.grid} />
  const tooltip = <Tooltip contentStyle={tooltipStyle} labelFormatter={(label) => `${unit} ${label}`} formatter={formatValue} />
  const cursorLine = cursor !== null && <ReferenceLine x={cursor} stroke={palette.ink} strokeOpacity={0.3} strokeDasharray="3 3" />

  if (objective.length === 0) return <p className="empty">This run recorded no history.</p>

  const objectiveSeries: Series[] = isGenetic
    ? [{ name: 'Max fitness', color: palette.accent }, { name: 'Mean fitness', color: palette.orange }]
    : [{ name: 'Current', color: palette.accent }, { name: 'Best', color: palette.indigo }]
  if (restarts.length > 0) objectiveSeries.push({ name: 'Restart', color: palette.inkMuted })

  return (
    <div className={large ? 'charts large' : 'charts'}>
      <ChartCard title={isGenetic ? 'Fitness' : 'Objective'} series={objectiveSeries} onExpand={onExpand}>
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart data={objective} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            {grid}{xAxis}{yAxis()}{tooltip}
            {restarts.map((iteration) => <ReferenceLine key={iteration} x={iteration} stroke={palette.inkMuted} strokeOpacity={0.8} strokeDasharray="2 3" />)}
            <Area type="monotone" dataKey="current" name={objectiveSeries[0].name} stroke={palette.accent} strokeWidth={2} fill={palette.accent} fillOpacity={0.1} dot={false} isAnimationActive={false} />
            {isGenetic
              ? <Line type="monotone" dataKey="mean" name="Mean fitness" stroke={palette.orange} strokeWidth={2} dot={false} isAnimationActive={false} />
              : <Line type="stepAfter" dataKey="best" name="Best" stroke={palette.indigo} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />}
            {cursorLine}
            {cursorPoint && cursorPoint.current !== null && <ReferenceDot x={cursorPoint.iteration} y={cursorPoint.current} r={4} fill="#ffffff" stroke={palette.accent} strokeWidth={2.4} />}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartCard>

      {experiment.algorithm === 'simulated_annealing' && (
        <>
          <ChartCard title="Temperature" series={[{ name: 'Temperature', color: palette.orange }]}>
            <ResponsiveContainer width="100%" height={height}>
              <LineChart data={annealing} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                {grid}{xAxis}{yAxis()}{tooltip}
                <Line type="monotone" dataKey="temperature" name="Temperature" stroke={palette.orange} strokeWidth={2} dot={false} isAnimationActive={false} />
                {cursorLine}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Acceptance probability" series={[{ name: 'exp(delta / T) of each worse candidate', color: palette.teal }]}>
            {worseCandidates.length === 0 ? <p className="empty">Every candidate in this run was at least as good, so each one was accepted.</p> : (
              <ResponsiveContainer width="100%" height={height}>
                <ComposedChart data={worseCandidates} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  {grid}
                  <XAxis dataKey="iteration" type="number" domain={[0, objective[objective.length - 1].iteration]} tick={{ fontSize: 11, fill: palette.inkMuted }} tickLine={false} axisLine={false} allowDecimals={false} />
                  {yAxis([0, 1])}{tooltip}
                  <Scatter dataKey="probability" name="Acceptance probability" shape={probabilityDot} isAnimationActive={false} />
                  {cursorLine}
                </ComposedChart>
              </ResponsiveContainer>
            )}
            <p className="caption">Better candidates always have probability 1, so only worse ones are plotted.</p>
          </ChartCard>
        </>
      )}

      {perRestart.length > 0 && (
        <ChartCard title="Best score per restart" series={[{ name: 'Highest', color: palette.accent }, { name: 'Other climbs', color: palette.restartBar }]}>
          <ResponsiveContainer width="100%" height={height}>
            <BarChart data={perRestart} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              {grid}
              <XAxis dataKey="restart" tick={{ fontSize: 11, fill: palette.inkMuted }} tickLine={false} axisLine={false} />
              {yAxis()}
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(label) => `Climb ${label}`} formatter={formatValue} />
              <Bar dataKey="score" name="Best score" radius={[5, 5, 0, 0]} isAnimationActive={false}>
                {perRestart.map((item) => (
                  <Cell key={item.restart} fill={item.score === Math.max(...perRestart.map((entry) => entry.score)) ? palette.accent : palette.restartBar} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  )
}

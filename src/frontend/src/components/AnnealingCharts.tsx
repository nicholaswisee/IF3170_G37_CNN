import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SearchEvent } from '../types/experiment'
import { sceneColors } from '../theme'
import { toAnnealingChartData } from './annealingChartData'

const charts = [
  { id: 'sa-objective', title: 'Current and best objective', series: [
    { key: 'current', label: 'Current objective', color: sceneColors.accent },
    { key: 'best', label: 'Best objective', color: sceneColors.cool },
  ] },
  { id: 'sa-temperature', title: 'Temperature', series: [
    { key: 'temperature', label: 'Temperature', color: sceneColors.accent },
  ] },
  { id: 'sa-probability', title: 'Acceptance probability', series: [
    { key: 'probability', label: 'Acceptance probability', color: sceneColors.cool },
  ] },
] as const

export function AnnealingCharts({ history }: { history: SearchEvent[] }) {
  const data = toAnnealingChartData(history)
  return (
    <section className="objective-chart" aria-label="Simulated annealing history">
      <div className="panel-heading">
        <span className="panel-index">03</span>
        <h2>Simulated annealing traces</h2>
      </div>
      {charts.map((chart) => (
        <section key={chart.id} aria-labelledby={chart.id}>
          <h3 id={chart.id}>{chart.title}</h3>
          <ul className="chart-legend">
            {chart.series.map((series) => <li key={series.key}><span aria-hidden="true" style={{ background: series.color }} />{series.label}</li>)}
          </ul>
          <div className="chart-frame">
            {data.length === 0 && <p className="chart-empty">This run recorded no history.</p>}
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
                <CartesianGrid stroke={sceneColors.grid} strokeDasharray="3 3" />
                <XAxis dataKey="iteration" stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} label={{ value: 'Iteration', position: 'insideBottom', offset: -4, fill: sceneColors.inkMuted }} />
                <YAxis domain={chart.id === 'sa-probability' ? [0, 1] : [0, 'auto']} stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: sceneColors.panel, border: `1px solid ${sceneColors.gridMajor}`, borderRadius: 0 }} />
                {chart.series.map((series) => <Line key={series.key} type="linear" dataKey={series.key} name={series.label} stroke={series.color} strokeWidth={2} dot={data.length === 1} connectNulls={false} isAnimationActive={false} />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ))}
    </section>
  )
}

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useReplayStore } from '../stores/replayStore'
import { sceneColors } from '../theme'

export function ObjectiveChart() {
  const experiment = useReplayStore((state) => state.experiment)
  const data = experiment?.history.map((event) => ({ iteration: event.iteration, objective: event.current_score })) ?? []
  const emptyMessage = !experiment
    ? 'Run an experiment to populate the objective trace.'
    : experiment.metadata.placeholder === true
      ? 'The search algorithm still a placeholder.'
      : 'This run recorded no history.'

  return (
    <section className="objective-chart" aria-labelledby="chart-heading">
      <div className="panel-heading">
        <span className="panel-index">03</span>
        <h2 id="chart-heading">Objective trace</h2>
      </div>
      <div className="chart-frame">
        {data.length === 0 && <p className="chart-empty">{emptyMessage}</p>}
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={sceneColors.grid} strokeDasharray="3 3" />
            <XAxis dataKey="iteration" stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} />
            <YAxis stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: sceneColors.panel, border: `1px solid ${sceneColors.gridMajor}`, borderRadius: 0 }} />
            <Line type="monotone" dataKey="objective" stroke={sceneColors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

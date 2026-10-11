import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useReplayStore } from '../stores/replayStore'
import { sceneColors } from '../theme'
import { progressLabelForAlgorithm, toObjectiveChartData } from './objectiveChartData'

export function ObjectiveChart() {
  const experiment = useReplayStore((state) => state.experiment)
  const isGeneticAlgorithm = experiment?.algorithm === 'genetic_algorithm'
  const data = experiment ? toObjectiveChartData(experiment.history, experiment.algorithm) : []
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
      {isGeneticAlgorithm && (
        <ul className="chart-legend" aria-label="Objective trace series">
          <li><span aria-hidden="true" style={{ background: sceneColors.accent }} />Generation maximum</li>
          <li><span aria-hidden="true" style={{ background: sceneColors.cool }} />Generation mean</li>
        </ul>
      )}
      <div className="chart-frame">
        {data.length === 0 && <p className="chart-empty">{emptyMessage}</p>}
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={sceneColors.grid} strokeDasharray="3 3" />
            <XAxis dataKey="generation" stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} label={{ value: progressLabelForAlgorithm(experiment?.algorithm), position: 'insideBottom', offset: -4, fill: sceneColors.inkMuted }} />
            <YAxis stroke={sceneColors.inkMuted} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ background: sceneColors.panel, border: `1px solid ${sceneColors.gridMajor}`, borderRadius: 0 }} />
            <Line type="monotone" dataKey="maximum" name={isGeneticAlgorithm ? 'Generation maximum' : 'Objective'} stroke={sceneColors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
            {isGeneticAlgorithm && <Line type="monotone" dataKey="mean" name="Generation mean" stroke={sceneColors.cool} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

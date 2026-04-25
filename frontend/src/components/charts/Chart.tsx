import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { ChartSpec } from '@/types'

const COLORS = ['#004977', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2', '#00B8D9', '#A78BFA']

const tooltipStyle = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 11,
  fontFamily: 'JetBrains Mono, monospace',
  color: 'var(--text-primary)',
}

interface Props {
  spec: ChartSpec
  height?: number
}

export default function Chart({ spec, height = 240 }: Props) {
  const { type, data, x_key, y_keys } = spec

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip contentStyle={tooltipStyle} />
          {y_keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {y_keys.map((k, i) => (
            <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 2.5 }} activeDot={{ r: 5 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <defs>
            {y_keys.map((k, i) => (
              <linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.45} />
                <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip contentStyle={tooltipStyle} />
          {y_keys.map((k, i) => (
            <Area key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} fill={`url(#grad-${k})`} strokeWidth={2} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'bar' || type === 'stacked_bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip contentStyle={tooltipStyle} />
          {y_keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {y_keys.map((k, i) => (
            <Bar
              key={k}
              dataKey={k}
              fill={COLORS[i % COLORS.length]}
              stackId={type === 'stacked_bar' ? 'a' : undefined}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey={y_keys[0]}
            nameKey={x_key}
            cx="50%"
            cy="50%"
            outerRadius={Math.min(80, height / 2 - 20)}
            innerRadius={Math.min(40, height / 4)}
            paddingAngle={2}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'scatter') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
          <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <YAxis dataKey={y_keys[0]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Scatter data={data} fill={COLORS[0]} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  return null
}

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export default function AntiConsensusChart({ data }) {
  if (!data?.length) {
    return (
      <div className="text-center py-8 text-gray-600 text-sm">
        No anti-consensus data available
      </div>
    );
  }

  const chartData = data.slice(0, 15).map((d) => ({
    name: d.name?.split(' ').pop() || d.name,
    fullName: d.name,
    model: (d.model_win_prob || 0) * 100,
    consensus: (d.consensus_win_prob || 0) * 100,
    undervalued: (d.model_win_prob || 0) > (d.consensus_win_prob || 0),
  }));

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
          barGap={2}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: '#9ca3af' }}
            angle={-45}
            textAnchor="end"
            height={60}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#6b7280' }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(val, name) => [
              `${val.toFixed(1)}%`,
              name === 'model' ? 'Model Prob' : 'Consensus Prob',
            ]}
            labelFormatter={(label, payload) =>
              payload?.[0]?.payload?.fullName || label
            }
          />
          <Legend
            wrapperStyle={{ fontSize: '11px' }}
            formatter={(val) =>
              val === 'model' ? 'Model Probability' : 'Consensus Probability'
            }
          />
          <Bar dataKey="model" fill="#006747" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.undervalued ? '#006747' : '#374151'}
              />
            ))}
          </Bar>
          <Bar dataKey="consensus" fill="#6b7280" radius={[3, 3, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.undervalued ? '#9ca3af' : '#ef4444'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

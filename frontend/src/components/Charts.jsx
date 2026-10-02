import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const axis = { stroke: "var(--muted)", fontSize: 11, tickLine: false, axisLine: false };
const tip = { contentStyle: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12, color: "var(--text)" } };
const shortDate = (d) => d.slice(5);
const fmt = (v) => (v === null || v === undefined ? "N/A" : Number(v).toLocaleString());

// 하나의 y축만 사용 (서로 다른 단위는 차트를 분리)
export function TrendLines({ data, series, height = 240 }) {
  return (
    <div className="chart-box" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} {...axis} />
          <YAxis {...axis} width={48} tickFormatter={(v) => Number(v).toLocaleString()} />
          <Tooltip {...tip} formatter={(v) => fmt(v)} labelFormatter={(l) => l} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-2)" }} />}
          {series.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Bars({ data, dataKey, name, color = "var(--series-1)", height = 240 }) {
  return (
    <div className="chart-box" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} {...axis} />
          <YAxis {...axis} width={56} tickFormatter={(v) => Number(v).toLocaleString()} />
          <Tooltip {...tip} formatter={(v) => fmt(v)} cursor={{ fill: "var(--surface-2)" }} />
          <Bar dataKey={dataKey} name={name} fill={color} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

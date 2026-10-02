import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Bars, TrendLines } from "../components/Charts";
import { Empty, Kpi, MockBadge, PlatformBadge, StatusBadge } from "../components/ui";
import { fmtTime, num, pct } from "../util";

export default function Dashboard({ status }) {
  const [d, setD] = useState(null);
  const [showTable, setShowTable] = useState(false);
  useEffect(() => {
    api.get("/api/dashboard?days=14").then(setD).catch(() => setD({ error: true }));
  }, []);
  if (!d) return <p>불러오는 중…</p>;
  if (d.error) return <div className="banner bad">대시보드를 불러오지 못했습니다.</div>;
  const c = d.cards;
  const a = d.ads_7d;
  const anyPosts = d.series.some((s) => s.posts > 0);
  const anyContent = d.series.some((s) => s.impressions !== null || s.views !== null || s.engagement !== null);
  const noMetricsMsg = anyPosts ? "게시물은 있지만 아직 성과 데이터가 수집되지 않았습니다 (매시 10분 자동 수집)." : "아직 게시된 콘텐츠가 없습니다.";
  const anyAds = d.series.some((s) => s.ad_spend !== null);
  return (
    <>
      <div className="topbar">
        <div>
          <h1>대시보드</h1>
          <div className="muted small">{d.today} · AI {status.ai_mode === "claude" ? "Claude" : "Mock"}</div>
        </div>
        <div className="row">
          <Link to="/approvals"><button className="primary">승인 대기 {c.pending_review}건 검토</button></Link>
        </div>
      </div>

      <div className="grid kpi" style={{ marginBottom: 16 }}>
        <Kpi label="오늘 게시 예정" value={c.today_scheduled} />
        <Kpi label="오늘 게시 완료" value={c.published_today} />
        <Kpi label="게시 실패" value={c.failed} sub={c.failed ? "콘텐츠 메뉴에서 확인" : ""} />
        <Kpi label="승인 대기" value={c.pending_review} sub={c.pending_ad_actions ? `광고 작업 ${c.pending_ad_actions}건` : ""} />
        <Kpi label="이번 주 콘텐츠" value={c.week_content} />
      </div>
      <h2>광고 (최근 7일) <MockBadge show={a.mock_data} /></h2>
      <div className="grid kpi" style={{ marginBottom: 16 }}>
        <Kpi label="광고 지출" value={num(a.spend)} />
        <Kpi label="CTR" value={pct(a.ctr)} />
        <Kpi label="CPC" value={num(a.cpc, 1)} />
        <Kpi label="CPA" value={num(a.cpa, 1)} />
        <Kpi label="ROAS" value={a.roas === null ? "N/A" : `${a.roas.toFixed(2)}x`} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>노출 · 조회 추이 (14일)</h2>
          {anyContent ? (
            <TrendLines data={d.series} series={[{ key: "impressions", name: "노출", color: "var(--series-1)" }, { key: "views", name: "조회", color: "var(--series-2)" }]} />
          ) : <Empty>{noMetricsMsg}</Empty>}
        </div>
        <div className="card">
          <h2>참여 수 추이 (좋아요+댓글+공유+저장)</h2>
          {anyContent ? <TrendLines data={d.series} series={[{ key: "engagement", name: "참여", color: "var(--series-3)" }]} /> : <Empty>{noMetricsMsg}</Empty>}
        </div>
        <div className="card">
          <h2>일별 광고 지출</h2>
          {anyAds ? <Bars data={d.series} dataKey="ad_spend" name="지출" /> : <Empty>광고 데이터 없음 — 광고 메뉴에서 [데이터 가져오기]</Empty>}
        </div>
        <div className="card">
          <h2>오늘 게시 예정</h2>
          {d.today_items.length === 0 ? <Empty>오늘 예약된 게시물이 없습니다.</Empty> : (
            <table>
              <tbody>
                {d.today_items.map((it) => (
                  <tr key={it.id}>
                    <td>{fmtTime(it.scheduled_at)}</td>
                    <td><PlatformBadge p={it.platform} /></td>
                    <td>{it.title}</td>
                    <td><StatusBadge s={it.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <button className="link small" onClick={() => setShowTable(!showTable)}>{showTable ? "표 숨기기" : "차트 데이터를 표로 보기"}</button>
      {showTable && (
        <div className="card table-wrap" style={{ marginTop: 8 }}>
          <table>
            <thead><tr><th>날짜</th><th className="num">게시</th><th className="num">노출</th><th className="num">조회</th><th className="num">참여</th><th className="num">광고 지출</th><th className="num">광고 클릭</th></tr></thead>
            <tbody>
              {d.series.map((s) => (
                <tr key={s.date}><td>{s.date}</td><td className="num">{s.posts}</td><td className="num">{num(s.impressions)}</td><td className="num">{num(s.views)}</td><td className="num">{num(s.engagement)}</td><td className="num">{num(s.ad_spend)}</td><td className="num">{num(s.ad_clicks)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

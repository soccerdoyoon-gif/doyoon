import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Bars, TrendLines } from "../components/Charts";
import { Empty, Kpi, MockBadge, PlatformBadge, StatusBadge } from "../components/ui";
import { t } from "../i18n";
import { fmtTime, num, pct, tzLabel, yen } from "../util";

export default function Dashboard({ status }) {
  const [d, setD] = useState(null);
  const [showTable, setShowTable] = useState(false);
  useEffect(() => {
    api.get("/api/dashboard?days=14").then(setD).catch(() => setD({ error: true }));
  }, []);
  if (!d) return <p>…</p>;
  if (d.error) return <div className="banner bad">{t("대시보드를 불러오지 못했습니다.")}</div>;
  const c = d.cards;
  const a = d.ads_7d;
  const anyPosts = d.series.some((s) => s.posts > 0);
  const anyContent = d.series.some((s) => s.impressions !== null || s.views !== null || s.engagement !== null);
  const anyAds = d.series.some((s) => s.ad_spend !== null);
  const noMetricsMsg = anyPosts ? t("게시물은 있지만 아직 성과 데이터가 수집되지 않았습니다 (매시 10분 자동 수집).") : t("아직 게시된 콘텐츠가 없습니다.");
  return (
    <>
      <div className="topbar">
        <div>
          <h1>{t("대시보드")}</h1>
          <div className="muted small">{d.today} ({tzLabel()}) · AI {status.ai_mode === "claude" ? "Claude" : "Mock"}</div>
        </div>
        <div className="row">
          <Link to="/content"><button>✨ {t("AI 콘텐츠 제작")}</button></Link>
          <Link to="/approvals"><button className="primary">{t("승인 대기 {n}건 검토", { n: c.pending_review })}</button></Link>
        </div>
      </div>

      <div className="grid kpi" style={{ marginBottom: 16 }}>
        <Kpi label={t("오늘의 게시 예정")} value={c.today_scheduled} />
        <Kpi label={t("게시 완료")} value={c.published_today} sub={t("오늘")} />
        <Kpi label={t("게시 실패")} value={c.failed} sub={c.failed ? t("콘텐츠 메뉴에서 확인") : ""} />
        <Kpi label={t("승인 대기")} value={c.pending_review} sub={c.pending_ad_actions ? t("광고 작업 {n}건", { n: c.pending_ad_actions }) : ""} />
        <Kpi label={t("이번 주 콘텐츠")} value={c.week_content} />
      </div>
      <h2>{t("광고 (최근 7일)")} <MockBadge show={a.mock_data} /></h2>
      <div className="grid kpi" style={{ marginBottom: 16 }}>
        <Kpi label={t("광고비")} value={yen(a.spend)} />
        <Kpi label={t("클릭률")} value={pct(a.ctr)} />
        <Kpi label="CPC" value={yen(a.cpc)} />
        <Kpi label={t("전환")} value={num(a.conversions)} />
        <Kpi label="CPA" value={yen(a.cpa)} />
        <Kpi label={t("매출")} value={yen(a.conversion_value)} />
        <Kpi label="ROAS" value={a.roas === null ? "N/A" : a.roas.toFixed(2)} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <div className="spread"><h2>🤖 {t("AI 분석")} <MockBadge show={d.ai.source && d.ai.source !== "ai"} label="MOCK AI" /></h2><Link className="small" to="/trends">{t("트렌드 보기")} →</Link></div>
          {!d.ai.content_summary && !d.ai.ads_summary && !d.ai.trend_summary ? <Empty>{t("아직 AI 분석이 없습니다 (매일 06:30 자동).")}</Empty> : (
            <div className="small stack">
              {d.ai.trend_summary && <p>📈 {d.ai.trend_summary}</p>}
              {d.ai.content_summary && <p>📝 {d.ai.content_summary}</p>}
              {d.ai.ads_summary && <p>💰 {d.ai.ads_summary}</p>}
            </div>
          )}
        </div>
        <div className="card">
          <h2>💡 {t("다음 추천 액션")}</h2>
          {d.ai.next_actions.length === 0 ? <Empty>{t("성과 데이터가 쌓이면 AI 가 다음 액션을 제안합니다.")}</Empty> : (
            <ul className="small">{d.ai.next_actions.map((x, i) => <li key={i}>{x}</li>)}</ul>
          )}
        </div>
        <div className="card">
          <h2>{t("노출 · 조회 추이 (14일)")}</h2>
          {anyContent ? (
            <TrendLines data={d.series} series={[{ key: "impressions", name: t("노출"), color: "var(--series-1)" }, { key: "views", name: t("조회"), color: "var(--series-2)" }]} />
          ) : <Empty>{noMetricsMsg}</Empty>}
        </div>
        <div className="card">
          <h2>{t("참여 수 추이 (좋아요+댓글+공유+저장)")}</h2>
          {anyContent ? <TrendLines data={d.series} series={[{ key: "engagement", name: t("참여"), color: "var(--series-3)" }]} /> : <Empty>{noMetricsMsg}</Empty>}
        </div>
        <div className="card">
          <h2>{t("일별 광고비")}</h2>
          {anyAds ? <Bars data={d.series} dataKey="ad_spend" name={t("광고비")} money /> : <Empty>{t("광고 데이터 없음 — 광고 메뉴에서 [데이터 가져오기]")}</Empty>}
        </div>
        <div className="card">
          <h2>{t("오늘의 게시 예정")} ({tzLabel()})</h2>
          {d.today_items.length === 0 ? <Empty>{t("오늘 예약된 게시물이 없습니다.")}</Empty> : (
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
      <button className="link small" onClick={() => setShowTable(!showTable)}>{showTable ? t("표 숨기기") : t("차트 데이터를 표로 보기")}</button>
      {showTable && (
        <div className="card table-wrap" style={{ marginTop: 8 }}>
          <table>
            <thead><tr><th>{t("날짜")}</th><th className="num">{t("게시")}</th><th className="num">{t("노출")}</th><th className="num">{t("조회")}</th><th className="num">{t("참여")}</th><th className="num">{t("광고비")}</th><th className="num">{t("광고 클릭")}</th></tr></thead>
            <tbody>
              {d.series.map((s) => (
                <tr key={s.date}><td>{s.date}</td><td className="num">{s.posts}</td><td className="num">{num(s.impressions)}</td><td className="num">{num(s.views)}</td><td className="num">{num(s.engagement)}</td><td className="num">{yen(s.ad_spend)}</td><td className="num">{num(s.ad_clicks)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, MockBadge, useAction } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, PLATFORMS, tzLabel } from "../util";

const PLAT_TREND = { tiktok: "TikTok", instagram_reels: "Instagram Reels", x: "X", youtube_shorts: "YouTube Shorts" };

export default function Trends() {
  const [trend, setTrend] = useState(null);
  const [pt, setPt] = useState(null);
  const [theme, setTheme] = useState("");
  const [run, busy] = useAction();
  const load = async () => {
    const [tr, p] = await Promise.all([api.get("/api/trends"), api.get("/api/posting-times")]);
    setTrend(tr);
    setPt(p);
  };
  useEffect(() => {
    load();
  }, []);
  const d = trend?.data;
  const learned = pt?.learned?.data?.platforms || {};
  return (
    <>
      <div className="topbar">
        <div><h1>{t("일본 트렌드 · 게시 시간")}</h1><div className="muted small">{t("우선순위: 일본 TikTok → Instagram Reels → X → YouTube Shorts. 해외 트렌드는 일본에서 통하는지 다시 판단합니다.")}</div></div>
        <div className="row">
          <input value={theme} onChange={(e) => setTheme(e.target.value)} placeholder={t("조사 주제 (선택)")} style={{ width: 200 }} />
          <button className="primary" disabled={busy} onClick={() => run(() => api.post(`/api/trends/research?theme=${encodeURIComponent(theme)}`), t("트렌드 조사 완료")).then(load)}>🔍 {t("지금 조사")}</button>
        </div>
      </div>
      <div className="card">
        {!d ? <Empty>{t("아직 트렌드 조사가 없습니다. 콘텐츠 제작 시 자동으로 조사합니다 (하루 1회).")}</Empty> : (
          <>
            <div className="spread">
              <h2>📈 {t("트렌드 리포트")} <MockBadge show={trend.source !== "ai"} label="MOCK AI" />
                <span className={`badge ${d.evidence === "web_search" ? "s-EXECUTED" : "v-watch"}`}>{d.evidence === "web_search" ? t("웹 검색 근거") : t("일반 지식 (미검증)")}</span></h2>
              <span className="small muted">{fmtDateTime(trend.created_at)} {tzLabel()}</span>
            </div>
            <p>{d.summary}</p>
            <div className="grid cols-2">
              {(d.platform_trends || []).map((p, i) => (
                <div key={i} className="content-card small">
                  <h3>{PLAT_TREND[p.platform] || p.platform}</h3>
                  {[["formats", "인기 형식"], ["hooks", "반응 좋은 Hook"], ["expressions", "자주 쓰는 표현"], ["hashtags", "Hashtag"], ["ctas", "반응 좋은 CTA"]].map(([k, l]) =>
                    (p[k] || []).length > 0 && <div key={k}><b>{t(l)}</b>: {p[k].join(" / ")}</div>)}
                  {p.ideal_video_length && p.ideal_video_length !== "-" && <div><b>{t("영상 길이")}</b>: {p.ideal_video_length}</div>}
                  {p.notes && <div className="hint">{p.notes}</div>}
                </div>
              ))}
            </div>
            {(d.competitor_styles || []).length > 0 && <><h3 style={{ marginTop: 12 }}>{t("일본 경쟁사 스타일")}</h3><ul className="small">{d.competitor_styles.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
            {(d.global_trends_applicability || []).length > 0 && <><h3>{t("글로벌 트렌드의 일본 적용 가능성")}</h3><ul className="small">{d.global_trends_applicability.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
            {d.data_limitations && <p className="hint">⚠️ {d.data_limitations}</p>}
            {(d.sources || []).length > 0 && (
              <details><summary className="small">{t("출처")} ({d.sources.length})</summary>
                <ul className="small">{d.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title || s.url}</a></li>)}</ul></details>
            )}
          </>
        )}
      </div>
      <div className="card">
        <div className="spread">
          <h2>⏰ {t("게시 시간 분석")} ({tzLabel()})</h2>
          <button className="sm" disabled={busy} onClick={() => run(() => api.post("/api/posting-times/learn"), t("분석 완료")).then(load)}>{t("지금 다시 학습")}</button>
        </div>
        <p className="small muted">{t("우리 계정의 실제 성과만 사용합니다 (mock 데이터 제외). 데이터가 부족하면 7-9시 / 12-13시 / 18-22시를 테스트 후보로만 사용하고, 계속 업데이트합니다.")}</p>
        <div className="table-wrap"><table>
          <thead><tr><th>SNS</th><th>{t("상태")}</th><th>{t("추천 시간")}</th><th>{t("테스트 후보")}</th><th>{t("시간대별 평균 ER (게시 수)")}</th></tr></thead>
          <tbody>{Object.keys(PLATFORMS).map((p) => {
            const l = learned[p];
            return (
              <tr key={p}><td>{PLATFORMS[p]}</td>
                <td>{l ? <span className={`badge ${l.status === "learned" ? "s-EXECUTED" : "v-watch"}`}>{l.status === "learned" ? t("학습됨") : t("테스트 중")}</span> : "-"}</td>
                <td>{(l?.recommended || []).join(", ") || "-"}</td>
                <td>{(l?.test_candidates || pt?.candidates?.[p] || []).join(", ")}</td>
                <td className="small">{l ? Object.entries(l.hour_stats).map(([h, v]) => `${h}時 ${v.avg_er}% (${v.posts})`).join(" · ") || t("데이터 없음") : "-"}</td></tr>
            );
          })}</tbody>
        </table></div>
      </div>
    </>
  );
}

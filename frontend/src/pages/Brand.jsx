import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, ListInput, MockBadge, useAction } from "../components/ui";
import { fmtDateTime } from "../util";

export default function Brand() {
  const [b, setB] = useState(null);
  const [camps, setCamps] = useState([]);
  const [strategy, setStrategy] = useState(null);
  const [insight, setInsight] = useState(null);
  const [newCamp, setNewCamp] = useState({ name: "", objective: "", notes: "" });
  const [run, busy] = useAction();
  const load = async () => {
    const [brand, c, s, i] = await Promise.all([api.get("/api/brand"), api.get("/api/campaigns"), api.get("/api/insights?kind=strategy&limit=1"), api.get("/api/insights?kind=content&limit=1")]);
    setB(brand); setCamps(c); setStrategy(s[0] || null); setInsight(i[0] || null);
  };
  useEffect(() => {
    load();
  }, []);
  if (!b) return <p>불러오는 중…</p>;
  const f = (k) => ({ value: b[k] ?? "", onChange: (e) => setB({ ...b, [k]: e.target.value }) });
  const save = () => {
    const keys = ["brand_name", "brand_description", "product_description", "target_customer", "country", "language", "brand_voice", "brand_values", "forbidden_words", "preferred_words", "competitors", "main_goal", "main_products", "website_url"];
    return run(() => api.put("/api/brand", Object.fromEntries(keys.map((k) => [k, b[k]]))), "브랜드 프로필을 저장했습니다");
  };
  return (
    <>
      <div className="topbar"><div><h1>브랜드 프로필 (Brand Memory)</h1><div className="muted small">AI 가 모든 콘텐츠/광고/분석에서 항상 이 정보를 사용합니다.</div></div>
        <button className="primary" disabled={busy} onClick={save}>💾 저장</button></div>
      <div className="grid cols-2">
        <div className="card">
          <div className="field"><label>brand_name</label><input {...f("brand_name")} /></div>
          <div className="field"><label>brand_description</label><textarea {...f("brand_description")} /></div>
          <div className="field"><label>product_description</label><textarea {...f("product_description")} /></div>
          <div className="field"><label>주요 판매 제품</label><input {...f("main_products")} /></div>
          <div className="field"><label>target_customer</label><textarea {...f("target_customer")} /></div>
          <div className="field"><label>website</label><input {...f("website_url")} /></div>
        </div>
        <div className="card">
          <div className="grid cols-3">
            <div className="field"><label>country</label><input {...f("country")} /></div>
            <div className="field"><label>language</label><select {...f("language")}><option value="ko">한국어</option><option value="ja">日本語</option><option value="en">English</option></select></div>
            <div className="field"><label>main_goal</label><select {...f("main_goal")}><option value="sales">sales</option><option value="followers">followers</option><option value="website_traffic">website_traffic</option><option value="brand_awareness">brand_awareness</option></select></div>
          </div>
          <div className="field"><label>brand_voice</label><input {...f("brand_voice")} /></div>
          <div className="field"><label>brand_values</label><input {...f("brand_values")} /></div>
          <div className="field"><label>forbidden_words</label><ListInput value={b.forbidden_words} onChange={(v) => setB({ ...b, forbidden_words: v })} /></div>
          <div className="field"><label>preferred_words</label><ListInput value={b.preferred_words} onChange={(v) => setB({ ...b, preferred_words: v })} /></div>
          <div className="field"><label>competitors</label><ListInput value={b.competitors} onChange={(v) => setB({ ...b, competitors: v })} /></div>
        </div>
      </div>
      <div className="grid cols-2">
        <div className="card">
          <div className="spread"><h2>AI 콘텐츠 전략 <MockBadge show={strategy && strategy.source !== "ai"} label="MOCK AI" /></h2>
            <button className="sm" disabled={busy} onClick={() => run(() => api.post("/api/strategy"), "전략을 생성했습니다").then(load)}>✨ 전략 다시 생성</button></div>
          {!strategy ? <Empty>아직 전략이 없습니다.</Empty> : (
            <div className="small">
              <p>{strategy.data.summary}</p>
              {[["content_pillars", "콘텐츠 기둥"], ["weekly_plan", "주간 계획"], ["platform_strategy", "플랫폼별 전략"], ["kpis_to_watch", "KPI"]].map(([k, l]) => (
                <div key={k}><b>{l}</b><ul>{(strategy.data[k] || []).map((x, i) => <li key={i}>{x}</li>)}</ul></div>
              ))}
              <p className="hint">{fmtDateTime(strategy.created_at)}</p>
            </div>
          )}
        </div>
        <div className="card">
          <div className="spread"><h2>최신 AI 성과 분석 <MockBadge show={insight && insight.source !== "ai"} label="MOCK AI" /></h2>
            <button className="sm" disabled={busy} onClick={() => run(() => api.post("/api/analytics/analyze"), "분석 완료").then(load)}>🔍 지금 분석</button></div>
          {!insight ? <Empty>아직 분석이 없습니다 (매일 06:30 자동).</Empty> : (
            <div className="small">
              <p>{insight.data.summary}</p>
              {[["top_content", "성과 좋은 콘텐츠"], ["low_content", "성과 낮은 콘텐츠"], ["hook_patterns", "좋은 Hook"], ["caption_patterns", "좋은 Caption"], ["cta_patterns", "좋은 CTA"], ["topics", "좋은 주제"], ["best_posting_times", "좋은 게시 시간"], ["platform_differences", "플랫폼별 차이"], ["recommendations_for_next_content", "다음 콘텐츠 개선 (자동 반영)"]].map(([k, l]) =>
                (insight.data[k] || []).length > 0 && <div key={k}><b>{l}</b><ul>{insight.data[k].map((x, i) => <li key={i}>{x}</li>)}</ul></div>)}
              {insight.data.data_limitations && <p className="hint">⚠️ {insight.data.data_limitations}</p>}
            </div>
          )}
        </div>
      </div>
      <div className="card">
        <h2>캠페인</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <input placeholder="캠페인 이름" value={newCamp.name} onChange={(e) => setNewCamp({ ...newCamp, name: e.target.value })} style={{ maxWidth: 220 }} />
          <input placeholder="목표" value={newCamp.objective} onChange={(e) => setNewCamp({ ...newCamp, objective: e.target.value })} style={{ maxWidth: 260 }} />
          <input placeholder="메모 (AI 참고)" value={newCamp.notes} onChange={(e) => setNewCamp({ ...newCamp, notes: e.target.value })} style={{ maxWidth: 300 }} />
          <button disabled={!newCamp.name || busy} onClick={() => run(() => api.post("/api/campaigns", newCamp), "추가했습니다").then(() => { setNewCamp({ name: "", objective: "", notes: "" }); load(); })}>＋ 추가</button>
        </div>
        {camps.length === 0 ? <Empty>진행 중인 캠페인이 없습니다.</Empty> : (
          <table><thead><tr><th>이름</th><th>목표</th><th>메모</th><th>상태</th><th></th></tr></thead><tbody>
            {camps.map((c) => (
              <tr key={c.id}><td>{c.name}</td><td>{c.objective}</td><td className="small">{c.notes}</td><td>{c.is_active ? "진행 중" : "종료"}</td>
                <td><button className="sm" onClick={() => run(() => api.put(`/api/campaigns/${c.id}`, { ...c, is_active: !c.is_active })).then(load)}>{c.is_active ? "종료" : "재개"}</button></td></tr>
            ))}</tbody></table>
        )}
      </div>
    </>
  );
}

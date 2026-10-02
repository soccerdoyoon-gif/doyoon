import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Modal, StatusBadge, useAction } from "../components/ui";

const VAR = { hook: "Hook", caption: "Caption", cta: "CTA", thumbnail: "Thumbnail", video_opening: "Video opening" };
const MET = { ctr: "CTR (클릭/노출)", engagement_rate: "참여율 (참여/노출)", conversion_rate: "전환율 (전환/클릭)" };
const VERDICT = { insufficient_data: "데이터 부족 — 결론 보류", no_significant_difference: "유의한 차이 없음", significant: "유의한 차이 있음" };

export default function ABTests() {
  const [tests, setTests] = useState([]);
  const [results, setResults] = useState({});
  const [form, setForm] = useState(null);
  const [run, busy] = useAction();
  const load = () => api.get("/api/abtests").then(setTests);
  useEffect(() => {
    load();
  }, []);
  const evaluate = async (id) => {
    const r = await run(() => api.post(`/api/abtests/${id}/evaluate`));
    if (r) { setResults({ ...results, [id]: r }); load(); }
  };
  const saveVariant = (t, v, k, val) => {
    const body = { impressions: v.impressions, clicks: v.clicks, engagements: v.engagements, conversions: v.conversions, [k]: Math.max(0, Number(val) || 0) };
    return api.put(`/api/abtests/${t.id}/variants/${v.id}`, body).then(load);
  };
  return (
    <>
      <div className="topbar">
        <div><h1>A/B 테스트</h1><div className="muted small">변형당 최소 1,000 노출 · 30 회 성공(클릭 등)이 모이기 전에는 결론을 내리지 않습니다. 콘텐츠와 연결하면 성과가 자동 반영됩니다.</div></div>
        <button className="primary" onClick={() => setForm({ name: "", platform: "instagram", variable: "hook", metric: "ctr", hypothesis: "", variant_a: "", variant_b: "", content_id_a: "", content_id_b: "" })}>＋ 새 테스트</button>
      </div>
      {tests.length === 0 ? <Empty>테스트가 없습니다.</Empty> : tests.map((t) => {
        const r = results[t.id];
        return (
          <div key={t.id} className="card">
            <div className="spread">
              <h2>{t.name} <span className="badge">{VAR[t.variable]}</span> <span className="badge">{MET[t.metric]}</span> <StatusBadge s={t.status === "RUNNING" ? "PENDING" : "EXECUTED"} /></h2>
              <div className="row">
                <button className="sm primary" disabled={busy} onClick={() => evaluate(t.id)}>📊 결과 비교</button>
                <button className="sm danger" onClick={() => window.confirm("테스트를 삭제할까요?") && run(() => api.del(`/api/abtests/${t.id}`)).then(load)}>삭제</button>
              </div>
            </div>
            {t.hypothesis && <p className="small muted">가설: {t.hypothesis}</p>}
            <div className="table-wrap"><table>
              <thead><tr><th>변형</th><th>설명</th><th>연결 콘텐츠</th><th className="num">노출</th><th className="num">클릭</th><th className="num">참여</th><th className="num">전환</th></tr></thead>
              <tbody>{t.variants.map((v) => (
                <tr key={v.id}><td><b>{v.label}</b></td><td>{v.description}</td><td>{v.content_id ? `#${v.content_id}` : "-"}</td>
                  {["impressions", "clicks", "engagements", "conversions"].map((k) => (
                    <td key={k} className="num"><input type="number" min="0" defaultValue={v[k]} style={{ width: 96, textAlign: "right" }} onBlur={(e) => Number(e.target.value) !== v[k] && saveVariant(t, v, k, e.target.value)} /></td>
                  ))}</tr>
              ))}</tbody>
            </table></div>
            {(r || t.conclusion) && (
              <div className={`banner ${r?.result.verdict === "significant" ? "good" : "info"}`} style={{ marginTop: 10 }}>
                {r && <div><b>{VERDICT[r.result.verdict]}</b>{r.result.p_value != null && ` · p=${r.result.p_value}`}{r.result.lift_percent != null && ` · 차이 ${r.result.lift_percent}%`}</div>}
                <div>{r?.ai?.interpretation || t.conclusion}</div>
                {r?.ai?.next_steps?.length > 0 && <ul>{r.ai.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>}
              </div>
            )}
          </div>
        );
      })}
      {form && (
        <Modal title="새 A/B 테스트" onClose={() => setForm(null)} footer={<button className="primary" disabled={!form.name || busy} onClick={() => run(() => api.post("/api/abtests", { ...form, content_id_a: form.content_id_a ? Number(form.content_id_a) : null, content_id_b: form.content_id_b ? Number(form.content_id_b) : null }), "생성했습니다").then((r) => { if (r) { setForm(null); load(); } })}>생성</button>}>
          <div className="field"><label>이름</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid cols-3">
            <div className="field"><label>플랫폼</label><select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}><option>instagram</option><option>tiktok</option><option>x</option><option>facebook</option><option value="meta_ads">Meta 광고</option></select></div>
            <div className="field"><label>변수</label><select value={form.variable} onChange={(e) => setForm({ ...form, variable: e.target.value })}>{Object.entries(VAR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div className="field"><label>지표</label><select value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })}>{Object.entries(MET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          </div>
          <div className="field"><label>가설</label><input value={form.hypothesis} onChange={(e) => setForm({ ...form, hypothesis: e.target.value })} placeholder="예: 질문형 Hook 이 CTR 을 높인다" /></div>
          <div className="grid cols-2">
            <div className="field"><label>Creative A 설명</label><input value={form.variant_a} onChange={(e) => setForm({ ...form, variant_a: e.target.value })} /></div>
            <div className="field"><label>Creative B 설명</label><input value={form.variant_b} onChange={(e) => setForm({ ...form, variant_b: e.target.value })} /></div>
            <div className="field"><label>A 콘텐츠 ID (선택)</label><input type="number" value={form.content_id_a} onChange={(e) => setForm({ ...form, content_id_a: e.target.value })} /></div>
            <div className="field"><label>B 콘텐츠 ID (선택)</label><input type="number" value={form.content_id_b} onChange={(e) => setForm({ ...form, content_id_b: e.target.value })} /></div>
          </div>
        </Modal>
      )}
    </>
  );
}

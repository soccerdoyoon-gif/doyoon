import { useEffect, useState } from "react";
import { api } from "../api";
import AdActions from "../components/AdActions";
import { Empty, Kpi, MockBadge, Modal, useAction } from "../components/ui";
import { fmtDateTime, num, pct } from "../util";

const VERDICT = { good: "성과 양호", watch: "관찰", poor: "개선 필요", insufficient_data: "데이터 부족" };

export default function Ads({ onChange }) {
  const [tab, setTab] = useState("perf");
  const [days, setDays] = useState(7);
  const [ov, setOv] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [creatives, setCreatives] = useState([]);
  const [actions, setActions] = useState([]);
  const [guard, setGuard] = useState(null);
  const [budgetEdit, setBudgetEdit] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [focus, setFocus] = useState("");
  const [run, busy] = useAction();

  const load = async () => {
    const [o, ins, cr, ac, g, st] = await Promise.all([
      api.get(`/api/ads/overview?days=${days}`), api.get("/api/insights?kind=ads&limit=1"), api.get("/api/ads/creatives"),
      api.get("/api/ads/actions"), api.get("/api/ads/budget-guard"), api.get("/api/system/status"),
    ]);
    setOv(o); setAnalysis(ins[0] || null); setCreatives(cr); setActions(ac); setGuard(g); setDryRun(st.dry_run);
    onChange?.();
  };
  useEffect(() => {
    load();
  }, [days]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!ov) return <p>불러오는 중…</p>;
  const t = ov.totals;
  const adsets = ov.entities.filter((e) => e.daily_budget !== null && e.daily_budget !== undefined);

  return (
    <>
      <div className="topbar">
        <div><h1>광고 성과 관리</h1><div className="muted small">광고 예산 변경·중지·삭제·캠페인 생성은 자동 실행되지 않으며 반드시 승인이 필요합니다.</div></div>
        <div className="row">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 110 }}><option value={7}>최근 7일</option><option value={14}>최근 14일</option><option value={30}>최근 30일</option></select>
          <button disabled={busy} onClick={() => run(() => api.post("/api/ads/sync"), "광고 데이터를 가져왔습니다").then(load)}>🔄 데이터 가져오기</button>
          <button className="primary" disabled={busy} onClick={() => run(() => api.post(`/api/ads/analyze?days=${days}`), "AI 분석 완료").then(() => { load(); setTab("ai"); })}>🤖 AI 분석</button>
        </div>
      </div>
      <div className="tabs">
        {[["perf", "성과"], ["ai", "AI 분석"], ["creatives", "광고 소재"], ["actions", `작업/승인 (${actions.filter((a) => a.status === "PENDING").length})`], ["guard", "Budget Guard"]].map(([k, l]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>

      {tab === "perf" && (
        <>
          <div className="grid kpi" style={{ marginBottom: 16 }}>
            <Kpi label="지출" value={num(t.spend)} sub={<MockBadge show={t.mock_data} />} />
            <Kpi label="노출" value={num(t.impressions)} />
            <Kpi label="클릭" value={num(t.clicks)} />
            <Kpi label="CTR" value={pct(t.ctr)} />
            <Kpi label="CPC" value={num(t.cpc, 1)} />
            <Kpi label="CPM" value={num(t.cpm, 1)} />
            <Kpi label="전환" value={num(t.conversions)} />
            <Kpi label="CPA" value={num(t.cpa, 1)} />
            <Kpi label="ROAS" value={t.roas == null ? "N/A" : `${t.roas.toFixed(2)}x`} />
          </div>
          <div className="card table-wrap">
            <h2>광고별 성과</h2>
            {ov.by_ad.length === 0 ? <Empty>광고 데이터가 없습니다. [데이터 가져오기]를 누르세요. (API 미연결 시 Mock 데이터)</Empty> : (
              <table>
                <thead><tr><th>광고</th><th>상태</th><th className="num">지출</th><th className="num">노출</th><th className="num">클릭</th><th className="num">CTR</th><th className="num">CPC</th><th className="num">CPM</th><th className="num">전환</th><th className="num">CPA</th><th className="num">ROAS</th></tr></thead>
                <tbody>{ov.by_ad.map((a) => (
                  <tr key={a.ad_id}><td>{a.name}<div className="hint">{a.ad_id}</div></td><td>{a.status}</td><td className="num">{num(a.spend)}</td><td className="num">{num(a.impressions)}</td><td className="num">{num(a.clicks)}</td><td className="num">{pct(a.ctr)}</td><td className="num">{num(a.cpc, 1)}</td><td className="num">{num(a.cpm, 1)}</td><td className="num">{num(a.conversions)}</td><td className="num">{num(a.cpa, 1)}</td><td className="num">{a.roas == null ? "N/A" : a.roas.toFixed(2)}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <div className="card table-wrap">
            <div className="spread"><h2>일일 예산</h2><span className="small muted">합계 {num(ov.total_daily_budget)} / 한도 {num(guard?.daily_budget_limit)} {guard?.currency} · 오늘 지출 {num(ov.today_spend)}</span></div>
            {adsets.length === 0 ? <Empty>예산 정보가 없습니다.</Empty> : (
              <table>
                <thead><tr><th>이름</th><th>레벨</th><th>상태</th><th className="num">일일 예산</th><th></th></tr></thead>
                <tbody>{adsets.map((e) => (
                  <tr key={e.id}><td>{e.name}</td><td>{e.level}</td><td>{e.status}</td><td className="num">{num(e.daily_budget)}</td>
                    <td className="row"><button className="sm" onClick={() => setBudgetEdit({ ...e, new_budget: e.daily_budget, reason: "" })}>예산 변경 요청</button>
                      <button className="sm" onClick={() => run(() => api.post("/api/ads/actions", { action_type: e.status === "ACTIVE" ? "pause" : "resume", target_level: e.level, target_external_id: e.external_id }), "승인 대기에 등록했습니다").then(load)}>{e.status === "ACTIVE" ? "중지 요청" : "재개 요청"}</button></td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
        </>
      )}

      {tab === "ai" && (
        <div className="card">
          {!analysis ? <Empty>아직 AI 분석이 없습니다. [AI 분석]을 눌러보세요.</Empty> : (
            <>
              <div className="spread"><h2>AI 광고 분석</h2><span className="small muted">{fmtDateTime(analysis.created_at)} <MockBadge show={analysis.source !== "ai"} label="MOCK AI" /></span></div>
              <p>{analysis.data.summary}</p>
              <div className="table-wrap"><table>
                <thead><tr><th>광고</th><th>판단</th><th>근거</th><th>권장</th></tr></thead>
                <tbody>{(analysis.data.ads || []).map((a) => (
                  <tr key={a.ad_id}><td>{a.name}</td><td><span className={`badge v-${a.verdict}`}>{VERDICT[a.verdict] || a.verdict}</span></td><td className="small">{a.findings.join(", ")}</td><td>{a.recommendation}</td></tr>
                ))}</tbody>
              </table></div>
              {analysis.data.creative_directions?.length > 0 && <><h3 style={{ marginTop: 12 }}>소재 개선 방향</h3><ul>{analysis.data.creative_directions.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
              {analysis.data.pending_action_ids?.length > 0 && <div className="banner info">AI 가 제안한 광고 작업 {analysis.data.pending_action_ids.length}건이 [작업/승인] 탭에 등록되었습니다. 승인 전에는 실행되지 않습니다.</div>}
              {analysis.data.data_limitations && <p className="hint">⚠️ {analysis.data.data_limitations}</p>}
            </>
          )}
        </div>
      )}

      {tab === "creatives" && (
        <>
          <div className="card row">
            <input value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="초점 (선택): 예) 첫 구매 할인, 30대 직장인" style={{ flex: 1, minWidth: 200 }} />
            <button className="primary" disabled={busy} onClick={() => run(() => api.post("/api/ads/creatives/generate", { count: 3, focus }), "광고안을 생성했습니다").then(load)}>✨ 새 광고안 3개 생성</button>
          </div>
          {creatives.length === 0 ? <Empty>광고안이 없습니다.</Empty> : (
            <div className="grid cols-2">{creatives.map((c) => (
              <div key={c.id} className="card" style={{ margin: 0 }}>
                <div className="spread"><span className={`badge s-${c.status === "DRAFT" ? "PENDING" : c.status === "APPROVED" ? "EXECUTED" : "REJECTED"}`}>{c.status}</span><MockBadge show={c.source !== "ai"} label="MOCK AI" /></div>
                <p className="hook" style={{ fontWeight: 700, marginTop: 8 }}>{c.hook}</p>
                <p><b>Headline:</b> {c.headline}</p>
                <p className="md">{c.primary_text}</p>
                <p className="small"><b>Description:</b> {c.description} · <b>CTA:</b> {c.cta}</p>
                <details><summary className="small">영상/이미지 아이디어 · 타깃 메시지</summary>
                  <p className="md small">🎬 {c.video_idea}</p><p className="small">🖼️ {c.image_idea}</p><p className="small">🎯 {c.target_message}</p><p className="hint">{c.rationale}</p></details>
                {c.status === "DRAFT" && <div className="row" style={{ marginTop: 8 }}>
                  <button className="sm primary" onClick={() => run(() => api.post(`/api/ads/creatives/${c.id}/approve`), "승인했습니다. 실제 광고 등록은 Ads Manager 에서 진행하세요.").then(load)}>승인</button>
                  <button className="sm danger" onClick={() => run(() => api.post(`/api/ads/creatives/${c.id}/reject`)).then(load)}>반려</button></div>}
              </div>
            ))}</div>
          )}
        </>
      )}

      {tab === "actions" && <div className="card"><AdActions actions={actions} onChange={load} dryRun={dryRun} /></div>}

      {tab === "guard" && guard && <GuardForm guard={guard} onSaved={load} />}

      {budgetEdit && (
        <Modal title={`예산 변경 요청 — ${budgetEdit.name}`} onClose={() => setBudgetEdit(null)}
          footer={<button className="primary" disabled={busy} onClick={() => run(() => api.post("/api/ads/actions", { action_type: "budget_change", target_level: budgetEdit.level, target_external_id: budgetEdit.external_id, new_budget: Number(budgetEdit.new_budget), reason: budgetEdit.reason })).then((r) => { if (r) { alert(`결과: ${r.status}\n${(r.guard_result.reasons || []).join("\n")}\n${r.result || ""}`); setBudgetEdit(null); load(); } })}>Budget Guard 확인 후 요청</button>}>
          <p>현재 일일 예산: <b>{num(budgetEdit.daily_budget)}</b> {guard?.currency}</p>
          <div className="field"><label>새 일일 예산</label><input type="number" min="0" value={budgetEdit.new_budget} onChange={(e) => setBudgetEdit({ ...budgetEdit, new_budget: e.target.value })} />
            <div className="hint">변경 폭: {budgetEdit.daily_budget ? (((budgetEdit.new_budget - budgetEdit.daily_budget) / budgetEdit.daily_budget) * 100).toFixed(1) : "-"}% (±{guard?.max_budget_change_percent}% 초과 시 승인 필요, 한도 초과 시 차단)</div></div>
          <div className="field"><label>사유</label><input value={budgetEdit.reason} onChange={(e) => setBudgetEdit({ ...budgetEdit, reason: e.target.value })} /></div>
        </Modal>
      )}
    </>
  );
}

function GuardForm({ guard, onSaved }) {
  const [g, setG] = useState(guard);
  const [run, busy] = useAction();
  const n = (k) => ({ type: "number", min: 0, value: g[k], onChange: (e) => setG({ ...g, [k]: Number(e.target.value) }) });
  return (
    <div className="card" style={{ maxWidth: 640 }}>
      <h2>Budget Guard (광고비 안전장치)</h2>
      <div className="field"><label>하루 광고비 한도 ({g.currency})</label><input {...n("daily_budget_limit")} /><div className="hint">변경 후 일일 예산 합계가 이 값을 넘으면 승인해도 무조건 차단됩니다.</div></div>
      <div className="field"><label>1회 최대 변경 폭 (%)</label><input {...n("max_budget_change_percent")} max={50} /><div className="hint">기본 10%. 이보다 큰 변경은 승인 필요.</div></div>
      <div className="field"><label>승인 필요 금액 (1회 변경액)</label><input {...n("approval_required_above")} /><div className="hint">변경 금액이 이 값을 넘으면 승인 필요.</div></div>
      <label className="row" style={{ fontWeight: 400, fontSize: 14 }}><input type="checkbox" checked={g.ads_auto_execute} onChange={(e) => setG({ ...g, ads_auto_execute: e.target.checked })} /> 한도 내 소폭 예산 변경은 자동 실행 허용 (기본: 끔)</label>
      <p className="hint">중지/재개/삭제/캠페인 생성/결제 변경은 이 설정과 관계없이 항상 승인이 필요합니다.</p>
      <button className="primary" disabled={busy} onClick={() => (!g.ads_auto_execute || window.confirm("자동 실행을 켜면 Budget Guard 범위 내 예산 변경이 승인 없이 실행됩니다. 계속할까요?")) && run(() => api.put("/api/ads/budget-guard", { value: g }), "저장했습니다").then(onSaved)}>저장</button>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, qs } from "../api";
import ContentEditor, { ContentCard } from "../components/ContentEditor";
import { PipelineLauncher, RunProgress } from "../components/PipelineLauncher";
import { Empty, useAction } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, PLATFORMS, statusLabel } from "../util";

const TABS = ["", "READY_FOR_REVIEW", "DRAFT", "APPROVED", "SCHEDULED", "PUBLISHED", "FAILED", "REJECTED"];

export default function Content({ onChange }) {
  const [status, setStatus] = useState("READY_FOR_REVIEW");
  const [platform, setPlatform] = useState("");
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null);
  const [launch, setLaunch] = useState(false);
  const [runId, setRunId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [run] = useAction();

  const load = () => api.get("/api/content" + qs({ status, platform })).then(setItems);
  const loadRuns = () => api.get("/api/pipeline/runs").then((rs) => {
    setRuns(rs);
    const active = rs.find((r) => r.status === "RUNNING");
    if (active) setRunId(active.id);
  });
  useEffect(() => {
    load();
  }, [status, platform]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    loadRuns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const newManual = async () => {
    const p = window.prompt(t("플랫폼 (instagram / tiktok / x / facebook)"), "instagram");
    if (!p) return;
    const r = await run(() => api.post("/api/content", { platform: p.trim().toLowerCase(), title: t("새 콘텐츠") }));
    if (r) {
      load();
      setOpen(r.id);
    }
  };

  return (
    <>
      <div className="topbar">
        <div><h1>{t("콘텐츠 제작")}</h1><div className="muted small">{t("일본 시장 · 일본어 기본. 점수는 내부 우선순위용이며 성과를 보장하지 않습니다.")}</div></div>
        <div className="row">
          <button onClick={newManual}>＋ {t("직접 작성")}</button>
          <button className="primary" onClick={() => setLaunch(true)}>✨ {t("AI 콘텐츠 제작")}</button>
        </div>
      </div>
      {runId && <RunProgress runId={runId} onDone={() => { load(); loadRuns(); onChange?.(); }} />}
      <div className="tabs">
        {TABS.map((s) => <button key={s} className={status === s ? "active" : ""} onClick={() => setStatus(s)}>{s ? statusLabel(s) : t("전체")}</button>)}
        <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={{ width: 140, marginLeft: "auto" }}>
          <option value="">{t("모든 SNS")}</option>
          {Object.entries(PLATFORMS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {items.length === 0 ? <Empty>{t("콘텐츠가 없습니다.")}</Empty> : (
        <div className="grid cols-3">{items.map((it) => <ContentCard key={it.id} item={it} onOpen={() => setOpen(it.id)} />)}</div>
      )}
      {runs.length > 0 && (
        <details style={{ marginTop: 16 }}>
          <summary className="small">{t("제작 기록")} ({runs.length})</summary>
          <table className="small"><tbody>{runs.map((r) => (
            <tr key={r.id}><td>#{r.id}</td><td>{fmtDateTime(r.created_at)}</td><td>{statusLabel(r.status)}</td>
              <td>{(r.request.platforms || []).join(", ") || t("설정된 SNS")} · {t("아이디어")} {r.request.idea_count ?? "-"} {r.request.theme && `· ${r.request.theme}`}</td>
              <td><button className="sm" onClick={() => setRunId(r.id)}>{t("보기")}</button></td></tr>
          ))}</tbody></table>
        </details>
      )}
      {open && <ContentEditor id={open} onClose={() => { setOpen(null); load(); }} onChange={() => { load(); onChange?.(); }} />}
      {launch && <PipelineLauncher onClose={() => setLaunch(false)} onStarted={(id) => { setLaunch(false); setRunId(id); setStatus("READY_FOR_REVIEW"); loadRuns(); }} />}
    </>
  );
}

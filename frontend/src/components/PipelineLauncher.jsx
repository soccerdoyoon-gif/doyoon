import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { fmtDateTime, PLATFORMS } from "../util";
import { Modal, StatusBadge, useAction } from "./ui";

// AI 콘텐츠 제작 (에이전트 파이프라인) 시작 모달
export function PipelineLauncher({ onClose, onStarted }) {
  const [styles, setStyles] = useState([]);
  const [f, setF] = useState({ platforms: ["instagram", "tiktok", "x"], idea_count: 2, theme: "", style: "", language: "ja", with_images: true, with_video: true, include_ads: true });
  const [run, busy] = useAction();
  useEffect(() => {
    api.get("/api/pipeline/styles").then(setStyles);
  }, []);
  const total = f.idea_count * f.platforms.length;
  const start = async () => {
    const r = await run(() => api.post("/api/pipeline/run", { ...f, style: f.style || undefined }), t("AI 콘텐츠 제작을 시작했습니다"));
    if (r) onStarted(r.id);
  };
  return (
    <Modal title={`✨ ${t("AI 콘텐츠 제작")}`} onClose={onClose} footer={<button className="primary" disabled={busy || !f.platforms.length} onClick={start}>{t("제작 시작")} ({t("{n}개", { n: total })})</button>}>
      <p className="small muted">{t("트렌드 분석 → 아이디어 → 일본어 카피 → 영상 스크립트 → 이미지·영상·자막 → Brand Guardian → 승인 대기. 승인 전에는 게시되지 않습니다.")}</p>
      <div className="field"><label>SNS</label>
        <div className="row">{Object.entries(PLATFORMS).map(([k, v]) => (
          <label key={k} className="row" style={{ fontWeight: 400 }}>
            <input type="checkbox" checked={f.platforms.includes(k)} onChange={(e) => setF({ ...f, platforms: e.target.checked ? [...f.platforms, k] : f.platforms.filter((x) => x !== k) })} /> {v}
          </label>))}
        </div>
      </div>
      <div className="grid cols-3">
        <div className="field"><label>{t("아이디어 수")}</label><input type="number" min="1" max="10" value={f.idea_count} onChange={(e) => setF({ ...f, idea_count: Math.max(1, Math.min(10, Number(e.target.value))) })} />
          <div className="hint">{t("아이디어 1개 → SNS 별로 각각 1개씩")}</div></div>
        <div className="field"><label>{t("스타일")}</label><select value={f.style} onChange={(e) => setF({ ...f, style: e.target.value })}><option value="">{t("AI 가 선택")}</option>{styles.map((s) => <option key={s}>{s}</option>)}</select></div>
        <div className="field"><label>{t("콘텐츠 언어")}</label><select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}><option value="ja">日本語 ({t("기본")})</option><option value="ko">한국어</option><option value="en">English</option></select></div>
      </div>
      <div className="field"><label>{t("주제 / 요청 (선택)")}</label><input value={f.theme} onChange={(e) => setF({ ...f, theme: e.target.value })} placeholder={t("예: 가을 신상품, 첫 구매 할인")} /></div>
      <div className="row">
        {[["with_images", "이미지 생성"], ["with_video", "영상 생성"], ["include_ads", "광고안 포함"]].map(([k, l]) => (
          <label key={k} className="row" style={{ fontWeight: 400 }}><input type="checkbox" checked={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} /> {t(l)}</label>
        ))}
      </div>
    </Modal>
  );
}

// 실행 진행 상황 (2초마다 갱신)
export function RunProgress({ runId, onDone }) {
  const [r, setR] = useState(null);
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const d = await api.get(`/api/pipeline/runs/${runId}`);
        if (stop) return;
        setR(d);
        if (d.status === "RUNNING") setTimeout(tick, 2000);
        else onDone?.(d);
      } catch {
        if (!stop) setTimeout(tick, 4000);
      }
    };
    tick();
    return () => { stop = true; };
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!r) return null;
  return (
    <div className={`banner ${r.status === "ERROR" ? "bad" : r.status === "DONE" ? "good" : "info"}`}>
      <div className="spread"><b>#{r.id} {t("AI 콘텐츠 제작")} — <StatusBadge s={r.status} /></b><span className="small">{fmtDateTime(r.created_at)}</span></div>
      <ol className="small" style={{ margin: "6px 0 0" }}>
        {(r.steps || []).map((s, i) => <li key={i}>{s.status === "done" ? "✅" : s.status === "error" ? "❌" : "⏳"} {s.name} {s.note && <span className="muted">— {s.note}</span>}</li>)}
        {r.status === "RUNNING" && <li className="muted">…</li>}
      </ol>
      {r.status === "DONE" && <div className="small">{t("승인 대기 {a}개 · 보류(초안) {b}개", { a: r.result.ready_for_review?.length ?? 0, b: r.result.held_as_draft?.length ?? 0 })}</div>}
      {r.error && <div className="small">{r.error}</div>}
    </div>
  );
}

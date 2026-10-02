import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime, localInputToISO, num, pct, PLATFORMS, toLocalInput, TYPE_LABEL } from "../util";
import { ListInput, MockBadge, Modal, PlatformBadge, Scores, StatusBadge, useAction } from "./ui";

// 콘텐츠 상세: 수정 / 미디어 업로드 / 승인·예약 / 게시 / 반려 / 삭제
export default function ContentEditor({ id, onClose, onChange }) {
  const [item, setItem] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [form, setForm] = useState(null);
  const [when, setWhen] = useState("");
  const [run, busy] = useAction();

  const load = async () => {
    const [d, st] = await Promise.all([api.get(`/api/content/${id}`), api.get("/api/system/status")]);
    setDryRun(st.dry_run);
    setItem(d);
    setForm(d);
    setWhen(toLocalInput(d.scheduled_at || d.suggested_time));
  };
  useEffect(() => {
    load();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!item) return <Modal title="불러오는 중…" onClose={onClose}><p>…</p></Modal>;
  const locked = item.status === "PUBLISHED";
  const f = (k) => ({ value: form[k] ?? "", onChange: (e) => setForm({ ...form, [k]: e.target.value }), disabled: locked });
  const after = async (p, msg) => {
    const r = await run(p, msg);
    if (r !== undefined) {
      await load();
      onChange?.();
    }
    return r;
  };
  const save = () =>
    after(() => api.put(`/api/content/${id}`, {
      title: form.title, idea: form.idea, hook: form.hook, caption: form.caption, script: form.script, cta: form.cta,
      hashtags: form.hashtags, structure: form.structure, thread: form.thread, media_idea: form.media_idea, media_url: form.media_url,
    }), "저장했습니다");
  const confirmLive = (what) => dryRun || window.confirm(`⚠️ LIVE 모드입니다. ${what} 실제 SNS 에 게시됩니다. 계속할까요?`);
  const m = item.latest_metrics;

  return (
    <Modal
      title={`#${item.id} ${item.title || "(제목 없음)"}`}
      onClose={onClose}
      footer={
        <>
          {!["PUBLISHED"].includes(item.status) && (
            <button className="danger" disabled={busy} onClick={async () => {
              if (!window.confirm("이 콘텐츠를 삭제할까요? 되돌릴 수 없습니다.")) return;
              if ((await run(() => api.del(`/api/content/${id}`), "삭제했습니다")) !== undefined) { onChange?.(); onClose(); }
            }}>삭제</button>
          )}
          {!locked && <button disabled={busy} onClick={save}>💾 저장</button>}
          {["DRAFT", "REJECTED"].includes(item.status) && <button disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/submit`), "검토 요청했습니다")}>검토 요청</button>}
          {["READY_FOR_REVIEW", "DRAFT"].includes(item.status) && <button className="danger" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/reject`, { note: window.prompt("반려 사유 (선택)") || "" }), "반려했습니다")}>반려</button>}
          {item.status === "READY_FOR_REVIEW" && <button className="primary" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/approve`, { schedule_at: localInputToISO(when) }), "승인 + 예약했습니다")}>✅ 승인 + 예약</button>}
          {["APPROVED", "FAILED"].includes(item.status) && <button className="primary" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/schedule`, { scheduled_at: localInputToISO(when) }), "예약했습니다")}>🗓️ 예약</button>}
          {item.status === "SCHEDULED" && <button disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/unschedule`), "예약을 취소했습니다")}>예약 취소</button>}
          {["APPROVED", "SCHEDULED", "FAILED"].includes(item.status) && <button className="good" disabled={busy} onClick={() => confirmLive("이 콘텐츠가") && after(() => api.post(`/api/content/${id}/publish-now`), dryRun ? "DRY RUN: 게시 시뮬레이션 완료" : "게시 요청 완료")}>🚀 지금 게시</button>}
        </>
      }
    >
      <div className="row" style={{ marginBottom: 12 }}>
        <PlatformBadge p={item.platform} /> <span className="badge">{TYPE_LABEL[item.content_type] || item.content_type}</span> <StatusBadge s={item.status} />
        <MockBadge show={item.source === "mock_ai"} label="MOCK AI" />
        {item.is_dry_run && <span className="badge mock">DRY RUN 게시</span>}
      </div>
      {item.review_note && <div className="banner warn">{item.review_note}</div>}
      {item.last_error && <div className="banner bad">실패 이유: {item.last_error}{item.next_retry_at && ` · 다음 재시도 ${fmtDateTime(item.next_retry_at)}`}</div>}
      <Scores scores={item.scores} total={item.score_total} note={item.score_note} />
      <div className="grid cols-2" style={{ marginTop: 12 }}>
        <div className="field"><label>제목</label><input {...f("title")} /></div>
        <div className="field"><label>{["APPROVED", "SCHEDULED", "FAILED", "READY_FOR_REVIEW"].includes(item.status) ? "게시 시간 (내 PC 시간 기준)" : "제안 시간 (내 PC 시간 기준)"}</label><input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} disabled={locked} /></div>
      </div>
      <div className="field"><label>아이디어</label><input {...f("idea")} /></div>
      <div className="field"><label>Hook (첫 문장 / 첫 3초)</label><input {...f("hook")} /></div>
      <div className="field"><label>Caption {item.platform === "x" && <span className="muted">({(form.caption || "").length}/280)</span>}</label><textarea {...f("caption")} rows={6} /></div>
      {(item.script || ["reel", "short_video"].includes(item.content_type)) && <div className="field"><label>대사 / 스크립트</label><textarea {...f("script")} rows={5} /></div>}
      {(form.structure || []).length > 0 && (
        <div className="field"><label>구성</label><ol className="small">{form.structure.map((s, i) => <li key={i}>{s}</li>)}</ol></div>
      )}
      {item.content_type === "thread" && (
        <div className="field"><label>Thread (한 줄에 트윗 하나)</label>
          <textarea rows={6} value={(form.thread || []).join("\n")} disabled={locked} onChange={(e) => setForm({ ...form, thread: e.target.value.split("\n") })} />
        </div>
      )}
      <div className="grid cols-2">
        <div className="field"><label>CTA</label><input {...f("cta")} /></div>
        <div className="field"><label>Hashtags</label>{locked ? <div className="tags">{(item.hashtags || []).join(" ")}</div> : <ListInput value={form.hashtags} onChange={(v) => setForm({ ...form, hashtags: v })} />}</div>
      </div>
      <div className="field"><label>이미지/영상 아이디어</label><textarea {...f("media_idea")} rows={2} /></div>
      <div className="grid cols-2">
        <div className="field"><label>미디어 공개 URL (선택)</label><input {...f("media_url")} placeholder="https://… (Instagram/TikTok 은 공개 URL 필요)" /></div>
        <div className="field"><label>미디어 파일 업로드</label>
          <input type="file" accept="image/*,video/*" disabled={locked} onChange={(e) => e.target.files[0] && after(() => api.upload(`/api/content/${id}/media`, e.target.files[0]), "업로드했습니다")} />
          {item.media_path && <div className="hint">업로드됨: <a href={`/media/${item.media_path}`} target="_blank" rel="noreferrer">{item.media_path}</a></div>}
        </div>
      </div>
      {item.status === "PUBLISHED" && (
        <div className="card">
          <h3>게시 결과 {m && <MockBadge show={m.source === "mock"} />}</h3>
          <p className="small">게시 시간 {fmtDateTime(item.published_at)} {item.external_url && <> · <a href={item.external_url} target="_blank" rel="noreferrer">게시물 보기</a></>}</p>
          {m ? (
            <div className="row small">
              {["impressions", "reach", "views", "likes", "comments", "shares", "saves", "clicks"].map((k) => <span key={k} className="badge">{k} {num(m[k])}</span>)}
              <span className="badge">ER {pct(m.engagement_rate)}</span>
            </div>
          ) : <p className="muted small">아직 성과 데이터가 없습니다 (매시 10분에 자동 수집).</p>}
        </div>
      )}
      {item.attempts?.length > 0 && (
        <details>
          <summary className="small">게시 시도 기록 ({item.attempts.length})</summary>
          <table className="small"><tbody>
            {item.attempts.map((a) => <tr key={a.id}><td>{fmtDateTime(a.attempted_at)}</td><td>{a.success ? "✅ 성공" : "❌ 실패"}{a.dry_run && " (dry run)"}</td><td>{a.error || a.response?.message}</td></tr>)}
          </tbody></table>
        </details>
      )}
    </Modal>
  );
}

export function ContentCard({ item, onOpen, selectable, selected, onSelect }) {
  return (
    <div className="content-card">
      <div className="spread">
        <div className="row">
          {selectable && <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} aria-label="선택" />}
          <PlatformBadge p={item.platform} /> <span className="badge">{TYPE_LABEL[item.content_type] || item.content_type}</span> <StatusBadge s={item.status} />
          <MockBadge show={item.source === "mock_ai"} label="MOCK AI" />
        </div>
        <span className="small muted">{fmtDateTime(item.scheduled_at || item.published_at || item.suggested_time)}</span>
      </div>
      <div className="hook">{item.hook || item.title}</div>
      <div className="caption">{item.caption}</div>
      {item.hashtags?.length > 0 && <div className="tags">{item.hashtags.join(" ")}</div>}
      <div className="spread" style={{ marginTop: 8 }}>
        <span className="small">점수 <span className="score">{item.score_total ?? "-"}</span>/10</span>
        <button className="sm" onClick={onOpen}>열기 / 수정</button>
      </div>
      {item.last_error && <div className="hint" style={{ color: "var(--bad)" }}>❌ {item.last_error}</div>}
    </div>
  );
}

export const PLATFORM_OPTIONS = Object.entries(PLATFORMS);

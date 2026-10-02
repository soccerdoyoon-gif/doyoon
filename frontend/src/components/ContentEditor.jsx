import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { fmtDateTime, localInputToISO, num, pct, toLocalInput, typeLabel, tzLabel } from "../util";
import { ListInput, MockBadge, Modal, PlatformBadge, Scores, StatusBadge, useAction } from "./ui";

const SEV = { error: "s-FAILED", warning: "v-watch", info: "" };

export function AssetGallery({ assets }) {
  const poster = (assets || []).find((a) => a.kind === "thumbnail");
  const media = (assets || []).filter((a) => ["image", "video", "thumbnail"].includes(a.kind));
  const subs = (assets || []).filter((a) => a.kind === "subtitle");
  if (!media.length && !subs.length) return null;
  return (
    <div>
      <div className="row" style={{ alignItems: "flex-start" }}>
        {media.map((a) => (
          <div key={a.id} style={{ width: a.aspect === "9:16" ? 120 : 150 }}>
            {a.kind === "video"
              ? <video src={a.url} poster={poster?.url} controls preload="metadata" style={{ width: "100%", borderRadius: 8, background: "#000" }} />
              : <a href={a.url} target="_blank" rel="noreferrer"><img src={a.url} alt={a.overlay_text} style={{ width: "100%", borderRadius: 8, border: "1px solid var(--border)" }} /></a>}
            <div className="hint">{a.kind === "video" ? `🎬 ${a.duration}s${a.meta?.voice ? " · 🔊" : ""}` : a.purpose} · {a.aspect}</div>
          </div>
        ))}
      </div>
      {subs.map((a) => <div key={a.id} className="hint"><a href={a.url} target="_blank" rel="noreferrer">📝 {t("자막 파일")} (.srt)</a></div>)}
    </div>
  );
}

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

  if (!item) return <Modal title="…" onClose={onClose}><p>…</p></Modal>;
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
    }), t("저장했습니다"));
  const confirmLive = () => dryRun || window.confirm(t("⚠️ LIVE 모드입니다. 이 콘텐츠가 실제 SNS 에 게시됩니다. 계속할까요?"));
  const m = item.latest_metrics;
  const g = item.guardian || {};
  const issues = [...(g.rule_issues || []), ...(g.ai_issues || [])];
  const isVideo = ["reel", "short_video"].includes(item.content_type);

  return (
    <Modal
      title={`#${item.id} ${item.title || t("(제목 없음)")}`}
      onClose={onClose}
      footer={
        <>
          {item.status !== "PUBLISHED" && (
            <button className="danger" disabled={busy} onClick={async () => {
              if (!window.confirm(t("이 콘텐츠를 삭제할까요? 되돌릴 수 없습니다."))) return;
              if ((await run(() => api.del(`/api/content/${id}`), t("삭제했습니다"))) !== undefined) { onChange?.(); onClose(); }
            }}>{t("삭제")}</button>
          )}
          {!locked && <button disabled={busy} onClick={save}>💾 {t("저장")}</button>}
          {["DRAFT", "REJECTED"].includes(item.status) && <button disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/submit`), t("검토 요청했습니다"))}>{t("검토 요청")}</button>}
          {["READY_FOR_REVIEW", "DRAFT"].includes(item.status) && <button className="danger" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/reject`, { note: window.prompt(t("반려 사유 (선택)")) || "" }), t("반려했습니다"))}>{t("반려")}</button>}
          {item.status === "READY_FOR_REVIEW" && <button className="primary" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/approve`, { schedule_at: localInputToISO(when) }), t("승인 + 예약했습니다"))}>✅ {t("승인 + 예약")}</button>}
          {["APPROVED", "FAILED"].includes(item.status) && <button className="primary" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/schedule`, { scheduled_at: localInputToISO(when) }), t("예약했습니다"))}>🗓️ {t("예약")}</button>}
          {item.status === "SCHEDULED" && <button disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/unschedule`), t("예약을 취소했습니다"))}>{t("예약 취소")}</button>}
          {["APPROVED", "SCHEDULED", "FAILED"].includes(item.status) && <button className="good" disabled={busy} onClick={() => confirmLive() && after(() => api.post(`/api/content/${id}/publish-now`), dryRun ? t("DRY RUN: 게시 시뮬레이션 완료") : t("게시 요청 완료"))}>🚀 {t("지금 게시")}</button>}
        </>
      }
    >
      <div className="row" style={{ marginBottom: 12 }}>
        <PlatformBadge p={item.platform} /> <span className="badge">{typeLabel(item.content_type)}</span> <StatusBadge s={item.status} />
        {item.style && <span className="badge">{item.style}</span>}
        <span className="badge">{item.language}</span>
        <MockBadge show={item.source === "mock_ai"} label="MOCK AI" />
        {item.is_dry_run && <span className="badge mock">{t("DRY RUN 게시")}</span>}
      </div>
      {item.review_note && <div className="banner warn">{item.review_note}</div>}
      {item.last_error && <div className="banner bad">{t("실패 이유")}: {item.last_error}{item.next_retry_at && ` · ${t("다음 재시도")} ${fmtDateTime(item.next_retry_at)}`}</div>}
      {g.verdict && (
        <div className="small" style={{ marginBottom: 10 }}>
          🛡️ Brand Guardian: <b>{g.verdict === "pass" ? t("통과") : g.verdict === "fix" ? t("수정 후 통과") : t("반려")}</b>
          {g.corrected_fields?.length > 0 && <span className="muted"> · {t("수정된 항목")}: {g.corrected_fields.join(", ")}</span>}
          {issues.length > 0 && <ul style={{ margin: "4px 0" }}>{issues.map((x, i) => <li key={i}><span className={`badge ${SEV[x.severity] || ""}`}>{x.severity}</span> {x.field}: {x.message}</li>)}</ul>}
        </div>
      )}
      <Scores scores={item.scores} total={item.score_total} note={item.score_note} />

      <div className="card" style={{ marginTop: 12 }}>
        <div className="spread"><h3 style={{ margin: 0 }}>🎨 {t("생성된 이미지 · 영상")}</h3>
          {!locked && item.platform !== "x" && <button className="sm" disabled={busy} onClick={() => after(() => api.post(`/api/content/${id}/regenerate-media`), t("미디어를 다시 생성했습니다"))}>🔄 {t("현재 문구로 다시 생성")}</button>}
        </div>
        {(item.assets || []).length ? <AssetGallery assets={item.assets} /> : <p className="muted small">{item.platform === "x" ? t("X 는 텍스트 게시입니다.") : t("아직 생성된 파일이 없습니다.")}</p>}
      </div>

      <div className="grid cols-2" style={{ marginTop: 12 }}>
        <div className="field"><label>{t("제목")}</label><input {...f("title")} /></div>
        <div className="field"><label>{t("게시 시간")} ({tzLabel()})</label><input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} disabled={locked} /></div>
      </div>
      <div className="field"><label>{t("Hook (첫 문장 / 첫 1~3초)")}</label><input {...f("hook")} /></div>
      <div className="field"><label>Caption {item.platform === "x" && <span className="muted">({t("일본어 1자 = 2카운트, 최대 280")})</span>}</label><textarea {...f("caption")} rows={6} /></div>
      {item.content_type === "thread" && (
        <div className="field"><label>{t("Thread (한 줄에 게시물 하나)")}</label>
          <textarea rows={6} value={(form.thread || []).join("\n")} disabled={locked} onChange={(e) => setForm({ ...form, thread: e.target.value.split("\n") })} />
        </div>
      )}
      <div className="grid cols-2">
        <div className="field"><label>CTA</label><input {...f("cta")} /></div>
        <div className="field"><label>Hashtags</label>{locked ? <div className="tags">{(item.hashtags || []).join(" ")}</div> : <ListInput value={form.hashtags} onChange={(v) => setForm({ ...form, hashtags: v })} />}</div>
      </div>
      {(item.thumbnail_text || item.video_title) && (
        <div className="grid cols-2">
          <div className="field"><label>{t("썸네일 문구")}</label><input value={item.thumbnail_text} disabled /></div>
          {item.video_title && <div className="field"><label>YouTube Shorts {t("제목")}</label><input value={item.video_title} disabled /></div>}
        </div>
      )}
      {isVideo && (item.scenes || []).length > 0 && (
        <details open>
          <summary className="small"><b>🎬 {t("영상 스크립트 (장면)")}</b> · 9:16 {item.music_style && `· ♪ ${item.music_style}`}</summary>
          <div className="table-wrap"><table className="small">
            <thead><tr><th>#</th><th>{t("초")}</th><th>{t("역할")}</th><th>{t("영상")}</th><th>{t("카메라")}</th><th>{t("대사")}</th><th>{t("자막")}</th></tr></thead>
            <tbody>{item.scenes.map((sc) => (
              <tr key={sc.scene_id}><td>{sc.scene_id}</td><td>{sc.duration}</td><td>{sc.purpose}</td><td>{sc.visual}</td><td>{sc.camera}</td><td>{sc.voiceover}</td><td>{sc.subtitle}</td></tr>
            ))}</tbody>
          </table></div>
          {item.video_prompt && <p className="hint">{t("영상 생성 AI 용 프롬프트")}: <span className="mono">{item.video_prompt}</span></p>}
        </details>
      )}
      {item.content_type === "carousel" && (item.structure || []).length > 0 && (
        <div className="field"><label>{t("캐러셀 슬라이드")}</label><ol className="small">{item.structure.map((s, i) => <li key={i}>{s}</li>)}</ol></div>
      )}
      <div className="grid cols-2">
        <div className="field"><label>{t("미디어 공개 URL (선택)")}</label><input {...f("media_url")} placeholder="https://…" /></div>
        <div className="field"><label>{t("직접 만든 파일 업로드 (선택)")}</label>
          <input type="file" accept="image/*,video/*" disabled={locked} onChange={(e) => e.target.files[0] && after(() => api.upload(`/api/content/${id}/media`, e.target.files[0]), t("업로드했습니다"))} />
          {item.media_path && <div className="hint">{t("업로드됨")}: <a href={`/media/${item.media_path}`} target="_blank" rel="noreferrer">{item.media_path}</a> ({t("생성 파일보다 우선 사용")})</div>}
        </div>
      </div>
      {item.status === "PUBLISHED" && (
        <div className="card">
          <h3>{t("게시 결과")} {m && <MockBadge show={m.source === "mock"} />}</h3>
          <p className="small">{t("게시 시간")} {fmtDateTime(item.published_at)} {item.external_url && <> · <a href={item.external_url} target="_blank" rel="noreferrer">{t("게시물 보기")}</a></>}</p>
          {m ? (
            <div className="row small">
              {["impressions", "reach", "views", "likes", "comments", "shares", "saves", "clicks"].map((k) => <span key={k} className="badge">{k} {num(m[k])}</span>)}
              <span className="badge">ER {pct(m.engagement_rate)}</span>
            </div>
          ) : <p className="muted small">{t("아직 성과 데이터가 없습니다 (매시 10분에 자동 수집).")}</p>}
        </div>
      )}
      {item.attempts?.length > 0 && (
        <details>
          <summary className="small">{t("게시 시도 기록")} ({item.attempts.length})</summary>
          <table className="small"><tbody>
            {item.attempts.map((a) => <tr key={a.id}><td>{fmtDateTime(a.attempted_at)}</td><td>{a.success ? `✅ ${t("성공")}` : `❌ ${t("실패")}`}{a.dry_run && " (dry run)"}</td><td>{a.error || a.response?.message}</td></tr>)}
          </tbody></table>
        </details>
      )}
    </Modal>
  );
}

export function ContentCard({ item, onOpen, selectable, selected, onSelect }) {
  const thumb = (item.assets || []).find((a) => a.kind === "thumbnail" || (a.kind === "image" && ["feed", "carousel"].includes(a.purpose)));
  const hasVideo = (item.assets || []).some((a) => a.kind === "video");
  return (
    <div className="content-card">
      <div className="spread">
        <div className="row">
          {selectable && <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} aria-label={t("선택")} />}
          <PlatformBadge p={item.platform} /> <span className="badge">{typeLabel(item.content_type)}</span> <StatusBadge s={item.status} />
          <MockBadge show={item.source === "mock_ai"} label="MOCK AI" />
        </div>
        <span className="small muted">{fmtDateTime(item.scheduled_at || item.published_at || item.suggested_time)}</span>
      </div>
      <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap", marginTop: 6 }}>
        {thumb && <img src={thumb.url} alt="" style={{ width: 64, borderRadius: 6, border: "1px solid var(--border)", flexShrink: 0 }} />}
        <div style={{ minWidth: 0 }}>
          <div className="hook" style={{ marginTop: 0 }}>{hasVideo && "🎬 "}{item.hook || item.title}</div>
          <div className="caption">{item.caption}</div>
        </div>
      </div>
      {item.hashtags?.length > 0 && <div className="tags">{item.hashtags.join(" ")}</div>}
      <div className="spread" style={{ marginTop: 8 }}>
        <span className="small">{t("점수")} <span className="score">{item.score_total ?? "-"}</span>/10 {item.guardian?.verdict && `· 🛡️ ${item.guardian.verdict}`}</span>
        <button className="sm" onClick={onOpen}>{t("열기 / 수정")}</button>
      </div>
      {item.review_note && <div className="hint" style={{ color: "var(--warn)" }}>⚠️ {item.review_note}</div>}
      {item.last_error && <div className="hint" style={{ color: "var(--bad)" }}>❌ {item.last_error}</div>}
    </div>
  );
}

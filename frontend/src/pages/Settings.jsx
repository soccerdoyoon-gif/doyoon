import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useToast } from "../components/ui";
import { t } from "../i18n";
import { PLATFORMS, tzLabel } from "../util";

const SECRET_GROUPS = [
  ["Claude AI", ["ANTHROPIC_API_KEY"]],
  ["Instagram (Instagram Login)", ["INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"]],
  ["TikTok", ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"]],
  ["X", ["X_CLIENT_ID", "X_CLIENT_SECRET", "X_ACCESS_TOKEN", "X_REFRESH_TOKEN"]],
  ["Facebook", ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"]],
  ["Meta Ads", ["META_AD_ACCOUNT_ID", "META_ADS_ACCESS_TOKEN"]],
  ["Creative", ["OPENAI_API_KEY", "VOICEVOX_URL", "PUBLIC_MEDIA_BASE_URL"]],
  ["Notification", ["SLACK_WEBHOOK_URL", "DISCORD_WEBHOOK_URL"]],
];
const OAUTH = { instagram: "Instagram", tiktok: "TikTok", x: "X" };
const isSecret = (k) => /SECRET|TOKEN|API_KEY/.test(k);

export default function Settings({ status, onChange }) {
  const [data, setData] = useState(null);
  const [secrets, setSecrets] = useState({});
  const [speakers, setSpeakers] = useState(null);
  const [run, busy] = useAction();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const load = () => api.get("/api/settings").then(setData);
  useEffect(() => {
    load();
    if (params.get("oauth")) {
      const ok = params.get("status") === "ok";
      toast(ok ? t("{p} 연결 완료!", { p: params.get("oauth") }) : t("{p} 연결 실패: {m}", { p: params.get("oauth"), m: params.get("msg") }), ok ? "ok" : "err");
      setParams({});
      onChange?.();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!data) return <p>…</p>;
  const s = data.settings;
  const cr = data.creative;
  const put = (key, value) => run(() => api.put(`/api/settings/${key}`, { value }), t("저장했습니다")).then(() => { load(); onChange?.(); });
  const saveSecrets = () => {
    const clean = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v && v.trim()));
    if (!Object.keys(clean).length) return;
    run(() => api.post("/api/settings/secrets", { secrets: clean }), t("저장했습니다. 서버를 재시작하면 확실히 적용됩니다.")).then(() => { setSecrets({}); load(); onChange?.(); });
  };
  const connect = async (p) => {
    const r = await run(() => api.get(`/api/oauth/${p}/start`));
    if (r) window.location.href = r.authorize_url;
  };
  const ok = (v) => <span className={`badge ${v ? "s-EXECUTED" : "mock"}`}>{v ? "OK" : t("없음")}</span>;
  const v = s.voice;

  return (
    <>
      <div className="topbar"><div><h1>{t("설정")}</h1><div className="muted small">{t("모드")}: {data.dry_run ? t("DRY RUN (안전)") : "LIVE"} — {t("DRY RUN 해제는 .env 파일의 DRY_RUN=false 로만 가능합니다 (README 참고).")}</div></div></div>

      <div className="grid cols-2">
        <div className="card">
          <h2>🇯🇵 {t("기본 시장")}</h2>
          <table className="small"><tbody>
            <tr><td>DEFAULT_COUNTRY</td><td>{data.defaults.country}</td></tr>
            <tr><td>DEFAULT_LANGUAGE</td><td>{data.defaults.language} — {t("콘텐츠는 일본어 기본, 한국어/영어는 요청할 때만")}</td></tr>
            <tr><td>DEFAULT_CURRENCY</td><td>{data.defaults.currency}</td></tr>
            <tr><td>DEFAULT_TIMEZONE</td><td>{data.defaults.timezone} ({tzLabel()})</td></tr>
          </tbody></table>
          <div className="field" style={{ marginTop: 12 }}><label>{t("대시보드 / 리포트 언어")}</label>
            <select value={s.ui_language} onChange={(e) => put("ui_language", e.target.value)} style={{ maxWidth: 200 }}><option value="ja">日本語</option><option value="ko">한국어</option></select></div>
        </div>
        <div className="card">
          <h2>🎨 {t("이미지 · 영상 · 음성 환경")}</h2>
          <table className="small"><tbody>
            <tr><td>{t("이미지 생성")}</td><td>{cr.image_provider === "openai" && cr.openai_images ? "OpenAI + " + t("일본어 문구 합성") : t("템플릿 디자인 (무료)")}</td></tr>
            <tr><td>{t("영상 생성")}</td><td>{cr.video_provider === "slideshow" ? t("9:16 슬라이드 영상 + 일본어 자막") : t("장면 정보/프롬프트만")} {ok(cr.ffmpeg)} ffmpeg</td></tr>
            <tr><td>{t("일본어 폰트")}</td><td>{ok(!!cr.japanese_font)} <span className="mono">{cr.japanese_font}</span></td></tr>
            <tr><td>{t("일본어 음성 (VOICEVOX)")}</td><td>{ok(cr.voicevox)}</td></tr>
          </tbody></table>
          <div className="row" style={{ marginTop: 10 }}>
            {[["generate_images", "이미지 자동 생성"], ["generate_videos", "영상 자동 생성"], ["include_ads", "광고안 포함"], ["ai_scene_images", "영상 장면에 AI 이미지 사용 (유료)"]].map(([k, l]) => (
              <label key={k} className="row" style={{ fontWeight: 400 }}><input type="checkbox" checked={!!s.media[k]} onChange={(e) => put("media", { ...s.media, [k]: e.target.checked })} /> {t(l)}</label>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <h2>🔊 {t("영상 음성 (일본어 TTS)")}</h2>
        <div className="row">
          <label className="row" style={{ fontWeight: 400 }}><input type="checkbox" checked={v.enabled} onChange={(e) => put("voice", { ...v, enabled: e.target.checked })} /> {t("음성 사용")}</label>
          <select value={v.gender} onChange={(e) => put("voice", { ...v, gender: e.target.value })} style={{ width: 120 }}><option value="female">female</option><option value="male">male</option></select>
          <select value={v.tone} onChange={(e) => put("voice", { ...v, tone: e.target.value })} style={{ width: 140 }}>{["casual", "energetic", "calm", "luxury"].map((x) => <option key={x}>{x}</option>)}</select>
          <span className="small muted">VOICEVOX speaker ID: {v.speakers?.[v.gender]?.[v.tone]}</span>
          <button className="sm" onClick={() => api.get("/api/voice/speakers").then(setSpeakers)}>{t("음성 목록 보기")}</button>
        </div>
        <div className="grid cols-2" style={{ marginTop: 10 }}>
          {["female", "male"].map((g) => (
            <div key={g} className="row small">{g}:
              {["casual", "energetic", "calm", "luxury"].map((tone) => (
                <label key={tone} style={{ fontWeight: 400 }}>{tone} <input type="number" min="0" style={{ width: 64 }} defaultValue={v.speakers?.[g]?.[tone]}
                  onBlur={(e) => Number(e.target.value) !== v.speakers?.[g]?.[tone] && put("voice", { ...v, speakers: { ...v.speakers, [g]: { ...v.speakers[g], [tone]: Number(e.target.value) } } })} /></label>
              ))}
            </div>
          ))}
        </div>
        {speakers && (speakers.available
          ? <div className="small" style={{ maxHeight: 160, overflowY: "auto", marginTop: 8 }}>{speakers.speakers.map((x) => <span key={x.id} className="badge" style={{ margin: 2 }}>{x.id}: {x.name}（{x.style}）</span>)}</div>
          : <p className="hint">{speakers.hint}</p>)}
        <p className="hint">{t("VOICEVOX 는 무료 일본어 음성 엔진입니다. 상업 이용 시 캐릭터별 크레딧 표기(예: VOICEVOX:春日部つむぎ)를 확인하세요. VOICEVOX_URL 이 없으면 자막만 들어간 무음 영상이 만들어집니다.")}</p>
      </div>

      <div className="card">
        <h2>{t("연결 상태")}</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>{t("서비스")}</th><th>{t("모드")}</th><th>{t("부족한 설정")}</th><th></th></tr></thead>
          <tbody>
            <tr><td>Claude AI</td><td><span className={`badge ${status.ai_mode === "claude" ? "s-EXECUTED" : "mock"}`}>{status.ai_mode === "claude" ? "LIVE" : "MOCK"}</span></td><td className="small">{status.ai_mode === "claude" ? "" : "ANTHROPIC_API_KEY"}</td><td /></tr>
            {Object.entries(status.connectors).map(([k, c]) => (
              <tr key={k}><td>{PLATFORMS[k] || "Meta Ads"}</td><td><span className={`badge ${c.mode === "live" ? "s-EXECUTED" : "mock"}`}>{c.mode.toUpperCase()}</span></td><td className="small">{c.missing.join(", ")}</td>
                <td>{OAUTH[k] && <button className="sm" disabled={busy} onClick={() => connect(k)}>{t("{p} 연결 (OAuth)", { p: OAUTH[k] })}</button>}</td></tr>
            ))}
          </tbody>
        </table></div>
        <p className="hint">OAuth Redirect URI: <span className="mono">{data.public_base_url}/api/oauth/&lt;instagram|tiktok|x&gt;/callback</span> — {t("각 개발자 포털에 그대로 등록하세요. 먼저 아래에서 App ID / Client ID·Secret 을 저장해야 합니다.")}</p>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>{t("SNS 사용 / 자동 승인")}</h2>
          <table><thead><tr><th>SNS</th><th>{t("사용")}</th><th>{t("자동 승인")}</th></tr></thead><tbody>
            {Object.keys(PLATFORMS).map((p) => (
              <tr key={p}><td>{PLATFORMS[p]}</td>
                <td><input type="checkbox" checked={!!s.platforms_enabled[p]} onChange={(e) => put("platforms_enabled", { ...s.platforms_enabled, [p]: e.target.checked })} /></td>
                <td><input type="checkbox" checked={!!s.auto_approve[p]} onChange={(e) => (!e.target.checked || window.confirm(t("{p} 콘텐츠를 승인 없이 자동 예약할까요?", { p: PLATFORMS[p] }) + (data.dry_run ? "" : " " + t("(LIVE 모드: 실제 게시됩니다)")))) && put("auto_approve", { ...s.auto_approve, [p]: e.target.checked })} /></td></tr>
            ))}</tbody></table>
          <p className="hint">{t("자동 승인을 켠 SNS 는 Brand Guardian 을 통과한 콘텐츠만 바로 제안 시간에 예약됩니다. 기본값은 모두 수동 승인입니다.")}</p>
        </div>
        <div className="card">
          <h2>{t("자동 생성 / 게시 시간")} ({tzLabel()})</h2>
          <GenForm gen={s.generation} onSave={(val) => put("generation", val)} />
          <h3 style={{ marginTop: 16 }}>{t("게시 시간 테스트 후보 (쉼표 구분)")}</h3>
          <p className="hint">{t("데이터가 쌓이면 실제 추천 시간은 우리 계정 성과로 자동 학습됩니다 (트렌드 · 게시 시간 메뉴).")}</p>
          {Object.keys(PLATFORMS).map((p) => (
            <div key={p} className="field row"><span style={{ width: 90 }}>{PLATFORMS[p]}</span>
              <input defaultValue={(s.posting_times[p] || []).join(", ")} style={{ flex: 1 }}
                onBlur={(e) => {
                  const val = e.target.value.split(",").map((x) => x.trim()).filter((x) => /^\d{1,2}:\d{2}$/.test(x));
                  if (val.join(",") !== (s.posting_times[p] || []).join(",")) put("posting_times", { ...s.posting_times, [p]: val });
                }} /></div>
          ))}
          <h3 style={{ marginTop: 16 }}>{t("리포트 전송 채널")}</h3>
          {["file", "slack", "discord"].map((ch) => (
            <label key={ch} className="row" style={{ fontWeight: 400 }}><input type="checkbox" disabled={ch === "file"} checked={s.reports.notify_channels.includes(ch)}
              onChange={(e) => put("reports", { ...s.reports, notify_channels: e.target.checked ? [...s.reports.notify_channels, ch] : s.reports.notify_channels.filter((x) => x !== ch) })} /> {ch}{ch !== "file" && ` (${t("Webhook URL 필요")})`}</label>
          ))}
          <label className="row" style={{ fontWeight: 400, marginTop: 12 }}><input type="checkbox" checked={!!s.ads_enabled} onChange={(e) => put("ads_enabled", e.target.checked)} /> {t("광고 데이터 자동 수집/분석 (매일 06:00)")}</label>
        </div>
      </div>

      <div className="card">
        <div className="spread"><h2>API Key / Token</h2><button className="primary" disabled={busy || !Object.values(secrets).some((x) => x)} onClick={saveSecrets}>💾 {t("입력한 값 저장")}</button></div>
        <p className="hint">{t("입력한 값은 서버의 data/secrets.env 에만 저장되고(Git 제외), 화면에는 마지막 4자리만 표시됩니다. 비밀번호는 입력하지 마세요 — 토큰은 OAuth 연결 버튼으로 받는 것을 권장합니다.")}</p>
        <div className="grid cols-2">
          {SECRET_GROUPS.map(([title, keys]) => (
            <div key={title}>
              <h3>{title}</h3>
              {keys.map((k) => (
                <div className="field" key={k}>
                  <label>{k} {data.secrets[k]?.configured ? <span className="badge s-EXECUTED">{t("설정됨")} {data.secrets[k].masked}</span> : <span className="badge">{t("미설정")}</span>}</label>
                  <input type={isSecret(k) ? "password" : "text"} autoComplete="off" value={secrets[k] || ""} placeholder={data.secrets[k]?.configured ? t("변경할 때만 입력") : ""} onChange={(e) => setSecrets({ ...secrets, [k]: e.target.value })} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function GenForm({ gen, onSave }) {
  const [g, setG] = useState(gen);
  return (
    <div className="row">
      <div className="field"><label>{t("하루 아이디어 수")}</label><input type="number" min="1" max="10" value={g.ideas_per_day} onChange={(e) => setG({ ...g, ideas_per_day: Math.max(1, Number(e.target.value)) })} style={{ width: 90 }} /></div>
      <div className="field"><label>{t("생성 시각")}</label><input type="time" value={`${String(g.hour).padStart(2, "0")}:${String(g.minute).padStart(2, "0")}`} onChange={(e) => { const [h, m] = e.target.value.split(":").map(Number); setG({ ...g, hour: h, minute: m }); }} style={{ width: 120 }} /></div>
      <button onClick={() => onSave(g)}>{t("저장")}</button>
      <div className="hint" style={{ width: "100%" }}>{t("아이디어 1개 → 사용 중인 SNS 별로 각각 생성 (하루 최소 5개 보장)")}</div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useToast } from "../components/ui";
import { PLATFORMS } from "../util";

const SECRET_GROUPS = [
  ["Claude AI", ["ANTHROPIC_API_KEY"]],
  ["Instagram (Instagram Login)", ["INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"]],
  ["Facebook 페이지", ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"]],
  ["Meta 광고", ["META_AD_ACCOUNT_ID", "META_ADS_ACCESS_TOKEN"]],
  ["TikTok", ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"]],
  ["X", ["X_CLIENT_ID", "X_CLIENT_SECRET", "X_ACCESS_TOKEN", "X_REFRESH_TOKEN"]],
  ["미디어 / 알림", ["PUBLIC_MEDIA_BASE_URL", "SLACK_WEBHOOK_URL", "DISCORD_WEBHOOK_URL"]],
];
const OAUTH = { instagram: "Instagram", tiktok: "TikTok", x: "X" };

export default function Settings({ status, onChange }) {
  const [data, setData] = useState(null);
  const [secrets, setSecrets] = useState({});
  const [run, busy] = useAction();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const load = () => api.get("/api/settings").then(setData);
  useEffect(() => {
    load();
    if (params.get("oauth")) {
      toast(params.get("status") === "ok" ? `${params.get("oauth")} 연결 완료!` : `${params.get("oauth")} 연결 실패: ${params.get("msg")}`, params.get("status") === "ok" ? "ok" : "err");
      setParams({});
      onChange?.();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!data) return <p>불러오는 중…</p>;
  const s = data.settings;
  const put = (key, value) => run(() => api.put(`/api/settings/${key}`, { value }), "저장했습니다").then(() => { load(); onChange?.(); });
  const saveSecrets = () => {
    const clean = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v && v.trim()));
    if (!Object.keys(clean).length) return;
    run(() => api.post("/api/settings/secrets", { secrets: clean }), "저장했습니다. 연결 상태를 확인하세요.").then(() => { setSecrets({}); load(); onChange?.(); });
  };
  const connect = async (p) => {
    const r = await run(() => api.get(`/api/oauth/${p}/start`));
    if (r) window.location.href = r.authorize_url;
  };

  return (
    <>
      <div className="topbar"><div><h1>설정</h1><div className="muted small">모드: {data.dry_run ? "DRY RUN (안전)" : "LIVE"} — DRY RUN 해제는 .env 파일의 DRY_RUN=false 로만 가능합니다 (README 참고).</div></div></div>

      <div className="card">
        <h2>연결 상태</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>서비스</th><th>모드</th><th>부족한 설정</th><th></th></tr></thead>
          <tbody>
            <tr><td>Claude AI</td><td><span className={`badge ${status.ai_mode === "claude" ? "s-EXECUTED" : "mock"}`}>{status.ai_mode === "claude" ? "LIVE" : "MOCK"}</span></td><td className="small">{status.ai_mode === "claude" ? "" : "ANTHROPIC_API_KEY"}</td><td /></tr>
            {Object.entries(status.connectors).map(([k, v]) => (
              <tr key={k}><td>{PLATFORMS[k] || "Meta 광고"}</td><td><span className={`badge ${v.mode === "live" ? "s-EXECUTED" : "mock"}`}>{v.mode.toUpperCase()}</span></td><td className="small">{v.missing.join(", ")}</td>
                <td>{OAUTH[k] && <button className="sm" disabled={busy} onClick={() => connect(k)}>{OAUTH[k]} 연결 (OAuth)</button>}</td></tr>
            ))}
          </tbody>
        </table></div>
        <p className="hint">OAuth Redirect URI: <span className="mono">{data.public_base_url}/api/oauth/&lt;instagram|tiktok|x&gt;/callback</span> — 각 개발자 포털에 그대로 등록하세요. 먼저 아래에서 App ID / Client ID·Secret 을 저장해야 합니다.</p>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h2>SNS 사용 / 자동 승인</h2>
          <table><thead><tr><th>SNS</th><th>사용</th><th>자동 승인</th></tr></thead><tbody>
            {Object.keys(PLATFORMS).map((p) => (
              <tr key={p}><td>{PLATFORMS[p]}</td>
                <td><input type="checkbox" checked={!!s.platforms_enabled[p]} onChange={(e) => put("platforms_enabled", { ...s.platforms_enabled, [p]: e.target.checked })} /></td>
                <td><input type="checkbox" checked={!!s.auto_approve[p]} onChange={(e) => (!e.target.checked || window.confirm(`${PLATFORMS[p]} 콘텐츠를 승인 없이 자동 예약할까요?${data.dry_run ? "" : " (LIVE 모드: 실제 게시됩니다)"}`)) && put("auto_approve", { ...s.auto_approve, [p]: e.target.checked })} /></td></tr>
            ))}</tbody></table>
          <p className="hint">자동 승인을 켠 SNS 는 AI 생성 후 바로 제안 시간에 예약됩니다 (금지어 포함 시 제외). 기본값은 모두 수동 승인입니다.</p>
        </div>
        <div className="card">
          <h2>자동 생성 / 게시 시간</h2>
          <GenForm gen={s.generation} onSave={(v) => put("generation", v)} />
          <h3 style={{ marginTop: 16 }}>기본 게시 시간 (현지, 쉼표 구분)</h3>
          {Object.keys(PLATFORMS).map((p) => (
            <div key={p} className="field row"><span style={{ width: 90 }}>{PLATFORMS[p]}</span>
              <input defaultValue={(s.posting_times[p] || []).join(", ")} style={{ flex: 1 }}
                onBlur={(e) => {
                  const v = e.target.value.split(",").map((x) => x.trim()).filter((x) => /^\d{1,2}:\d{2}$/.test(x));
                  if (v.join(",") !== (s.posting_times[p] || []).join(",")) put("posting_times", { ...s.posting_times, [p]: v });
                }} /></div>
          ))}
          <h3 style={{ marginTop: 16 }}>리포트 전송 채널</h3>
          {["file", "slack", "discord"].map((ch) => (
            <label key={ch} className="row" style={{ fontWeight: 400 }}><input type="checkbox" disabled={ch === "file"} checked={s.reports.notify_channels.includes(ch)}
              onChange={(e) => put("reports", { ...s.reports, notify_channels: e.target.checked ? [...s.reports.notify_channels, ch] : s.reports.notify_channels.filter((x) => x !== ch) })} /> {ch}{ch !== "file" && " (Webhook URL 필요)"}</label>
          ))}
          <label className="row" style={{ fontWeight: 400, marginTop: 12 }}><input type="checkbox" checked={!!s.ads_enabled} onChange={(e) => put("ads_enabled", e.target.checked)} /> 광고 데이터 자동 수집/분석 (매일 06:00)</label>
        </div>
      </div>

      <div className="card">
        <div className="spread"><h2>API Key / Token</h2><button className="primary" disabled={busy || !Object.values(secrets).some((v) => v)} onClick={saveSecrets}>💾 입력한 값 저장</button></div>
        <p className="hint">입력한 값은 서버의 data/secrets.env 에만 저장되고(Git 제외), 화면에는 마지막 4자리만 표시됩니다. 비밀번호는 입력하지 마세요 — 토큰은 OAuth 연결 버튼으로 받는 것을 권장합니다.</p>
        <div className="grid cols-2">
          {SECRET_GROUPS.map(([title, keys]) => (
            <div key={title}>
              <h3>{title}</h3>
              {keys.map((k) => (
                <div className="field" key={k}>
                  <label>{k} {data.secrets[k]?.configured ? <span className="badge s-EXECUTED">설정됨 {data.secrets[k].masked}</span> : <span className="badge">미설정</span>}</label>
                  <input type={/SECRET|TOKEN|KEY$/.test(k) && !k.endsWith("CLIENT_KEY") ? "password" : "text"} autoComplete="off" value={secrets[k] || ""} placeholder={data.secrets[k]?.configured ? "변경할 때만 입력" : ""} onChange={(e) => setSecrets({ ...secrets, [k]: e.target.value })} />
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
      <div className="field"><label>하루 생성 개수</label><input type="number" min="5" max="20" value={g.daily_count} onChange={(e) => setG({ ...g, daily_count: Math.max(5, Number(e.target.value)) })} style={{ width: 90 }} /></div>
      <div className="field"><label>생성 시각</label><input type="time" value={`${String(g.hour).padStart(2, "0")}:${String(g.minute).padStart(2, "0")}`} onChange={(e) => { const [h, m] = e.target.value.split(":").map(Number); setG({ ...g, hour: h, minute: m }); }} style={{ width: 120 }} /></div>
      <button onClick={() => onSave(g)}>저장</button>
    </div>
  );
}

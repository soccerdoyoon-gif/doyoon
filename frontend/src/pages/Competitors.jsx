import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, MockBadge, useAction } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime } from "../util";

const EMPTY_OBS = { topic: "", content_format: "", hook_pattern: "", public_reaction: "", posts_per_week: "", post_url: "", notes: "" };

export default function Competitors() {
  const [list, setList] = useState([]);
  const [insight, setInsight] = useState(null);
  const [form, setForm] = useState({ name: "", platform: "instagram", handle: "", url: "" });
  const [obs, setObs] = useState({});
  const [run, busy] = useAction();
  const load = async () => {
    const [l, i] = await Promise.all([api.get("/api/competitors"), api.get("/api/insights?kind=competitor&limit=1")]);
    setList(l); setInsight(i[0] || null);
  };
  useEffect(() => {
    load();
  }, []);
  const o = (cid) => obs[cid] || EMPTY_OBS;
  const setO = (cid, k, v) => setObs({ ...obs, [cid]: { ...o(cid), [k]: v } });
  return (
    <>
      <div className="topbar">
        <div><h1>{t("경쟁사 분석 (일본)")}</h1><div className="muted small">{t("공개 페이지에서 직접 확인한 내용만 기록하세요. 자동 스크래핑이나 로그인 우회는 하지 않습니다. AI 는 복제가 아닌 차별화 아이디어를 제안합니다.")}</div></div>
        <button className="primary" disabled={busy} onClick={() => run(() => api.post("/api/competitors/analyze"), t("분석 완료")).then(load)}>🤖 {t("차별화 분석")}</button>
      </div>
      {insight && (
        <div className="card">
          <div className="spread"><h2>{t("AI 분석")} <MockBadge show={insight.source !== "ai"} label="MOCK AI" /></h2><span className="small muted">{fmtDateTime(insight.created_at)}</span></div>
          <p>{insight.data.summary}</p>
          <div className="grid cols-2 small">
            {[["competitor_patterns", "경쟁사 패턴"], ["gaps_and_opportunities", "빈틈과 기회"], ["differentiation_ideas", "차별화 아이디어"], ["avoid", "피할 것"]].map(([k, l]) => (
              <div key={k}><b>{t(l)}</b><ul>{(insight.data[k] || []).map((x, i) => <li key={i}>{x}</li>)}</ul></div>
            ))}
          </div>
        </div>
      )}
      <div className="card row">
        <input placeholder={t("경쟁사 이름")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ maxWidth: 200 }} />
        <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} style={{ maxWidth: 140 }}><option>instagram</option><option>tiktok</option><option>x</option><option>facebook</option></select>
        <input placeholder={t("@계정")} value={form.handle} onChange={(e) => setForm({ ...form, handle: e.target.value })} style={{ maxWidth: 160 }} />
        <input placeholder={t("공개 URL")} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} style={{ maxWidth: 260 }} />
        <button disabled={!form.name} onClick={() => run(() => api.post("/api/competitors", form), t("추가했습니다")).then(() => { setForm({ name: "", platform: "instagram", handle: "", url: "" }); load(); })}>＋ {t("경쟁사 추가")}</button>
      </div>
      {list.length === 0 ? <Empty>{t("등록된 경쟁사가 없습니다.")}</Empty> : list.map((c) => (
        <div key={c.id} className="card">
          <div className="spread">
            <h2>{c.name} <span className="badge">{c.platform}</span> <span className="small muted">{c.handle}</span> {c.url && <a className="small" href={c.url} target="_blank" rel="noreferrer">{t("공개 페이지")}</a>}</h2>
            <button className="sm danger" onClick={() => window.confirm(t("{n} 과(와) 관찰 기록을 삭제할까요?", { n: c.name })) && run(() => api.del(`/api/competitors/${c.id}`)).then(load)}>{t("삭제")}</button>
          </div>
          {c.observations.length > 0 && (
            <div className="table-wrap"><table className="small">
              <thead><tr><th>{t("날짜")}</th><th>{t("주제")}</th><th>{t("형식")}</th><th>{t("Hook 패턴")}</th><th>{t("공개 반응")}</th><th className="num">{t("주당 게시")}</th><th></th></tr></thead>
              <tbody>{c.observations.map((x) => (
                <tr key={x.id}><td>{fmtDateTime(x.observed_at)}</td><td>{x.topic}</td><td>{x.content_format}</td><td>{x.hook_pattern}</td><td>{x.public_reaction}</td><td className="num">{x.posts_per_week ?? "-"}</td>
                  <td><button className="sm" onClick={() => run(() => api.del(`/api/competitors/observations/${x.id}`)).then(load)}>✕</button></td></tr>
              ))}</tbody>
            </table></div>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <input placeholder={t("주제")} value={o(c.id).topic} onChange={(e) => setO(c.id, "topic", e.target.value)} style={{ maxWidth: 160 }} />
            <input placeholder={t("형식 (reel, carousel…)")} value={o(c.id).content_format} onChange={(e) => setO(c.id, "content_format", e.target.value)} style={{ maxWidth: 160 }} />
            <input placeholder={t("Hook 패턴")} value={o(c.id).hook_pattern} onChange={(e) => setO(c.id, "hook_pattern", e.target.value)} style={{ maxWidth: 200 }} />
            <input placeholder={t("공개 반응 (예: 좋아요 약 2천)")} value={o(c.id).public_reaction} onChange={(e) => setO(c.id, "public_reaction", e.target.value)} style={{ maxWidth: 200 }} />
            <input type="number" placeholder={t("주당 게시 수")} value={o(c.id).posts_per_week} onChange={(e) => setO(c.id, "posts_per_week", e.target.value)} style={{ maxWidth: 120 }} />
            <button onClick={() => run(() => api.post(`/api/competitors/${c.id}/observations`, { ...o(c.id), posts_per_week: o(c.id).posts_per_week === "" ? null : Number(o(c.id).posts_per_week) }), t("기록했습니다")).then(() => { setObs({ ...obs, [c.id]: EMPTY_OBS }); load(); })}>＋ {t("관찰 기록")}</button>
          </div>
        </div>
      ))}
    </>
  );
}

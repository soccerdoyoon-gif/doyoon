import { useEffect, useState } from "react";
import { api, qs } from "../api";
import ContentEditor, { ContentCard, PLATFORM_OPTIONS } from "../components/ContentEditor";
import { Empty, Modal, useAction } from "../components/ui";
import { STATUS_LABEL } from "../util";

const TABS = ["", "READY_FOR_REVIEW", "DRAFT", "APPROVED", "SCHEDULED", "PUBLISHED", "FAILED", "REJECTED"];

export default function Content({ onChange }) {
  const [status, setStatus] = useState("READY_FOR_REVIEW");
  const [platform, setPlatform] = useState("");
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null);
  const [gen, setGen] = useState(null);
  const [run, busy] = useAction();

  const load = () => api.get("/api/content" + qs({ status, platform })).then(setItems);
  useEffect(() => {
    load();
  }, [status, platform]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async () => {
    const r = await run(() => api.post("/api/content/generate", { count: Number(gen.count), platforms: gen.platforms, theme: gen.theme }), null);
    if (r) {
      setGen(null);
      setStatus("READY_FOR_REVIEW");
      load();
      onChange?.();
    }
  };
  const newManual = async () => {
    const p = window.prompt("플랫폼 (instagram / tiktok / x / facebook)", "instagram");
    if (!p) return;
    const r = await run(() => api.post("/api/content", { platform: p.trim().toLowerCase(), title: "새 콘텐츠" }));
    if (r) {
      load();
      setOpen(r.id);
    }
  };

  return (
    <>
      <div className="topbar">
        <div><h1>콘텐츠</h1><div className="muted small">AI 가 만든 후보는 점수 높은 순으로 정렬됩니다. 점수는 내부 우선순위용이며 성과를 보장하지 않습니다.</div></div>
        <div className="row">
          <button onClick={newManual}>＋ 직접 작성</button>
          <button className="primary" onClick={() => setGen({ count: 6, platforms: [], theme: "" })}>✨ AI 콘텐츠 생성</button>
        </div>
      </div>
      <div className="tabs">
        {TABS.map((t) => <button key={t} className={status === t ? "active" : ""} onClick={() => setStatus(t)}>{t ? STATUS_LABEL[t] : "전체"}</button>)}
        <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={{ width: 140, marginLeft: "auto" }}>
          <option value="">모든 SNS</option>
          {PLATFORM_OPTIONS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {items.length === 0 ? <Empty>콘텐츠가 없습니다.</Empty> : (
        <div className="grid cols-3">{items.map((it) => <ContentCard key={it.id} item={it} onOpen={() => setOpen(it.id)} />)}</div>
      )}
      {open && <ContentEditor id={open} onClose={() => { setOpen(null); load(); }} onChange={() => { load(); onChange?.(); }} />}
      {gen && (
        <Modal title="AI 콘텐츠 생성" onClose={() => setGen(null)} footer={<button className="primary" disabled={busy} onClick={generate}>{busy ? "생성 중… (최대 1~2분)" : "생성"}</button>}>
          <p className="small muted">브랜드 프로필, 과거 성과, 최신 AI 분석을 반영해 후보를 만듭니다. 생성된 콘텐츠는 바로 게시되지 않고 '승인 대기' 상태가 됩니다.</p>
          <div className="field"><label>개수 (최소 5)</label><input type="number" min="5" max="20" value={gen.count} onChange={(e) => setGen({ ...gen, count: e.target.value })} /></div>
          <div className="field"><label>SNS (비우면 설정된 SNS 전체)</label>
            <div className="row">{PLATFORM_OPTIONS.map(([k, v]) => (
              <label key={k} className="row" style={{ fontWeight: 400 }}>
                <input type="checkbox" checked={gen.platforms.includes(k)} onChange={(e) => setGen({ ...gen, platforms: e.target.checked ? [...gen.platforms, k] : gen.platforms.filter((x) => x !== k) })} /> {v}
              </label>))}
            </div>
          </div>
          <div className="field"><label>주제 / 요청 (선택)</label><input value={gen.theme} onChange={(e) => setGen({ ...gen, theme: e.target.value })} placeholder="예: 가을 신상품 런칭, 할인 이벤트" /></div>
        </Modal>
      )}
    </>
  );
}

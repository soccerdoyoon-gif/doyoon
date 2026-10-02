import { useEffect, useState } from "react";
import { api } from "../api";
import AdActions from "../components/AdActions";
import ContentEditor, { ContentCard } from "../components/ContentEditor";
import { Empty, useAction } from "../components/ui";

export default function Approvals({ onChange }) {
  const [items, setItems] = useState([]);
  const [actions, setActions] = useState([]);
  const [selected, setSelected] = useState([]);
  const [open, setOpen] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [run, busy] = useAction();

  const load = async () => {
    const [c, a, s] = await Promise.all([api.get("/api/content?status=READY_FOR_REVIEW"), api.get("/api/ads/actions?status=PENDING"), api.get("/api/system/status")]);
    setItems(c);
    setActions(a);
    setDryRun(s.dry_run);
    setSelected([]);
    onChange?.();
  };
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const bulk = async () => {
    const r = await run(() => api.post("/api/content/bulk-approve", { ids: selected, use_suggested_time: true }));
    if (r) {
      const errs = Object.entries(r.errors);
      if (errs.length) alert(`일부 실패:\n${errs.map(([id, e]) => `#${id}: ${e}`).join("\n")}`);
      load();
    }
  };

  return (
    <>
      <div className="topbar">
        <div><h1>승인 대기</h1><div className="muted small">AI 가 만든 콘텐츠와 광고 작업은 여기서 승인해야 실행됩니다.</div></div>
      </div>
      <div className="card">
        <div className="spread" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>콘텐츠 ({items.length})</h2>
          <div className="row">
            <button className="sm" onClick={() => setSelected(selected.length === items.length ? [] : items.map((i) => i.id))}>{selected.length === items.length && items.length ? "선택 해제" : "전체 선택"}</button>
            <button className="sm primary" disabled={!selected.length || busy} onClick={bulk}>선택 {selected.length}개 승인 + 제안 시간에 예약</button>
          </div>
        </div>
        {items.length === 0 ? <Empty>승인 대기 콘텐츠가 없습니다. 콘텐츠 메뉴에서 AI 생성을 눌러보세요.</Empty> : (
          <div className="grid cols-3">
            {items.map((it) => (
              <ContentCard key={it.id} item={it} onOpen={() => setOpen(it.id)} selectable selected={selected.includes(it.id)}
                onSelect={(on) => setSelected(on ? [...selected, it.id] : selected.filter((x) => x !== it.id))} />
            ))}
          </div>
        )}
      </div>
      <div className="card">
        <h2>광고 작업 ({actions.length})</h2>
        <AdActions actions={actions} onChange={load} dryRun={dryRun} />
      </div>
      {open && <ContentEditor id={open} onClose={() => { setOpen(null); load(); }} onChange={load} />}
    </>
  );
}

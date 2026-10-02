import { useEffect, useState } from "react";
import { api } from "../api";
import AdActions from "../components/AdActions";
import ContentEditor, { ContentCard } from "../components/ContentEditor";
import { Empty, useAction } from "../components/ui";
import { t } from "../i18n";

export default function Approvals({ onChange }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [actions, setActions] = useState([]);
  const [selected, setSelected] = useState([]);
  const [open, setOpen] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [run, busy] = useAction();

  const load = async () => {
    const [c, d, a, s] = await Promise.all([api.get("/api/content?status=READY_FOR_REVIEW"), api.get("/api/content?status=DRAFT"),
      api.get("/api/ads/actions?status=PENDING"), api.get("/api/system/status")]);
    setItems(c);
    setDrafts(d.filter((x) => x.review_note));
    setActions(a);
    setDryRun(s.dry_run);
    setSelected([]);
    onChange?.();
  };
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const bulk = async () => {
    if (!dryRun && !window.confirm(t("⚠️ LIVE 모드입니다. 승인한 콘텐츠는 예약 시간에 실제 SNS 에 게시됩니다. 계속할까요?"))) return;
    const r = await run(() => api.post("/api/content/bulk-approve", { ids: selected, use_suggested_time: true }));
    if (r) {
      const errs = Object.entries(r.errors);
      if (errs.length) alert(`${t("일부 실패")}:\n${errs.map(([id, e]) => `#${id}: ${e}`).join("\n")}`);
      load();
    }
  };

  return (
    <>
      <div className="topbar">
        <div><h1>{t("승인 대기")}</h1><div className="muted small">{t("AI 가 만든 콘텐츠와 광고 작업은 여기서 승인해야 실행됩니다. 승인하면 일본 시간(JST) 기준 제안 시간에 예약됩니다.")}</div></div>
      </div>
      <div className="card">
        <div className="spread" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>{t("콘텐츠")} ({items.length})</h2>
          <div className="row">
            <button className="sm" onClick={() => setSelected(selected.length === items.length ? [] : items.map((i) => i.id))}>{selected.length === items.length && items.length ? t("선택 해제") : t("전체 선택")}</button>
            <button className="sm primary" disabled={!selected.length || busy} onClick={bulk}>{t("선택 {n}개 승인 + 제안 시간에 예약", { n: selected.length })}</button>
          </div>
        </div>
        {items.length === 0 ? <Empty>{t("승인 대기 콘텐츠가 없습니다. 콘텐츠 제작 메뉴에서 AI 콘텐츠 제작을 눌러보세요.")}</Empty> : (
          <div className="grid cols-3">
            {items.map((it) => (
              <ContentCard key={it.id} item={it} onOpen={() => setOpen(it.id)} selectable selected={selected.includes(it.id)}
                onSelect={(on) => setSelected(on ? [...selected, it.id] : selected.filter((x) => x !== it.id))} />
            ))}
          </div>
        )}
      </div>
      {drafts.length > 0 && (
        <div className="card">
          <h2>🛡️ {t("Brand Guardian 이 보류한 콘텐츠")} ({drafts.length})</h2>
          <p className="small muted">{t("일본어 표현·금지어·과장 표현 등의 문제로 승인 단계로 보내지 않았습니다. 수정 후 [검토 요청]을 누르세요.")}</p>
          <div className="grid cols-3">{drafts.map((it) => <ContentCard key={it.id} item={it} onOpen={() => setOpen(it.id)} />)}</div>
        </div>
      )}
      <div className="card">
        <h2>{t("광고 작업")} ({actions.length})</h2>
        <AdActions actions={actions} onChange={load} dryRun={dryRun} />
      </div>
      {open && <ContentEditor id={open} onClose={() => { setOpen(null); load(); }} onChange={load} />}
    </>
  );
}

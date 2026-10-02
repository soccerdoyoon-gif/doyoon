import { useEffect, useState } from "react";
import { api, qs } from "../api";
import ContentEditor from "../components/ContentEditor";
import { MockBadge, PlatformBadge, StatusBadge, useAction } from "../components/ui";
import { t } from "../i18n";
import { addDaysKey, dayKey, fmtDayKey, fmtTime, hourOf, keyToISO, parseUTC, PLATFORMS, statusLabel, todayKey, tzLabel, weekdayOfKey } from "../util";

function Item({ it, onOpen }) {
  const draggable = it.status !== "PUBLISHED";
  const thumb = (it.assets || []).find((a) => a.kind === "thumbnail" || a.kind === "image");
  return (
    <div
      className={`cal-item st-${it.status}`}
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(it.id))}
      onClick={() => onOpen(it.id)}
      title={`${PLATFORMS[it.platform]} · ${statusLabel(it.status)}${it.campaign_name ? " · " + it.campaign_name : ""}\n${it.caption || ""}`}
    >
      <div className="spread"><b>{fmtTime(it.calendar_time)}</b><PlatformBadge p={it.platform} /></div>
      {thumb && <img src={thumb.url} alt="" style={{ width: "100%", maxHeight: 90, objectFit: "cover", borderRadius: 4, marginTop: 4 }} />}
      <div>{it.title || it.hook}</div>
      <div className="row" style={{ marginTop: 3 }}>
        <StatusBadge s={it.status} />
        {it.campaign_name && <span className="badge">{it.campaign_name}</span>}
        {(it.assets || []).some((a) => a.kind === "video") && <span title={t("영상")}>🎬</span>}
        {(it.media_path || it.media_url) && <span title={t("미디어 첨부")}>🖼️</span>}
        {it.is_dry_run && <MockBadge label="DRY" />}
      </div>
      {it.status === "PUBLISHED" && it.latest_metrics && <div className="hint">❤ {it.latest_metrics.likes ?? "-"} · 👁 {it.latest_metrics.views ?? it.latest_metrics.impressions ?? "-"}</div>}
      {it.status === "FAILED" && <div className="hint" style={{ color: "var(--bad)" }}>{it.last_error}</div>}
      {it.status === "READY_FOR_REVIEW" && <div className="hint">{t("제안 시간 (승인 전)")}</div>}
    </div>
  );
}

export default function CalendarPage() {
  const [view, setView] = useState("week");
  const [anchor, setAnchor] = useState(todayKey());
  const [items, setItems] = useState([]);
  const [dropKey, setDropKey] = useState(null);
  const [open, setOpen] = useState(null);
  const [run] = useAction();

  const startKey = view === "week" ? addDaysKey(anchor, -((weekdayOfKey(anchor) + 6) % 7)) : anchor;
  const days = view === "week" ? 7 : 1;
  const load = () => api.get("/api/calendar" + qs({ start: keyToISO(startKey), end: keyToISO(addDaysKey(startKey, days)) })).then(setItems);
  useEffect(() => {
    load();
  }, [view, anchor]); // eslint-disable-line react-hooks/exhaustive-deps

  const move = async (id, iso) => {
    setDropKey(null);
    const r = await run(() => api.patch(`/api/calendar/${id}`, { scheduled_at: iso }), t("일정을 변경했습니다"));
    if (r) load();
  };
  const findItem = (e) => items.find((x) => x.id === Number(e.dataTransfer.getData("text/plain")));
  const onDropDay = (e, key) => {
    e.preventDefault();
    const it = findItem(e);
    if (!it) return;
    const [hh, mm] = fmtTime(it.calendar_time).split(":").map(Number);
    move(it.id, keyToISO(key, hh, mm));
  };
  const onDropHour = (e, hour) => {
    e.preventDefault();
    const it = findItem(e);
    if (!it) return;
    const mm = Number(fmtTime(it.calendar_time).split(":")[1]);
    move(it.id, keyToISO(anchor, hour, mm));
  };
  const dz = (key, handler) => ({
    onDragOver: (e) => { e.preventDefault(); setDropKey(key); },
    onDragLeave: () => setDropKey(null),
    onDrop: handler,
  });

  const step = view === "week" ? 7 : 1;
  return (
    <>
      <div className="topbar">
        <div><h1>{t("콘텐츠 캘린더")}</h1><div className="muted small">{t("모든 시간은 {tz} 기준입니다. 카드를 끌어서 다른 날짜/시간에 놓으면 게시 일정이 바뀝니다. 게시 완료 콘텐츠는 이동할 수 없습니다.", { tz: tzLabel() })}</div></div>
        <div className="row">
          <button onClick={() => setAnchor(addDaysKey(anchor, -step))}>◀</button>
          <button onClick={() => setAnchor(todayKey())}>{t("오늘")}</button>
          <button onClick={() => setAnchor(addDaysKey(anchor, step))}>▶</button>
          <div className="tabs" style={{ margin: 0, border: "none" }}>
            <button className={view === "day" ? "active" : ""} onClick={() => setView("day")}>{t("일간")}</button>
            <button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>{t("주간")}</button>
          </div>
        </div>
      </div>
      <h2>{fmtDayKey(startKey)} {view === "week" && `〜 ${fmtDayKey(addDaysKey(startKey, 6))}`} <span className="small muted">({tzLabel()})</span></h2>
      {view === "week" ? (
        <div className="cal-week">
          {Array.from({ length: 7 }, (_, i) => addDaysKey(startKey, i)).map((key) => {
            const list = items.filter((it) => dayKey(parseUTC(it.calendar_time)) === key);
            return (
              <div key={key} className={`cal-day ${key === todayKey() ? "today" : ""} ${dropKey === key ? "drop" : ""}`} {...dz(key, (e) => onDropDay(e, key))}>
                <h4><button className="link" onClick={() => { setAnchor(key); setView("day"); }}>{fmtDayKey(key)}</button> <span className="muted">({list.length})</span></h4>
                {list.map((it) => <Item key={it.id} it={it} onOpen={setOpen} />)}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card">
          <div className="cal-hours">
            {Array.from({ length: 24 }, (_, h) => {
              const list = items.filter((it) => hourOf(it.calendar_time) === h);
              return [
                <div key={`l${h}`} className="cal-hour small muted">{String(h).padStart(2, "0")}:00</div>,
                <div key={`c${h}`} className={`cal-hour ${dropKey === h ? "drop" : ""}`} {...dz(h, (e) => onDropHour(e, h))}>
                  <div className="grid cols-3">{list.map((it) => <Item key={it.id} it={it} onOpen={setOpen} />)}</div>
                </div>,
              ];
            })}
          </div>
        </div>
      )}
      {open && <ContentEditor id={open} onClose={() => { setOpen(null); load(); }} onChange={load} />}
    </>
  );
}

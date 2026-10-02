import { useEffect, useState } from "react";
import { api, qs } from "../api";
import ContentEditor from "../components/ContentEditor";
import { MockBadge, PlatformBadge, StatusBadge, useAction } from "../components/ui";
import { addDays, parseUTC, PLATFORMS, startOfDay, STATUS_LABEL } from "../util";

const sameDay = (a, b) => a.toDateString() === b.toDateString();

function Item({ it, onOpen }) {
  const t = parseUTC(it.calendar_time);
  const draggable = it.status !== "PUBLISHED";
  return (
    <div
      className={`cal-item st-${it.status}`}
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(it.id))}
      onClick={() => onOpen(it.id)}
      title={`${PLATFORMS[it.platform]} · ${STATUS_LABEL[it.status]}${it.campaign_name ? " · " + it.campaign_name : ""}\n${it.caption || ""}`}
    >
      <div className="spread"><b>{t.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</b><PlatformBadge p={it.platform} /></div>
      <div>{it.title || it.hook}</div>
      <div className="row" style={{ marginTop: 3 }}>
        <StatusBadge s={it.status} />
        {it.campaign_name && <span className="badge">{it.campaign_name}</span>}
        {(it.media_path || it.media_url) && <span title="미디어 첨부">🖼️</span>}
        {it.is_dry_run && <MockBadge label="DRY" />}
      </div>
      {it.status === "PUBLISHED" && it.latest_metrics && <div className="hint">❤ {it.latest_metrics.likes ?? "-"} · 👁 {it.latest_metrics.views ?? it.latest_metrics.impressions ?? "-"}</div>}
      {it.status === "FAILED" && <div className="hint" style={{ color: "var(--bad)" }}>{it.last_error}</div>}
      {it.status === "READY_FOR_REVIEW" && <div className="hint">제안 시간 (승인 전)</div>}
    </div>
  );
}

export default function CalendarPage() {
  const [view, setView] = useState("week");
  const [anchor, setAnchor] = useState(startOfDay(new Date()));
  const [items, setItems] = useState([]);
  const [dropKey, setDropKey] = useState(null);
  const [open, setOpen] = useState(null);
  const [run] = useAction();

  const start = view === "week" ? addDays(anchor, -((anchor.getDay() + 6) % 7)) : anchor;
  const days = view === "week" ? 7 : 1;
  const end = addDays(start, days);
  const load = () => api.get("/api/calendar" + qs({ start: start.toISOString(), end: end.toISOString() })).then(setItems);
  useEffect(() => {
    load();
  }, [view, anchor]); // eslint-disable-line react-hooks/exhaustive-deps

  const move = async (id, target) => {
    setDropKey(null);
    const r = await run(() => api.patch(`/api/calendar/${id}`, { scheduled_at: target.toISOString() }), "일정을 변경했습니다");
    if (r) load();
  };
  const onDropDay = (e, day) => {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData("text/plain"));
    const it = items.find((x) => x.id === id);
    if (!it) return;
    const old = parseUTC(it.calendar_time);
    const t = new Date(day);
    t.setHours(old.getHours(), old.getMinutes(), 0, 0);
    move(id, t);
  };
  const onDropHour = (e, hour) => {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData("text/plain"));
    const it = items.find((x) => x.id === id);
    if (!it) return;
    const t = new Date(anchor);
    t.setHours(hour, parseUTC(it.calendar_time).getMinutes(), 0, 0);
    move(id, t);
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
        <div><h1>콘텐츠 캘린더</h1><div className="muted small">카드를 끌어서 다른 날짜/시간에 놓으면 게시 일정이 바뀝니다. 게시 완료 콘텐츠는 이동할 수 없습니다.</div></div>
        <div className="row">
          <button onClick={() => setAnchor(addDays(anchor, -step))}>◀</button>
          <button onClick={() => setAnchor(startOfDay(new Date()))}>오늘</button>
          <button onClick={() => setAnchor(addDays(anchor, step))}>▶</button>
          <div className="tabs" style={{ margin: 0, border: "none" }}>
            <button className={view === "day" ? "active" : ""} onClick={() => setView("day")}>일간</button>
            <button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>주간</button>
          </div>
        </div>
      </div>
      <h2>{start.toLocaleDateString()} {view === "week" && `~ ${addDays(start, 6).toLocaleDateString()}`}</h2>
      {view === "week" ? (
        <div className="cal-week">
          {Array.from({ length: 7 }, (_, i) => addDays(start, i)).map((day) => {
            const key = day.toDateString();
            const list = items.filter((it) => sameDay(parseUTC(it.calendar_time), day));
            return (
              <div key={key} className={`cal-day ${sameDay(day, new Date()) ? "today" : ""} ${dropKey === key ? "drop" : ""}`} {...dz(key, (e) => onDropDay(e, day))}>
                <h4><button className="link" onClick={() => { setAnchor(startOfDay(day)); setView("day"); }}>{day.toLocaleDateString(undefined, { weekday: "short", month: "numeric", day: "numeric" })}</button> <span className="muted">({list.length})</span></h4>
                {list.map((it) => <Item key={it.id} it={it} onOpen={setOpen} />)}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card">
          <div className="cal-hours">
            {Array.from({ length: 24 }, (_, h) => {
              const list = items.filter((it) => parseUTC(it.calendar_time).getHours() === h);
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

import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, useAction } from "../components/ui";
import { fmtDateTime } from "../util";

export default function Reports() {
  const [list, setList] = useState([]);
  const [cur, setCur] = useState(null);
  const [run, busy] = useAction();
  const load = () => api.get("/api/reports").then((l) => { setList(l); if (!cur && l[0]) open(l[0].id); });
  const open = (id) => api.get(`/api/reports/${id}`).then(setCur);
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const make = async (type) => {
    const r = await run(() => api.post(`/api/reports/${type}`), "리포트를 생성했습니다");
    if (r) { setCur(r); api.get("/api/reports").then(setList); }
  };
  const download = () => {
    const blob = new Blob([cur.content_md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = cur.file_path.split(/[\\/]/).pop() || "report.md";
    a.click();
  };
  return (
    <>
      <div className="topbar">
        <div><h1>리포트</h1><div className="muted small">Daily 는 매일 21:00, Weekly 는 매주 월요일 08:00 자동 생성 (data/reports 폴더에도 저장)</div></div>
        <div className="row">
          <button disabled={busy} onClick={() => make("daily")}>Daily 지금 생성</button>
          <button disabled={busy} onClick={() => make("weekly")}>Weekly 지금 생성</button>
        </div>
      </div>
      <div className="grid split">
        <div className="card">
          {list.length === 0 ? <Empty>리포트 없음</Empty> : list.map((r) => (
            <div key={r.id}><button className="link" onClick={() => open(r.id)} style={{ fontWeight: cur?.id === r.id ? 700 : 400 }}>{r.report_type.toUpperCase()} · {fmtDateTime(r.created_at)}</button></div>
          ))}
        </div>
        <div className="card">
          {cur ? (<><div className="spread"><span className="muted small">{cur.file_path}</span><button className="sm" onClick={download}>⬇ .md 다운로드</button></div><div className="md">{cur.content_md}</div></>) : <Empty>왼쪽에서 리포트를 선택하세요.</Empty>}
        </div>
      </div>
    </>
  );
}

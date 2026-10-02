import { useEffect, useState } from "react";
import { api, qs } from "../api";
import { fmtDateTime } from "../util";

const CATS = ["", "ai_generation", "post_attempt", "api_response", "api_error", "ad_data", "approval", "budget_change", "dry_run", "system"];

export default function Logs() {
  const [cat, setCat] = useState("");
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api.get("/api/logs" + qs({ category: cat, limit: 300 })).then(setRows);
  }, [cat]);
  return (
    <>
      <div className="topbar">
        <div><h1>로그</h1><div className="muted small">주요 이벤트 기록 (전체 로그는 logs/app.log). API Key/Token 은 자동으로 가려집니다.</div></div>
        <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ width: 200 }}>{CATS.map((c) => <option key={c} value={c}>{c || "전체"}</option>)}</select>
      </div>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>시간</th><th>분류</th><th>레벨</th><th>내용</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}>
              <td className="small" style={{ whiteSpace: "nowrap" }}>{fmtDateTime(r.created_at)}</td>
              <td><span className="badge">{r.category}</span></td>
              <td className="small" style={{ color: r.level === "ERROR" ? "var(--bad)" : r.level === "WARNING" ? "var(--warn)" : undefined }}>{r.level}</td>
              <td>{r.message}{r.details && Object.keys(r.details).length > 0 && <details><summary className="small muted">상세</summary><pre className="mono" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(r.details, null, 1)}</pre></details>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

import { createContext, useCallback, useContext, useState } from "react";
import { PLATFORMS, SCORE_LABEL, STATUS_LABEL, TYPE_LABEL } from "../util";

export const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const show = useCallback((msg, kind = "ok") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), kind === "err" ? 6000 : 3000);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.msg}</div>}
    </ToastContext.Provider>
  );
}

// 버튼 클릭 → 비동기 작업 실행 + 결과 알림
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = useCallback(
    async (fn, okMsg) => {
      setBusy(true);
      try {
        const r = await fn();
        if (okMsg) toast(okMsg);
        return r;
      } catch (e) {
        toast(e.message || String(e), "err");
        return undefined;
      } finally {
        setBusy(false);
      }
    },
    [toast]
  );
  return [run, busy];
}

export const StatusBadge = ({ s }) => <span className={`badge s-${s}`}>{STATUS_LABEL[s] || s}</span>;
export const PlatformBadge = ({ p }) => <span className={`badge p-${p}`}>{PLATFORMS[p] || p}</span>;
export const TypeBadge = ({ t }) => <span className="badge">{TYPE_LABEL[t] || t}</span>;
export const MockBadge = ({ show = true, label = "MOCK" }) => (show ? <span className="badge mock" title="테스트용 가짜 데이터">{label}</span> : null);

export function Modal({ title, onClose, children, footer }) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label={title}>
        <div className="spread" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="sm" onClick={onClose} aria-label="닫기">✕</button>
        </div>
        {children}
        {footer && <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>{footer}</div>}
      </div>
    </div>
  );
}

export function Scores({ scores, total, note }) {
  if (!scores || !Object.keys(scores).length) return null;
  return (
    <div title="AI 내부 우선순위 점수 — 실제 성과를 보장하지 않습니다">
      <div className="small">
        내부 점수 <span className="score">{total ?? "-"}</span>/10 <span className="muted">(성과 보장 아님)</span>
      </div>
      <div className="scorebar">
        {Object.entries(scores).map(([k, v]) => (
          <span key={k}>{SCORE_LABEL[k] || k} {v}</span>
        ))}
      </div>
      {note && <div className="hint">💡 {note}</div>}
    </div>
  );
}

export function Kpi({ label, value, sub }) {
  return (
    <div className="kpi-tile">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

// 쉼표로 구분한 목록 입력 (입력 중에는 글자 그대로 유지)
export function ListInput({ value, onChange, placeholder }) {
  const [text, setText] = useState((value || []).join(", "));
  return (
    <input
      value={text}
      placeholder={placeholder || "쉼표(,)로 구분"}
      onChange={(e) => {
        setText(e.target.value);
        onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean));
      }}
    />
  );
}

export function Empty({ children }) {
  return <div className="muted" style={{ padding: 24, textAlign: "center" }}>{children}</div>;
}

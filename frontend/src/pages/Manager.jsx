import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAction } from "../components/ui";
import { t } from "../i18n";

const EXAMPLES = [
  "오늘 일본 TikTok용 영상 3개 만들어줘.",
  "이번 주 Instagram 성과 어때?",
  "왜 TikTok 조회수가 떨어졌어?",
  "광고비 5만엔이면 어떻게 배분하는 게 좋을까?",
  "지난주 광고 중 어떤 소재가 효율적이었어?",
  "요즘 일본 TikTok 트렌드 알려줘.",
];

function sessionId() {
  try {
    let s = localStorage.getItem("chat_session");
    if (!s) {
      s = Math.random().toString(36).slice(2, 12);
      localStorage.setItem("chat_session", s);
    }
    return s;
  } catch {
    return "default";
  }
}

export default function Manager({ status }) {
  const [sid, setSid] = useState(sessionId);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [run, busy] = useAction();
  const logRef = useRef(null);

  useEffect(() => {
    api.get(`/api/chat/${sid}`).then(setMsgs);
  }, [sid]);
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [msgs, busy]);

  const send = async (q) => {
    const message = (q ?? text).trim();
    if (!message) return;
    setText("");
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "user", content: message }]);
    const r = await run(() => api.post("/api/chat", { session_id: sid, message }));
    if (r) setMsgs((m) => [...m, { id: `a${Date.now()}`, role: "assistant", content: r.answer, tools: r.tools_used }]);
  };
  const reset = () => {
    const s = Math.random().toString(36).slice(2, 12);
    try { localStorage.setItem("chat_session", s); } catch { /* ignore */ }
    setSid(s);
  };

  return (
    <>
      <div className="topbar">
        <div><h1>AI Marketing Manager</h1><div className="muted small">{t("실제 DB 데이터를 조회해서 답합니다. 데이터가 없으면 없다고 답합니다.")} {status.ai_mode !== "claude" && t("(현재 Mock 모드 — Claude API Key 를 넣으면 자유 질문 가능)")}</div></div>
        <button onClick={reset}>{t("새 대화")}</button>
      </div>
      <div className="card chat">
        <div className="chat-log" ref={logRef}>
          {msgs.length === 0 && (
            <div className="stack">
              <p className="muted">{t("예시 질문")}:</p>
              {EXAMPLES.map((e) => <div key={e}><button className="sm" onClick={() => send(t(e))}>{t(e)}</button></div>)}
            </div>
          )}
          {msgs.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              {m.content}
              {m.tools?.length > 0 && <div className="hint">{t("조회한 데이터")}: {m.tools.join(", ")}</div>}
            </div>
          ))}
          {busy && <div className="msg assistant muted">{t("데이터를 조회하고 분석하는 중…")}</div>}
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t("질문을 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)")} style={{ flex: 1, minHeight: 44 }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
          <button className="primary" disabled={busy || !text.trim()} onClick={() => send()}>{t("전송")}</button>
        </div>
      </div>
    </>
  );
}

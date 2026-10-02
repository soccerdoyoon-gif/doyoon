import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { getLang, setLang, t } from "./i18n";
import ABTests from "./pages/ABTests";
import Ads from "./pages/Ads";
import Approvals from "./pages/Approvals";
import Brand from "./pages/Brand";
import CalendarPage from "./pages/Calendar";
import Competitors from "./pages/Competitors";
import Content from "./pages/Content";
import Dashboard from "./pages/Dashboard";
import Logs from "./pages/Logs";
import Manager from "./pages/Manager";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import SetupWizard from "./pages/SetupWizard";
import Trends from "./pages/Trends";
import { setTZ, tzLabel } from "./util";

const NAV = [
  ["/", "📊", "대시보드"],
  ["/approvals", "✅", "승인 대기", "pending"],
  ["/content", "📝", "콘텐츠 제작"],
  ["/calendar", "🗓️", "캘린더"],
  ["/trends", "📈", "트렌드 · 게시 시간"],
  ["/manager", "🤖", "AI 매니저"],
  ["/ads", "💰", "광고"],
  ["/abtests", "🧪", "A/B 테스트"],
  ["/competitors", "🔍", "경쟁사"],
  ["/reports", "📄", "리포트"],
  ["/brand", "🏷️", "브랜드"],
  ["/settings", "⚙️", "설정"],
  ["/logs", "📜", "로그"],
];

export default function App() {
  const [status, setStatus] = useState(null);
  const [pending, setPending] = useState(0);
  const [open, setOpen] = useState(false);
  const [, setLangTick] = useState(getLang());
  const location = useLocation();

  const refresh = useCallback(async () => {
    try {
      const s = await api.get("/api/system/status");
      setTZ(s.timezone);
      setLang(s.ui_language);
      setLangTick(s.ui_language);
      setStatus(s);
      if (s.setup_completed) {
        const d = await api.get("/api/dashboard?days=1");
        setPending((d.cards.pending_review || 0) + (d.cards.pending_ad_actions || 0));
      }
    } catch {
      setStatus((prev) => prev || { error: true });
    }
  }, []);

  useEffect(() => {
    refresh();
    setOpen(false);
  }, [location.pathname, refresh]);

  const switchLang = async (l) => {
    await api.put("/api/settings/ui_language", { value: l });
    await refresh();
  };

  if (!status) return <div className="main">Loading…</div>;
  if (status.error) return <div className="main"><div className="banner bad">{t("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요 (README 의 \"실행 방법\").")}</div></div>;
  if (!status.setup_completed && location.pathname !== "/setup") return <Navigate to="/setup" replace />;
  if (location.pathname === "/setup") return <SetupWizard onDone={refresh} status={status} onLang={switchLang} />;

  return (
    <div className="layout" key={getLang()}>
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand-mark">
          <img src="/favicon.svg" width="24" height="24" alt="" /> SNS AI Marketing
        </div>
        <nav className="nav">
          {NAV.map(([to, icon, label, badge]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              <span>{icon} {t(label)}</span>
              {badge === "pending" && pending > 0 && <span className="count">{pending}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="small muted" style={{ padding: "16px 10px" }}>
          {t("시장")}: 🇯🇵 {t("일본")} · ¥ · {tzLabel()}
          <br />
          AI: {status.ai_mode === "claude" ? "Claude" : t("Mock (API Key 없음)")}
          <br />
          {t("모드")}: {status.dry_run ? "DRY RUN" : "LIVE"}
          <div className="row" style={{ marginTop: 8 }}>
            <button className={`sm ${getLang() === "ja" ? "primary" : ""}`} onClick={() => switchLang("ja")}>日本語</button>
            <button className={`sm ${getLang() === "ko" ? "primary" : ""}`} onClick={() => switchLang("ko")}>한국어</button>
          </div>
        </div>
      </aside>
      <main className="main">
        <button className="menu-btn sm" style={{ marginBottom: 10 }} onClick={() => setOpen(!open)}>☰ {t("메뉴")}</button>
        {status.dry_run ? (
          <div className="banner warn">🧪 <b>{t("DRY RUN 모드")}</b> — {t("실제 SNS 게시, 광고 수정, 비용 지출이 일어나지 않습니다. 모든 동작은 \"~했을 것\" 로그로만 기록됩니다.")}</div>
        ) : (
          <div className="banner bad">🔴 <b>{t("LIVE 모드")}</b> — {t("승인한 콘텐츠가 실제 SNS 에 게시되고, 승인한 광고 작업이 실제로 실행됩니다.")}</div>
        )}
        <Routes>
          <Route path="/" element={<Dashboard status={status} />} />
          <Route path="/approvals" element={<Approvals onChange={refresh} />} />
          <Route path="/content" element={<Content onChange={refresh} />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/trends" element={<Trends />} />
          <Route path="/manager" element={<Manager status={status} />} />
          <Route path="/ads" element={<Ads onChange={refresh} />} />
          <Route path="/abtests" element={<ABTests />} />
          <Route path="/competitors" element={<Competitors />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/brand" element={<Brand />} />
          <Route path="/settings" element={<Settings status={status} onChange={refresh} />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

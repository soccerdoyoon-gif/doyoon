import { api } from "../api";
import { t } from "../i18n";
import { fmtDateTime, yen } from "../util";
import { Empty, StatusBadge, useAction } from "./ui";

const ACTION_LABEL = { budget_change: "예산 변경", pause: "중지", resume: "재개", delete: "삭제", create_campaign: "캠페인 생성", billing_change: "결제 설정 변경" };

// 광고 작업 승인 목록 (Budget Guard 결과 포함)
export default function AdActions({ actions, onChange, dryRun = true }) {
  const [run, busy] = useAction();
  if (!actions.length) return <Empty>{t("승인 대기 중인 광고 작업이 없습니다.")}</Empty>;
  const approve = (a) => {
    const what = a.action_type === "budget_change"
      ? `${t("예산")} ${yen(a.payload.current_budget)} → ${yen(a.payload.new_budget)}`
      : t(ACTION_LABEL[a.action_type]);
    const msg = dryRun ? t("{w} 작업을 승인합니다 (DRY RUN: 실제 변경 없음).", { w: what }) : t("⚠️ LIVE 모드: {w} 이(가) 실제 광고 계정에 적용되어 비용에 영향을 줍니다. 승인할까요?", { w: what });
    if (window.confirm(msg)) run(() => api.post(`/api/ads/actions/${a.id}/approve`), t("처리했습니다")).then(onChange);
  };
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>#</th><th>{t("작업")}</th><th>{t("대상")}</th><th>{t("내용")}</th><th>Budget Guard</th><th>{t("요청")}</th><th>{t("상태")}</th><th></th></tr></thead>
        <tbody>
          {actions.map((a) => (
            <tr key={a.id}>
              <td>{a.id}</td>
              <td>{t(ACTION_LABEL[a.action_type] || a.action_type)}</td>
              <td>{a.target_name || a.target_external_id}<div className="hint">{a.target_level}</div></td>
              <td>
                {a.action_type === "budget_change" && <>{yen(a.payload.current_budget)} → <b>{yen(a.payload.new_budget)}</b>{a.guard_result?.change_percent != null && <div className="hint">{a.guard_result.change_percent > 0 ? "+" : ""}{a.guard_result.change_percent}%</div>}</>}
                {a.reason && <div className="hint">{a.reason}</div>}
                {a.result && <div className="hint">{a.result}</div>}
              </td>
              <td className="small">{(a.guard_result?.reasons || []).map((r, i) => <div key={i}>• {r}</div>)}</td>
              <td className="small">{a.requested_by === "ai" ? "🤖 AI" : "👤"}<div className="hint">{fmtDateTime(a.created_at)}</div></td>
              <td><StatusBadge s={a.status} /></td>
              <td>
                {a.status === "PENDING" && (
                  <div className="row">
                    <button className="sm primary" disabled={busy} onClick={() => approve(a)}>{t("승인")}</button>
                    <button className="sm danger" disabled={busy} onClick={() => run(() => api.post(`/api/ads/actions/${a.id}/reject`, { note: "" }), t("거절했습니다")).then(onChange)}>{t("거절")}</button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

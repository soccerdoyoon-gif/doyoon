export const PLATFORMS = { instagram: "Instagram", facebook: "Facebook", tiktok: "TikTok", x: "X" };
export const STATUS_LABEL = {
  DRAFT: "초안",
  READY_FOR_REVIEW: "승인 대기",
  APPROVED: "승인됨",
  SCHEDULED: "예약됨",
  PUBLISHED: "게시 완료",
  FAILED: "실패",
  REJECTED: "반려",
  PENDING: "승인 대기",
  EXECUTED: "실행됨",
  BLOCKED: "차단됨",
};
export const TYPE_LABEL = {
  post: "게시물", carousel: "캐러셀", reel: "Reel", story: "스토리", short_video: "숏폼",
  tweet: "일반", ad_tweet: "광고성", info_tweet: "정보성", thread: "Thread",
};
export const SCORE_LABEL = {
  hook_strength: "Hook", target_audience_fit: "타깃 적합", brand_consistency: "브랜드",
  cta_quality: "CTA", originality: "독창성", expected_engagement: "참여 기대",
};

export function parseUTC(s) {
  if (!s) return null;
  return new Date(s.endsWith("Z") ? s : s + "Z");
}
export function fmtDateTime(s) {
  const d = parseUTC(s);
  if (!d) return "-";
  return d.toLocaleString(undefined, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
export function fmtTime(s) {
  const d = parseUTC(s);
  return d ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "-";
}
export function toLocalInput(s) {
  const d = parseUTC(s) || new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export function localInputToISO(v) {
  return v ? new Date(v).toISOString() : null;
}
export function num(v, digits = 0) {
  if (v === null || v === undefined) return "N/A";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}
export function pct(v, digits = 2) {
  return v === null || v === undefined ? "N/A" : `${Number(v).toFixed(digits)}%`;
}
export function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
export function addDays(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

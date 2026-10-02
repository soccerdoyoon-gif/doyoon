import { t } from "./i18n";

// 모든 시간은 서버 설정 시간대(기본 Asia/Tokyo = JST)로 표시합니다.
let TZ = "Asia/Tokyo";
export const setTZ = (tz) => { TZ = tz || "Asia/Tokyo"; };
export const getTZ = () => TZ;
export const tzLabel = () => (TZ === "Asia/Tokyo" ? "JST" : TZ);

export const PLATFORMS = { instagram: "Instagram", facebook: "Facebook", tiktok: "TikTok", x: "X" };
export const STATUS_KEYS = {
  DRAFT: "초안", READY_FOR_REVIEW: "승인 대기", APPROVED: "승인됨", SCHEDULED: "예약됨", PUBLISHED: "게시 완료",
  FAILED: "실패", REJECTED: "반려", PENDING: "승인 대기", EXECUTED: "실행됨", BLOCKED: "차단됨", RUNNING: "진행 중", DONE: "완료", ERROR: "오류",
};
export const statusLabel = (s) => t(STATUS_KEYS[s] || s);
export const TYPE_KEYS = {
  post: "게시물", carousel: "캐러셀", reel: "Reel", story: "스토리", short_video: "숏폼",
  tweet: "일반", ad_tweet: "광고성", info_tweet: "정보성", thread: "Thread",
};
export const typeLabel = (k) => t(TYPE_KEYS[k] || k);
export const SCORE_KEYS = {
  hook_strength: "Hook", target_audience_fit: "타깃 적합", brand_consistency: "브랜드",
  cta_quality: "CTA", originality: "독창성", expected_engagement: "참여 기대",
};

export function parseUTC(s) {
  if (!s) return null;
  return new Date(s.endsWith("Z") ? s : s + "Z");
}

function parts(d) {
  const o = {};
  new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "short", hourCycle: "h23" })
    .formatToParts(d).forEach((p) => { o[p.type] = p.value; });
  return o;
}

export function fmtDateTime(s) {
  const d = typeof s === "string" ? parseUTC(s) : s;
  if (!d) return "-";
  const p = parts(d);
  return `${p.month}/${p.day} ${p.hour}:${p.minute}`;
}
export function fmtTime(s) {
  const d = typeof s === "string" ? parseUTC(s) : s;
  if (!d) return "-";
  const p = parts(d);
  return `${p.hour}:${p.minute}`;
}
export const hourOf = (s) => Number(parts(parseUTC(s)).hour);

// 날짜 키 "YYYY-MM-DD" (설정 시간대 기준)
export function dayKey(d) {
  const p = parts(typeof d === "string" ? parseUTC(d) : d);
  return `${p.year}-${p.month}-${p.day}`;
}
export const todayKey = () => dayKey(new Date());
export function addDaysKey(key, n) {
  const [y, m, d] = key.split("-").map(Number);
  const x = new Date(Date.UTC(y, m - 1, d + n));
  return x.toISOString().slice(0, 10);
}
export function weekdayOfKey(key) {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0=일
}
export function fmtDayKey(key) {
  const wd = ["日", "月", "火", "水", "木", "金", "土"][weekdayOfKey(key)];
  return `${Number(key.slice(5, 7))}/${Number(key.slice(8, 10))} (${wd})`;
}

// datetime-local 입력값 <-> UTC ISO (설정 시간대 기준)
export function toLocalInput(s) {
  const p = parts(parseUTC(s) || new Date());
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
function tzOffsetMs(date) {
  const p = parts(date);
  const asUTC = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
  return asUTC - Math.floor(date.getTime() / 60000) * 60000;
}
export function localInputToISO(v) {
  if (!v) return null;
  const [date, time] = v.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = (time || "00:00").split(":").map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  let ts = guess - tzOffsetMs(new Date(guess));
  ts = guess - tzOffsetMs(new Date(ts));
  return new Date(ts).toISOString();
}
export const keyToISO = (key, hh = 0, mm = 0) => localInputToISO(`${key}T${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`);

export function num(v, digits = 0) {
  if (v === null || v === undefined) return "N/A";
  return Number(v).toLocaleString("ja-JP", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}
export function yen(v) {
  return v === null || v === undefined ? "N/A" : `¥${Math.round(Number(v)).toLocaleString("ja-JP")}`;
}
export function pct(v, digits = 2) {
  return v === null || v === undefined ? "N/A" : `${Number(v).toFixed(digits)}%`;
}

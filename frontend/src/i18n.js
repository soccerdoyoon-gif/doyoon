// 화면 언어: ja(기본) / ko. 키는 한국어 원문, 일본어는 i18n_ja.js 사전에서 찾음.
import JA from "./i18n_ja";

let LANG = "ja";
const missing = new Set();

export function setLang(l) {
  LANG = l === "ko" ? "ko" : "ja";
  try { document.documentElement.lang = LANG; } catch { /* ignore */ }
}
export const getLang = () => LANG;

export function t(ko, vars) {
  let s = ko;
  if (LANG === "ja") {
    if (JA[ko] !== undefined) s = JA[ko];
    else missing.add(ko);
  }
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

// 번역 누락 확인용 (개발 도구 콘솔에서 window.__i18nMissing)
if (typeof window !== "undefined") window.__i18nMissing = missing;

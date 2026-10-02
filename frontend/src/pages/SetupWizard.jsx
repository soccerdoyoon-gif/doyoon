import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ListInput, useAction } from "../components/ui";
import { getLang, t } from "../i18n";

const STEPS = ["브랜드", "타깃·언어", "SNS 선택", "Claude API", "SNS API", "광고", "완료"];

export default function SetupWizard({ onDone, onLang }) {
  const nav = useNavigate();
  const [run, busy] = useAction();
  const [step, setStep] = useState(0);
  const [styles, setStyles] = useState([]);
  const [brand, setBrand] = useState({
    brand_name: "", brand_description: "", product_description: "", main_products: "", target_customer: "日本在住の消費者",
    country: "JP", language: "ja", default_style: "親しみやすい", brand_voice: "", brand_values: "", forbidden_words: [], preferred_words: [],
    competitors: [], main_goal: "sales", website_url: "",
  });
  const [platforms, setPlatforms] = useState({ instagram: true, tiktok: true, x: true, facebook: false });
  const [secrets, setSecrets] = useState({});
  const [ads, setAds] = useState({ ads_enabled: false, daily_budget_limit: 10000, currency: "JPY" });
  const [firstGen, setFirstGen] = useState(true);
  useEffect(() => {
    api.get("/api/pipeline/styles").then(setStyles).catch(() => null);
  }, []);

  const b = (k) => ({ value: brand[k], onChange: (e) => setBrand({ ...brand, [k]: e.target.value }) });
  const sec = (k) => ({ value: secrets[k] || "", onChange: (e) => setSecrets({ ...secrets, [k]: e.target.value }), autoComplete: "off" });
  const canNext = step !== 0 || brand.brand_name.trim().length > 0;

  const finish = () =>
    run(async () => {
      const clean = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v && v.trim()));
      await api.post("/api/setup", { brand, platforms_enabled: platforms, secrets: clean, ...ads, daily_budget_limit: Number(ads.daily_budget_limit) });
      await api.post("/api/strategy").catch(() => null);
      if (firstGen) await api.post("/api/pipeline/run", {});
      await onDone();
      nav(firstGen ? "/content" : "/");
    }, t("설정이 완료되었습니다!"));

  return (
    <div className="main" style={{ maxWidth: 760, margin: "0 auto" }}>
      <div className="spread">
        <h1>👋 {t("설치 마법사")}</h1>
        <div className="row">
          <button className={`sm ${getLang() === "ja" ? "primary" : ""}`} onClick={() => onLang("ja")}>日本語</button>
          <button className={`sm ${getLang() === "ko" ? "primary" : ""}`} onClick={() => onLang("ko")}>한국어</button>
        </div>
      </div>
      <p className="muted">{t("기본 시장은 일본입니다 (일본어 · 엔화 · JST). API Key 가 없어도 Mock(테스트) 모드로 모든 기능을 사용해 볼 수 있어요. 나중에 설정 메뉴에서 언제든 바꿀 수 있습니다.")}</p>
      <div className="steps">{STEPS.map((s, i) => <span key={s} className={i === step ? "on" : ""}>{i + 1}. {t(s)}</span>)}</div>
      <div className="card">
        {step === 0 && (
          <>
            <h2>1. {t("브랜드 / 사업 설명")}</h2>
            <div className="field"><label>{t("브랜드 이름")} *</label><input {...b("brand_name")} placeholder="例: Sakura Tea" /></div>
            <div className="field"><label>{t("사업 설명")}</label><textarea {...b("brand_description")} placeholder={t("어떤 회사/브랜드인지 2~3문장으로 (일본어 권장)")} /></div>
            <div className="field"><label>{t("제품 또는 서비스 설명")}</label><textarea {...b("product_description")} /></div>
            <div className="field"><label>{t("주요 판매 제품")}</label><input {...b("main_products")} placeholder="例: 抹茶パウダー、ほうじ茶ティーバッグ" /></div>
            <div className="field"><label>{t("웹사이트 (선택)")}</label><input {...b("website_url")} placeholder="https://" /></div>
            <p className="hint">{t("제품명 등은 일본어로 입력하면 콘텐츠가 더 자연스러워집니다.")}</p>
          </>
        )}
        {step === 1 && (
          <>
            <h2>2. {t("타깃 / 국가 / 언어")}</h2>
            <div className="field"><label>{t("목표 고객")}</label><textarea {...b("target_customer")} /></div>
            <div className="grid cols-3">
              <div className="field"><label>{t("국가")}</label><select {...b("country")}><option value="JP">🇯🇵 {t("일본")}</option><option value="KR">{t("한국")}</option><option value="US">US</option><option value="OTHER">{t("기타")}</option></select></div>
              <div className="field"><label>{t("콘텐츠 언어")}</label><select {...b("language")}><option value="ja">日本語 ({t("기본")})</option><option value="ko">한국어</option><option value="en">English</option></select></div>
              <div className="field"><label>{t("주요 목표")}</label><select {...b("main_goal")}><option value="sales">{t("판매")}</option><option value="followers">{t("팔로워")}</option><option value="website_traffic">{t("웹사이트 방문")}</option><option value="brand_awareness">{t("브랜드 인지도")}</option></select></div>
            </div>
            <div className="grid cols-2">
              <div className="field"><label>{t("기본 카피 스타일")}</label><select {...b("default_style")}>{styles.map((s) => <option key={s}>{s}</option>)}</select></div>
              <div className="field"><label>{t("브랜드 톤")}</label><input {...b("brand_voice")} placeholder="例: やさしく落ち着いた" /></div>
            </div>
            <div className="field"><label>{t("브랜드 가치")}</label><input {...b("brand_values")} placeholder="例: オーガニック、サステナブル" /></div>
            <div className="field"><label>{t("경쟁사")}</label><ListInput value={brand.competitors} onChange={(v) => setBrand({ ...brand, competitors: v })} placeholder={t("예: A사, B사")} /></div>
            <div className="field"><label>{t("금지어 (AI 가 절대 쓰지 않을 단어)")}</label><ListInput value={brand.forbidden_words} onChange={(v) => setBrand({ ...brand, forbidden_words: v })} placeholder="例: 最強, 奇跡" /></div>
            <div className="field"><label>{t("선호 단어")}</label><ListInput value={brand.preferred_words} onChange={(v) => setBrand({ ...brand, preferred_words: v })} /></div>
          </>
        )}
        {step === 2 && (
          <>
            <h2>3. {t("연결할 SNS")}</h2>
            {Object.entries({ instagram: "Instagram", tiktok: "TikTok", x: "X", facebook: "Facebook" }).map(([k, label]) => (
              <label key={k} className="row" style={{ fontWeight: 400, fontSize: 14, marginBottom: 10 }}>
                <input type="checkbox" checked={platforms[k]} onChange={(e) => setPlatforms({ ...platforms, [k]: e.target.checked })} /> {label}
              </label>
            ))}
            <p className="hint">{t("기본 업로드 대상은 Instagram / TikTok / X 입니다. API 를 아직 연결하지 않아도 Mock 모드로 동작합니다.")}</p>
          </>
        )}
        {step === 3 && (
          <>
            <h2>4. {t("Claude API Key (선택)")}</h2>
            <p className="muted small">{t("https://console.anthropic.com 에서 발급. 비워 두면 템플릿 기반 Mock AI 로 동작합니다. 키는 서버의 data/secrets.env 에만 저장되고 화면에는 다시 표시되지 않습니다.")}</p>
            <div className="field"><label>ANTHROPIC_API_KEY</label><input type="password" {...sec("ANTHROPIC_API_KEY")} placeholder="sk-ant-..." /></div>
          </>
        )}
        {step === 4 && (
          <>
            <h2>5. {t("SNS API 설정 (선택 — 나중에 해도 됩니다)")}</h2>
            <p className="muted small">{t("각 개발자 포털에서 앱을 만든 뒤 아래 값을 넣고, 완료 후 [설정] 화면의 \"연결\" 버튼으로 OAuth 로그인하세요. 비밀번호는 저장하지 않습니다. 자세한 방법은 README 참고.")}</p>
            <div className="grid cols-2">
              {["INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "X_CLIENT_ID", "X_CLIENT_SECRET"].map((k) => (
                <div className="field" key={k}><label>{k}</label><input type={/SECRET/.test(k) ? "password" : "text"} {...sec(k)} /></div>
              ))}
            </div>
          </>
        )}
        {step === 5 && (
          <>
            <h2>6. {t("광고 계정 / 하루 광고 예산 제한")}</h2>
            <label className="row" style={{ fontWeight: 400, fontSize: 14, marginBottom: 12 }}>
              <input type="checkbox" checked={ads.ads_enabled} onChange={(e) => setAds({ ...ads, ads_enabled: e.target.checked })} /> {t("Meta 광고 성과 분석 사용")}
            </label>
            {ads.ads_enabled && (
              <div className="grid cols-2">
                <div className="field"><label>{t("META_AD_ACCOUNT_ID (숫자)")}</label><input {...sec("META_AD_ACCOUNT_ID")} placeholder={t("act_ 없이 숫자만")} /></div>
                <div className="field"><label>META_ADS_ACCESS_TOKEN</label><input type="password" {...sec("META_ADS_ACCESS_TOKEN")} /></div>
              </div>
            )}
            <div className="grid cols-2">
              <div className="field"><label>{t("하루 광고비 한도")} (¥)</label><input type="number" min="0" value={ads.daily_budget_limit} onChange={(e) => setAds({ ...ads, daily_budget_limit: e.target.value })} /><div className="hint">{t("이 금액을 넘는 예산 변경은 승인해도 무조건 차단됩니다.")}</div></div>
              <div className="field"><label>{t("통화")}</label><select value={ads.currency} onChange={(e) => setAds({ ...ads, currency: e.target.value })}><option>JPY</option><option>KRW</option><option>USD</option></select></div>
            </div>
            <p className="hint">{t("광고 예산 변경은 1회 ±10% 까지만 허용되며, 모든 광고 작업은 기본적으로 사용자 승인이 필요합니다.")}</p>
          </>
        )}
        {step === 6 && (
          <>
            <h2>7. {t("확인")}</h2>
            <ul>
              <li>{t("브랜드")}: <b>{brand.brand_name}</b> ({brand.country}, {brand.language}, {brand.default_style})</li>
              <li>SNS: {Object.entries(platforms).filter(([, v]) => v).map(([k]) => k).join(", ") || "-"}</li>
              <li>Claude: {secrets.ANTHROPIC_API_KEY ? t("API Key 입력됨") : t("Mock AI 사용")}</li>
              <li>{t("광고")}: {ads.ads_enabled ? t("사용") : t("사용 안 함")} · {t("하루 한도")} ¥{Number(ads.daily_budget_limit).toLocaleString("ja-JP")}</li>
              <li>{t("안전 모드: DRY RUN (실제 게시/광고 수정 없음)")}</li>
            </ul>
            <label className="row" style={{ fontWeight: 400, fontSize: 14 }}>
              <input type="checkbox" checked={firstGen} onChange={(e) => setFirstGen(e.target.checked)} /> {t("완료 후 AI 콘텐츠 전략과 첫 콘텐츠 패키지를 바로 제작")}
            </label>
          </>
        )}
        <div className="spread" style={{ marginTop: 16 }}>
          <button disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>← {t("이전")}</button>
          {step < STEPS.length - 1 ? (
            <button className="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>{t("다음")} →</button>
          ) : (
            <button className="primary" disabled={busy} onClick={finish}>{busy ? t("설정 중…") : t("완료")}</button>
          )}
        </div>
      </div>
    </div>
  );
}

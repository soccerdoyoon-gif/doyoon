import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ListInput, useAction } from "../components/ui";

const STEPS = ["브랜드", "타깃·언어", "SNS 선택", "Claude API", "SNS API", "광고", "완료"];

export default function SetupWizard({ onDone, status }) {
  const nav = useNavigate();
  const [run, busy] = useAction();
  const [step, setStep] = useState(0);
  const [brand, setBrand] = useState({
    brand_name: "", brand_description: "", product_description: "", main_products: "", target_customer: "",
    country: "JP", language: "ko", brand_voice: "", brand_values: "", forbidden_words: [], preferred_words: [],
    competitors: [], main_goal: "sales", website_url: "",
  });
  const [platforms, setPlatforms] = useState({ instagram: true, tiktok: true, x: true, facebook: false });
  const [secrets, setSecrets] = useState({});
  const [ads, setAds] = useState({ ads_enabled: false, daily_budget_limit: 10000, currency: "JPY" });
  const [firstGen, setFirstGen] = useState(true);

  const b = (k) => ({ value: brand[k], onChange: (e) => setBrand({ ...brand, [k]: e.target.value }) });
  const sec = (k) => ({ value: secrets[k] || "", onChange: (e) => setSecrets({ ...secrets, [k]: e.target.value }), autoComplete: "off" });
  const canNext = step !== 0 || brand.brand_name.trim().length > 0;

  const finish = () =>
    run(async () => {
      const clean = Object.fromEntries(Object.entries(secrets).filter(([, v]) => v && v.trim()));
      await api.post("/api/setup", { brand, platforms_enabled: platforms, secrets: clean, ...ads, daily_budget_limit: Number(ads.daily_budget_limit) });
      await api.post("/api/strategy").catch(() => null);
      if (firstGen) await api.post("/api/content/generate", {});
      await onDone();
      nav(firstGen ? "/approvals" : "/");
    }, "설정이 완료되었습니다!");

  return (
    <div className="main" style={{ maxWidth: 760, margin: "0 auto" }}>
      <h1>👋 설치 마법사</h1>
      <p className="muted">처음 한 번만 설정하면 됩니다. API Key 가 없어도 Mock(테스트) 모드로 모든 기능을 사용해 볼 수 있어요. 나중에 설정 메뉴에서 언제든 바꿀 수 있습니다.</p>
      <div className="steps">{STEPS.map((s, i) => <span key={s} className={i === step ? "on" : ""}>{i + 1}. {s}</span>)}</div>
      <div className="card">
        {step === 0 && (
          <>
            <h2>1. 브랜드 / 사업 설명</h2>
            <div className="field"><label>브랜드 이름 *</label><input {...b("brand_name")} placeholder="예: Sakura Tea" /></div>
            <div className="field"><label>사업 설명</label><textarea {...b("brand_description")} placeholder="어떤 회사/브랜드인지 2~3문장으로" /></div>
            <div className="field"><label>제품 또는 서비스 설명</label><textarea {...b("product_description")} /></div>
            <div className="field"><label>주요 판매 제품</label><input {...b("main_products")} placeholder="예: 말차 파우더, 호지차 티백" /></div>
            <div className="field"><label>웹사이트 (선택)</label><input {...b("website_url")} placeholder="https://" /></div>
          </>
        )}
        {step === 1 && (
          <>
            <h2>2. 타깃 / 국가 / 언어</h2>
            <div className="field"><label>목표 고객</label><textarea {...b("target_customer")} placeholder="예: 25-39세 건강에 관심 많은 직장인 여성" /></div>
            <div className="grid cols-3">
              <div className="field"><label>국가</label><select {...b("country")}><option value="JP">일본</option><option value="KR">한국</option><option value="US">미국</option><option value="GB">영국</option><option value="OTHER">기타</option></select></div>
              <div className="field"><label>콘텐츠 언어</label><select {...b("language")}><option value="ko">한국어</option><option value="ja">日本語</option><option value="en">English</option></select></div>
              <div className="field"><label>주요 목표</label><select {...b("main_goal")}><option value="sales">판매</option><option value="followers">팔로워</option><option value="website_traffic">웹사이트 방문</option><option value="brand_awareness">브랜드 인지도</option></select></div>
            </div>
            <div className="field"><label>브랜드 톤</label><input {...b("brand_voice")} placeholder="예: 따뜻하고 차분한, 전문적이지만 친근한" /></div>
            <div className="field"><label>브랜드 가치</label><input {...b("brand_values")} placeholder="예: 유기농, 지속가능성" /></div>
            <div className="field"><label>경쟁사</label><ListInput value={brand.competitors} onChange={(v) => setBrand({ ...brand, competitors: v })} placeholder="예: A사, B사" /></div>
            <div className="field"><label>금지어 (AI 가 절대 쓰지 않을 단어)</label><ListInput value={brand.forbidden_words} onChange={(v) => setBrand({ ...brand, forbidden_words: v })} placeholder="예: 최고, 100% 효과" /></div>
            <div className="field"><label>선호 단어</label><ListInput value={brand.preferred_words} onChange={(v) => setBrand({ ...brand, preferred_words: v })} /></div>
          </>
        )}
        {step === 2 && (
          <>
            <h2>3. 연결할 SNS</h2>
            {Object.entries({ instagram: "Instagram", tiktok: "TikTok", x: "X", facebook: "Facebook 페이지" }).map(([k, label]) => (
              <label key={k} className="row" style={{ fontWeight: 400, fontSize: 14, marginBottom: 10 }}>
                <input type="checkbox" checked={platforms[k]} onChange={(e) => setPlatforms({ ...platforms, [k]: e.target.checked })} /> {label}
              </label>
            ))}
            <p className="hint">선택한 SNS 용 콘텐츠가 매일 생성됩니다. API 를 아직 연결하지 않아도 Mock 모드로 동작합니다.</p>
          </>
        )}
        {step === 3 && (
          <>
            <h2>4. Claude API Key (선택)</h2>
            <p className="muted small">https://console.anthropic.com 에서 발급. 비워 두면 템플릿 기반 Mock AI 로 동작합니다. 키는 서버의 data/secrets.env 에만 저장되고 화면에는 다시 표시되지 않습니다.</p>
            <div className="field"><label>ANTHROPIC_API_KEY</label><input type="password" {...sec("ANTHROPIC_API_KEY")} placeholder="sk-ant-..." /></div>
          </>
        )}
        {step === 4 && (
          <>
            <h2>5. SNS API 설정 (선택 — 나중에 해도 됩니다)</h2>
            <p className="muted small">각 개발자 포털에서 앱을 만든 뒤 아래 값을 넣고, 완료 후 [설정] 화면의 "연결" 버튼으로 OAuth 로그인하세요. 비밀번호는 저장하지 않습니다. 자세한 방법은 README 참고.</p>
            <div className="grid cols-2">
              <div className="field"><label>INSTAGRAM_APP_ID</label><input {...sec("INSTAGRAM_APP_ID")} /></div>
              <div className="field"><label>INSTAGRAM_APP_SECRET</label><input type="password" {...sec("INSTAGRAM_APP_SECRET")} /></div>
              <div className="field"><label>TIKTOK_CLIENT_KEY</label><input {...sec("TIKTOK_CLIENT_KEY")} /></div>
              <div className="field"><label>TIKTOK_CLIENT_SECRET</label><input type="password" {...sec("TIKTOK_CLIENT_SECRET")} /></div>
              <div className="field"><label>X_CLIENT_ID</label><input {...sec("X_CLIENT_ID")} /></div>
              <div className="field"><label>X_CLIENT_SECRET</label><input type="password" {...sec("X_CLIENT_SECRET")} /></div>
              <div className="field"><label>FACEBOOK_PAGE_ID</label><input {...sec("FACEBOOK_PAGE_ID")} /></div>
              <div className="field"><label>FACEBOOK_PAGE_ACCESS_TOKEN</label><input type="password" {...sec("FACEBOOK_PAGE_ACCESS_TOKEN")} /></div>
            </div>
          </>
        )}
        {step === 5 && (
          <>
            <h2>6. 광고 계정 / 하루 광고 예산 제한</h2>
            <label className="row" style={{ fontWeight: 400, fontSize: 14, marginBottom: 12 }}>
              <input type="checkbox" checked={ads.ads_enabled} onChange={(e) => setAds({ ...ads, ads_enabled: e.target.checked })} /> Meta 광고 성과 분석 사용
            </label>
            {ads.ads_enabled && (
              <div className="grid cols-2">
                <div className="field"><label>META_AD_ACCOUNT_ID (숫자)</label><input {...sec("META_AD_ACCOUNT_ID")} placeholder="act_ 없이 숫자만" /></div>
                <div className="field"><label>META_ADS_ACCESS_TOKEN</label><input type="password" {...sec("META_ADS_ACCESS_TOKEN")} /></div>
              </div>
            )}
            <div className="grid cols-2">
              <div className="field"><label>하루 광고비 한도</label><input type="number" min="0" value={ads.daily_budget_limit} onChange={(e) => setAds({ ...ads, daily_budget_limit: e.target.value })} /><div className="hint">이 금액을 넘는 예산 변경은 승인해도 무조건 차단됩니다.</div></div>
              <div className="field"><label>통화</label><select value={ads.currency} onChange={(e) => setAds({ ...ads, currency: e.target.value })}><option>JPY</option><option>KRW</option><option>USD</option></select></div>
            </div>
            <p className="hint">광고 예산 변경은 1회 ±10% 까지만 허용되며, 모든 광고 작업은 기본적으로 사용자 승인이 필요합니다.</p>
          </>
        )}
        {step === 6 && (
          <>
            <h2>7. 확인</h2>
            <ul>
              <li>브랜드: <b>{brand.brand_name}</b> ({brand.country}, {brand.language})</li>
              <li>SNS: {Object.entries(platforms).filter(([, v]) => v).map(([k]) => k).join(", ") || "없음"}</li>
              <li>Claude: {secrets.ANTHROPIC_API_KEY ? "API Key 입력됨" : "Mock AI 사용"}</li>
              <li>광고: {ads.ads_enabled ? "사용" : "사용 안 함"} · 하루 한도 {Number(ads.daily_budget_limit).toLocaleString()} {ads.currency}</li>
              <li>안전 모드: DRY RUN (실제 게시/광고 수정 없음)</li>
            </ul>
            <label className="row" style={{ fontWeight: 400, fontSize: 14 }}>
              <input type="checkbox" checked={firstGen} onChange={(e) => setFirstGen(e.target.checked)} /> 완료 후 AI 콘텐츠 전략과 첫 콘텐츠 후보를 바로 생성
            </label>
          </>
        )}
        <div className="spread" style={{ marginTop: 16 }}>
          <button disabled={step === 0 || busy} onClick={() => setStep(step - 1)}>← 이전</button>
          {step < STEPS.length - 1 ? (
            <button className="primary" disabled={!canNext} onClick={() => setStep(step + 1)}>다음 →</button>
          ) : (
            <button className="primary" disabled={busy} onClick={finish}>{busy ? "설정 중… (AI 생성은 1~2분 걸릴 수 있어요)" : "완료"}</button>
          )}
        </div>
      </div>
    </div>
  );
}

# SNS AI Marketing — 일본 시장용 SNS 광고·마케팅 자동화 시스템

**기본 시장은 일본입니다.** (기본 언어 日本語 · 국가 Japan · 통화 JPY(¥) · 시간 Asia/Tokyo(JST) · 타깃 日本在住の消費者)

Instagram · TikTok · X 콘텐츠를 **일본 트렌드 분석 → AI 기획 → 일본어 카피·숏폼 스크립트 → 이미지·영상·자막 자동 생성 →
Brand Guardian 검사 → 내가 승인 → JST 예약 게시 → 성과 수집 → AI 분석 → 다음 콘텐츠 개선**까지 자동으로 돌리고,
Meta 광고 성과를 분석해 **개선안과 새 광고안**을 만들어 주는 시스템입니다.

콘텐츠(캡션·광고 카피·영상 대사·자막·썸네일 문구·CTA·해시태그)는 **기본적으로 자연스러운 일본어**로 만듭니다.
한국어·영어는 콘텐츠 제작 화면에서 언어를 고르거나 AI 매니저에게 명시적으로 요청할 때만 사용합니다.
대시보드는 **日本語 / 한국어** 중 선택할 수 있습니다 (왼쪽 아래 버튼).

> **안전 원칙**
> - 처음에는 항상 `DRY_RUN=true` (기본값) — 실제 게시·광고 수정·비용 지출이 **절대** 일어나지 않고 "~했을 것" 로그만 남깁니다.
> - AI가 만든 콘텐츠는 바로 게시되지 않습니다. **내가 승인**해야 예약/게시됩니다.
> - 광고 예산 변경·중지·삭제·캠페인 생성·결제 변경은 **자동 실행되지 않습니다.** Budget Guard + 내 승인이 필요합니다.
> - API Key 가 없어도 **Mock(가짜) 모드**로 전체 기능을 먼저 써 볼 수 있습니다.

---

## 목차
0. [일본 시장 자동화 흐름 (에이전트 파이프라인)](#0-일본-시장-자동화-흐름)
1. [현재 상태 — 완료 / Mock / 내가 해야 할 일](#1-현재-상태)
2. [설치 방법](#2-설치-방법)
3. [실행 방법 / 종료 방법](#3-실행-방법--종료-방법)
4. [처음 사용하기 (설치 마법사)](#4-처음-사용하기)
5. [매일 자동으로 일어나는 일](#5-매일-자동으로-일어나는-일)
6. [API Key 넣는 위치](#6-api-key-넣는-위치)
7. [SNS 연결 방법](#7-sns-연결-방법)
8. [광고 계정 연결 방법](#8-광고-계정-연결-방법)
9. [Dry Run 해제 방법 (실제 게시 시작)](#9-dry-run-해제-방법)
10. [안전장치 정리](#10-안전장치-정리)
11. [오류 해결 방법](#11-오류-해결-방법)
12. [고급: PostgreSQL / 테스트 / 폴더 구조](#12-고급)

---

## 0. 일본 시장 자동화 흐름

```
Trend Research Agent  (일본 TikTok → Reels → X → Shorts 우선, Claude 웹 검색 · 하루 1회 캐시)
 ↓ Content Strategist (트렌드 + 우리 계정 성과 분석 → 아이디어)
 ↓ Copywriter + Hashtag (스타일별 일본어 카피, 플랫폼별 별도 문구, 같은 해시태그 반복 방지)
 ↓ Short-form Script Agent (0-1초 Hook → 1-3초 궁금증 → 3-10초 가치 → 10-20초 제품 → CTA, 장면별 JSON)
 ↓ Creative Director (이미지 브리프: 피드/스토리/캐러셀/썸네일/광고 배너)
 ↓ Brand Guardian (일본어 문법·번역체·한국식 표현·과장·景品表示法/薬機法 위험 표현·금지어 검사 → 자동 수정 또는 보류)
 ↓ Image / Video Generation (assets/generated/ 에 저장)
 ↓ READY_FOR_REVIEW → 내가 승인 → JST 제안 시간에 예약
 ↓ Publishing (Instagram / TikTok / X: 캡션·해시태그·미디어 자동 매칭)
 ↓ Analytics (성과 수집 → AI 분석 → JST 게시 시간 학습 → 다음 콘텐츠에 반영)
```

**아이디어 1개 → 콘텐츠 패키지**
| 플랫폼 | 만들어지는 것 |
|---|---|
| Instagram | 캡션(일본어) · 해시태그 · 이미지(피드 4:5 + 스토리 9:16) 또는 캐러셀 이미지 또는 Reel 스크립트+영상 |
| TikTok | 첫 1~3초 Hook · 스크립트(장면) · 캡션 · 해시태그 · 9:16 영상(일본어 자막, 음성 선택) · 썸네일 · YouTube Shorts 제목 |
| X | 짧고 대화형인 게시물 또는 Thread (일본어는 1자=2카운트로 280 제한 검사) |
| Ads | headline · primary text · CTA · 배너 이미지(1:1) · 스토리 이미지 · 영상(TikTok 영상 연결) |

**이렇게 명령할 수 있습니다** (AI 매니저 화면):
- 「오늘 일본 TikTok용 영상 3개 만들어줘」 / 「今日の日本向けTikTok動画を3本作って」
  → 트렌드 분석 → 아이디어 3개 → 일본어 Hook → 영상 스크립트 → 영상(또는 영상 생성 프롬프트) → 일본어 자막 → Caption → Hashtag → **승인 요청**
- 승인하면 → 예약 시간(JST)에 영상 + 일본어 캡션 + 해시태그 업로드 → 성과 측정

**생성 파일 저장 위치**
```
assets/generated/
  images/      c{콘텐츠ID}_feed_xxxx.jpg, c{ID}_story_..., c{ID}_carousel_..., ad{광고안ID}_ad_banner_...
  videos/      c{ID}_tiktok_xxxx.mp4  (9:16, 1080x1920, H.264/AAC)
  thumbnails/  c{ID}_tiktok_xxxx.jpg
  subtitles/   c{ID}_tiktok_xxxx.srt  (일본어 자막, 화면당 14자 이내로 분할)
```
파일 이름·이미지 EXIF·영상 메타데이터·DB(generated_assets) 모두에 콘텐츠 ID 가 기록됩니다.

**이미지·영상·음성 생성 방식**
| 항목 | 기본 (무료) | 선택 (유료/외부) |
|---|---|---|
| 이미지 | 서버가 깔끔한 일본 광고 스타일(미니멀, 짧은 일본어, 모바일 가독성)로 직접 디자인 | `IMAGE_PROVIDER=openai` + `OPENAI_API_KEY`: AI 가 배경 비주얼(텍스트 없음)을 만들고, 일본어 문구는 서버가 선명한 폰트로 합성 |
| 영상 | 장면별 배경 + 큰 일본어 자막의 **텍스트 동画(타이포그래피 숏폼)** mp4 | 장면 이미지를 AI 로 생성(설정 > "영상 장면에 AI 이미지 사용"). 실사 촬영/외부 영상 생성 AI(Sora·Veo·Runway 등)는 콘텐츠 상세의 **장면 JSON + 영상 생성 프롬프트**를 사용 |
| 음성 | 없음 (자막만) | **VOICEVOX**(무료 일본어 TTS): male/female × casual/energetic/calm/luxury |

---

## 1. 현재 상태

### ✅ 완료되어 바로 쓸 수 있는 기능
| 기능 | 설명 |
|---|---|
| 웹 대시보드 | 오늘 게시 예정/완료/실패, 승인 대기, 이번 주 콘텐츠 수, 광고 지출·CTR·CPC·CPA·ROAS, 성과 추이 차트 |
| 설치 마법사 | 브랜드·타깃·국가·언어·SNS·API Key·광고·하루 예산 한도를 처음 한 번 설정 |
| Brand Profile (브랜드 메모리) | AI 가 모든 생성/분석에 항상 사용. 금지어가 들어간 콘텐츠는 승인 불가 |
| AI 콘텐츠 생성 | 매일 07:00 (JST) 자동 (최소 5개). 아이디어마다 Instagram / TikTok / X 별도 콘텐츠 + 광고안 패키지 |
| 콘텐츠 점수 | Hook·타깃 적합·브랜드 일관성·CTA·독창성·참여 기대 (내부 우선순위용, 성과 보장 아님) |
| 승인 시스템 | DRAFT → READY_FOR_REVIEW → APPROVED → SCHEDULED → PUBLISHED / FAILED. 일괄 승인, 플랫폼별 자동 승인 설정 |
| 콘텐츠 캘린더 | 일간/주간 보기, **드래그 & 드롭으로 일정 변경** |
| 예약 게시 + 재시도 | 매분 확인. 실패 시 이유 기록 후 1분 → 5분 → 15분 재시도, 그 후 중단 |
| 성과 수집 | 매시 10분. 플랫폼이 주지 않는 지표는 비워 둠(null), 추정하지 않음 |
| AI 성과 분석 → 다음 콘텐츠 반영 | 매일 06:30 분석 결과가 다음 날 생성 프롬프트에 자동 포함 (개선 루프) |
| 광고 분석 / 개선안 / 새 광고안 | 광고별 "CTR 높음·CPA 낮음 → 성과 양호" 식 판단, AI 제안 작업은 승인 대기로 등록 |
| Budget Guard | 1회 ±10% 초과 시 승인 필요, 하루 한도 초과는 무조건 차단 |
| A/B 테스트 | 두 비율 z-검정. 표본이 적으면 "데이터 부족"으로 결론 보류 |
| 경쟁사 분석 | 공개 페이지에서 직접 본 내용을 기록 → AI 가 복제가 아닌 차별화 아이디어 제안 |
| AI Marketing Manager | 자연어 질문 → AI 가 실제 DB 를 조회해서 답변 ("다음 주 콘텐츠 7개 만들어줘"도 가능) |
| Daily / Weekly Report | 매일 21:00 / 매주 월 08:00. DB + `data/reports/*.md` 저장, Slack/Discord 전송 가능 |
| 로그 | AI 생성, 게시 시도, API 응답/오류, 광고 데이터, 승인, 예산 변경 → `logs/app.log` + DB. 토큰은 자동 마스킹 |
| 일본 시장 기본 | DEFAULT_COUNTRY=JP · DEFAULT_LANGUAGE=ja · DEFAULT_CURRENCY=JPY · DEFAULT_TIMEZONE=Asia/Tokyo. 모든 시간 JST 표시, 금액 ¥ 표시 |
| 에이전트 파이프라인 | 트렌드 조사 → 전략 → 카피/해시태그 → 숏폼 스크립트 → 크리에이티브 → Brand Guardian → 이미지/영상 → 승인 대기 (진행 상황 화면 표시) |
| 이미지/영상/자막 자동 생성 | 피드·스토리·캐러셀·썸네일·광고 배너 JPEG, 9:16 mp4 + .srt, `assets/generated/` 저장 |
| Brand Guardian | 일본어 표현 검사(한글 혼입, 번역체, 과장·법적 위험 표현, 금지어, X 글자 수) → 자동 수정 / 보류(DRAFT) |
| JST 게시 시간 학습 | 우리 계정 데이터로 시간대별 참여율 학습, 부족하면 7-9시/12-13시/18-22시를 테스트 후보로 |
| 다국어 | 콘텐츠는 일본어 기본 (한국어/영어는 요청 시), 대시보드 日本語/한국어 |
| Docker | `docker compose up` 한 줄로 실행 |
| 테스트 | pytest 80개 (실제 API 호출 없음) |

### 🧪 지금은 Mock(가짜)으로 동작하는 것 — API Key 만 넣으면 실제로 전환
| 항목 | Mock 일 때 | 실제 전환 조건 |
|---|---|---|
| Claude AI | 템플릿 기반 문구 + 규칙 기반 분석 (`[MOCK AI]` 표시) | `ANTHROPIC_API_KEY` |
| Instagram | 게시 시뮬레이션 + 가짜 성과 (`MOCK` 표시) | Instagram 연결 (OAuth) |
| Facebook 페이지 | 위와 동일 | `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` |
| TikTok | 위와 동일 | TikTok 연결 (OAuth) |
| X | 위와 동일 | X 연결 (OAuth) |
| Meta 광고 | 가짜 캠페인 3개 + 일별 성과 | `META_ADS_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` |

Mock 데이터는 화면과 리포트에 항상 `MOCK` 으로 표시되고, AI 에게도 "테스트 데이터"라고 알려 줍니다.

### 📝 내가 나중에 해야 하는 일 (API 설정)
1. **Claude API Key** 발급 → 설정 화면에 입력 (유료, 사용량 과금)
2. **Instagram**: Meta 개발자 앱 생성 → Instagram Login 설정 → App ID/Secret 입력 → [Instagram 연결]
3. **TikTok**: TikTok 개발자 앱 생성 → Content Posting API 신청 → Client Key/Secret 입력 → [TikTok 연결] → (공개 게시하려면 TikTok 앱 심사)
4. **X**: X 개발자 앱 생성 → OAuth 2.0 설정 → Client ID/Secret 입력 → [X 연결] → 크레딧 구매 (X API 는 사용량 과금)
5. **Meta 광고**: System User 토큰 발급 → 광고 계정 ID 와 함께 입력
6. **미디어 공개 주소**: Instagram/TikTok 은 이미지·영상을 **공개 URL** 에서 가져가므로, 서버를 인터넷에 공개하거나(예: 클라우드 서버) 공개 저장소 URL 을 콘텐츠에 넣어야 합니다
7. 모든 테스트가 끝나면 `DRY_RUN=false` 로 전환

### ⚠️ 알려진 제한 (정직하게)
- 기본 영상은 **텍스트 동画(장면 배경 + 큰 일본어 자막)** 입니다. 실사 영상이 필요하면 장면 JSON/프롬프트로 직접 촬영하거나 외부 영상 생성 AI 를 사용하세요 (외부 영상 API 직접 연동은 아직 없음).
- 일본어 음성은 VOICEVOX 를 따로 실행해야 합니다 (Docker: `docker compose --profile voice up`). 캐릭터별 이용약관·크레딧 표기를 지켜야 합니다.
- OpenAI 이미지 provider 는 공식 API 형식으로 구현했지만 실제 키로는 아직 호출해 보지 않았습니다.
- YouTube Shorts 는 트렌드 분석·제목·9:16 영상까지만 지원하고, 자동 업로드는 아직 없습니다 (YouTube Data API 연동 필요).
- 트렌드 조사의 웹 검색은 Claude API 의 web search 기능을 사용합니다 (검색 1회당 추가 요금, `TREND_WEB_SEARCH=false` 로 끌 수 있음). 웹 검색이 없으면 "일반 지식(미검증)" 으로 표시됩니다.
- 이 개발 환경에서는 Meta/TikTok/X 개발자 문서 사이트 접속이 막혀 있어, 엔드포인트는 **웹 검색으로 확인한 2026년 기준 공식 경로**로 구현했고 실제 계정으로는 아직 호출해 보지 않았습니다. 실제 키를 넣은 뒤 DRY_RUN=true 상태에서 [연결 상태] 를 확인하고, 테스트 계정으로 1건씩 확인하는 것을 권장합니다. Graph API 버전은 `.env` 의 `META_GRAPH_VERSION` 으로 바꿀 수 있습니다.
- X 게시는 **텍스트(및 Thread)만** 지원합니다. X 미디어 첨부는 아직 미구현입니다.
- TikTok 은 **영상만** 게시할 수 있고, 앱 심사 전에는 **비공개(SELF_ONLY)** 로만 게시됩니다. 비공개 게시물은 성과 조회가 제한됩니다.
- Instagram 신규 게시물은 `impressions` 지표를 제공하지 않아 비워 둡니다(null).
- 광고 **삭제 / 캠페인 생성 / 결제 변경**은 안전을 위해 이 시스템에서 실행하지 않습니다. 승인해도 "Ads Manager 에서 직접 진행" 안내만 합니다. AI 가 만든 광고안도 실제 광고 등록은 Ads Manager 에서 직접 합니다.
- 경쟁사 데이터는 자동 수집하지 않습니다 (스크래핑/로그인 우회 금지). 공개 페이지를 보고 직접 기록합니다.

---

## 2. 설치 방법

### 방법 A — Docker (권장, 가장 쉬움)
1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치 후 실행
2. 이 폴더(프로젝트)를 내려받기
3. (선택) `.env.example` 파일을 복사해서 이름을 `.env` 로 변경 — 안 해도 기본값(DRY RUN + Mock)으로 실행됩니다

### 방법 B — Docker 없이
필요한 것: **Python 3.11 이상**, **Node.js 20.19 이상 (22 권장)**
- Mac / Linux: 터미널에서 `./start.sh`
- Windows: `start.bat` 더블클릭

처음 실행할 때 필요한 패키지를 자동으로 설치합니다 (몇 분 걸릴 수 있음).

---

## 3. 실행 방법 / 종료 방법

| | Docker | Docker 없이 |
|---|---|---|
| **실행** | 프로젝트 폴더에서 `docker compose up` | `./start.sh` 또는 `start.bat` |
| **접속** | 브라우저에서 http://localhost:8000 | 동일 |
| **종료** | 터미널에서 `Ctrl + C` (백그라운드 실행 시 `docker compose down`) | `Ctrl + C` |
| **백그라운드 실행** | `docker compose up -d` | - |
| **코드 변경 후 재빌드** | `docker compose up --build` | 다시 실행 |

데이터는 `data/` 폴더(DB, 업로드 파일, 리포트, 화면에서 저장한 키)와 `logs/` 폴더에 남습니다. 종료해도 지워지지 않습니다.

> 자동 작업(예약 게시, 매일 생성 등)은 **서버가 켜져 있는 동안에만** 동작합니다. 매일 자동으로 돌리려면 PC 를 켜 두거나 클라우드 서버에서 실행하세요.

---

## 4. 처음 사용하기
1. http://localhost:8000 접속 → **설치 마법사**가 자동으로 열립니다
2. 브랜드 이름 → 사업 설명 → 타깃/국가/언어 → 연결할 SNS → Claude API Key(선택) → SNS API(선택) → 광고 사용 여부 → 하루 광고 예산 한도
3. [완료] → AI 콘텐츠 전략 + 첫 콘텐츠 후보가 생성되고 **승인 대기** 화면으로 이동
4. 카드를 열어 문구를 고치고 **[승인 + 예약]** → 캘린더에서 일정 확인/드래그로 변경
5. 예약 시간이 되면 자동 게시 (DRY RUN 이면 시뮬레이션) → 매시 성과 수집 → 다음 날 AI 가 분석해서 더 나은 콘텐츠 생성

---

## 5. 매일 자동으로 일어나는 일
시간은 `.env` 의 `DEFAULT_TIMEZONE` 기준 (기본 `Asia/Tokyo` = JST).

| 시간 | 작업 |
|---|---|
| 매분 | 예약 시간이 된 콘텐츠 게시 (실패 시 재시도) |
| 매시 10분 | 게시물 성과 수집 |
| 06:00 | 광고 데이터 수집 (광고 사용 시) |
| 06:20 | AI 광고 분석 + 개선 작업 제안 (승인 대기로) |
| 06:30 | AI 콘텐츠 성과 분석 → 다음 생성에 반영 |
| 06:30 | (위와 함께) JST 게시 시간 재학습 |
| 07:00 | 콘텐츠 패키지 생성: 트렌드 → … → 이미지/영상 → 승인 대기 (설정에서 시간/아이디어 수 변경) |
| 21:00 | Daily Report |
| 월 08:00 | Weekly Report |
| 일 03:00 | Instagram 장기 토큰 갱신 |

어떤 작업이든 화면 버튼(예: [AI 분석], [Daily 지금 생성])으로 즉시 실행할 수도 있습니다.

---

## 6. API Key 넣는 위치
두 가지 방법 중 편한 것을 쓰세요. **소스코드에는 절대 넣지 마세요.**

1. **화면에서 (권장)**: 대시보드 → ⚙️ 설정 → *API Key / Token* → 입력 → [입력한 값 저장]
   - `data/secrets.env` 파일에 저장됩니다 (권한 600, Git 제외). 화면에는 마지막 4자리만 표시됩니다.
2. **.env 파일**: `.env.example` 을 `.env` 로 복사 후 값 입력 → 서버 재시작
   - `.env` 는 `.gitignore` 에 등록되어 Git 에 올라가지 않습니다.

우선순위: 환경변수 > `data/secrets.env` > `.env`

비밀번호는 어디에도 입력/저장하지 않습니다. SNS 토큰은 **OAuth 연결 버튼**으로 받는 것이 원칙입니다.

---

## 7. SNS 연결 방법
공통 준비: 설정 화면 맨 위 [연결 상태] 의 **OAuth Redirect URI** 를 각 개발자 포털에 그대로 등록해야 합니다.
```
{PUBLIC_BASE_URL}/api/oauth/instagram/callback
{PUBLIC_BASE_URL}/api/oauth/tiktok/callback
{PUBLIC_BASE_URL}/api/oauth/x/callback
```
`PUBLIC_BASE_URL` 기본값은 `http://localhost:8000` 입니다. 일부 플랫폼은 `https` 주소만 허용하므로, 그 경우 서버를 https 도메인으로 공개한 뒤 `.env` 의 `PUBLIC_BASE_URL` 을 바꾸세요.

> 각 플랫폼의 화면/메뉴 이름은 자주 바뀝니다. 아래는 2026년 기준 흐름이며, 막히면 각 공식 문서를 확인하세요.

### Instagram (공식 Instagram Platform API — Instagram Login)
- 필요: **비즈니스 또는 크리에이터** Instagram 계정 (개인 계정 불가)
1. https://developers.facebook.com → 앱 만들기 → Instagram 제품 추가 → *API setup with Instagram login*
2. 권한: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_insights`
3. Redirect URI 등록 → Instagram App ID / App Secret 을 설정 화면의 `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` 에 저장
4. 설정 → [Instagram 연결 (OAuth)] → 로그인/허용 → 장기 토큰과 계정 ID 가 자동 저장
- 게시 흐름: 미디어 컨테이너 생성 → 처리 완료 확인 → 게시 (24시간 100건 제한)
- 이미지/영상은 **공개 URL** 이어야 합니다 → `PUBLIC_MEDIA_BASE_URL` 을 설정하면 자동 생성된 파일(`/generated/...`)을 그 주소로 Instagram 에 넘깁니다. 이미지는 JPEG 로 생성됩니다. 캐러셀도 자동 게시됩니다
- Facebook Login 방식 토큰을 이미 갖고 있다면 `INSTAGRAM_API_HOST=graph.facebook.com` + 토큰/ID 를 직접 입력해도 됩니다

### Facebook 페이지
1. Meta 앱에서 페이지 권한(`pages_manage_posts`, `pages_read_engagement`) 으로 **Page access token** 발급
2. `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` 저장 → 설정에서 Facebook 사용 체크

### TikTok (공식 Content Posting API)
1. https://developers.tiktok.com → 앱 만들기 → *Login Kit* + *Content Posting API* 추가 (Direct Post)
2. scope: `user.info.basic`, `video.publish`, `video.upload`, `video.list`
3. Redirect URI 등록 → `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` 저장 → [TikTok 연결 (OAuth)]
- **심사(audit) 전에는 비공개(SELF_ONLY) 게시만 가능**합니다. 심사 통과 후 `.env` 의 `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE` 으로 변경
- 서버에 있는 영상 파일(자동 생성 영상 포함, 64MB 이하)은 **직접 업로드(FILE_UPLOAD)** 로 보내므로 도메인 인증이 필요 없습니다. URL 만 있는 경우(PULL_FROM_URL)는 도메인 인증이 필요합니다

### X (공식 X API v2)
1. https://developer.x.com → 프로젝트/앱 생성 → *User authentication settings* 에서 OAuth 2.0 켜기 (Read and write)
2. Redirect URI 등록 → `X_CLIENT_ID`, `X_CLIENT_SECRET` 저장 → [X 연결 (OAuth)]
- scope: `tweet.read tweet.write users.read offline.access` (토큰은 자동 갱신)
- **X API 는 사용량 과금**입니다 (게시/조회마다 크레딧 차감). Developer Console 에서 크레딧과 요금을 확인하세요

연결 후 설정 → [연결 상태] 에서 해당 SNS 가 **LIVE** 로 바뀌면 성공입니다. (DRY_RUN=true 인 동안은 LIVE 여도 실제 게시하지 않습니다.)

---

## 8. 광고 계정 연결 방법
1. Meta Business Suite → 비즈니스 설정 → **시스템 사용자** 생성 → 광고 계정 자산 할당
2. 토큰 생성: 권한 `ads_read` (조회), `ads_management` (승인한 예산/상태 변경을 실행하려면)
3. 광고 계정 ID 확인 (Ads Manager 주소의 `act=` 뒤 숫자)
4. 설정 화면에 `META_ADS_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID` 저장, [광고 데이터 자동 수집/분석] 체크
5. 광고 메뉴 → [데이터 가져오기] → [AI 분석]

수집 항목: Campaign / Ad Set / Ad, Spend, Impressions, Reach, Clicks, CTR, CPC, CPM, Conversions, CPA, ROAS
(전환은 구매 → 리드 순으로 찾습니다. 픽셀/전환 설정이 없으면 비어 있습니다.)

---

## 9. Dry Run 해제 방법
**모든 기능을 DRY RUN 으로 충분히 확인한 뒤에만** 하세요.
1. `.env` 파일을 열어 `DRY_RUN=true` → `DRY_RUN=false`
2. 서버 재시작 (`Ctrl + C` 후 다시 실행, 또는 `docker compose up -d --force-recreate`)
3. 화면 상단 배너가 🔴 **LIVE 모드** 로 바뀌었는지 확인

LIVE 모드에서도:
- 승인하지 않은 콘텐츠는 게시되지 않습니다
- [지금 게시], 광고 작업 승인, 자동 승인 켜기는 확인창이 한 번 더 뜹니다
- Budget Guard 한도는 그대로 적용됩니다

다시 안전 모드로 돌아가려면 `DRY_RUN=true` 로 바꾸고 재시작하면 됩니다.
(DRY_RUN 은 실수로 켜지지 않도록 화면에서는 바꿀 수 없게 했습니다.)

---

## 10. 안전장치 정리
| 장치 | 내용 |
|---|---|
| DRY_RUN | 기본 true. 게시·광고 수정 API 를 아예 호출하지 않음 |
| 콘텐츠 승인 | AI 생성물은 READY_FOR_REVIEW. 승인 후 문구를 고치면 다시 승인 필요. 금지어 포함 시 승인 불가 |
| Budget Guard | 1회 변경 ±10% 초과 → 승인 필요 / 변경액이 `approval_required_above` 초과 → 승인 필요 / 변경 후 일일 예산 합계가 한도 초과 → **차단** / 오늘 지출이 한도 도달 시 증액 **차단** / 승인 시점에 한 번 더 검사 |
| 항상 승인 필요 | 광고 중지·재개·삭제·캠페인 생성·결제 변경 (삭제/생성/결제는 아예 실행 안 함) |
| 광고 자동 실행 | 기본 꺼짐. 켜도 Guard 범위 내 소폭 예산 변경만 자동 |
| 재시도 제한 | 1분 → 5분 → 15분 후 최종 실패 처리 (무한 반복 없음) |
| 비밀값 보호 | 소스코드에 키 없음, `.env`/`data/secrets.env` Git 제외, 로그·API 응답에서 토큰 자동 마스킹, 비밀번호 미저장 |
| Timeout | 모든 외부 API 호출에 timeout (기본 20초, Claude 300초) |
| 점수 표시 | "내부 우선순위용, 성과 보장 아님" 명시 |
| 데이터 정직성 | 없는 지표는 null, AI 는 DB 에 없는 수치를 만들지 않도록 지시, Mock 데이터는 항상 표시 |

---

## 11. 오류 해결 방법
| 증상 | 해결 |
|---|---|
| 화면에 "백엔드 서버에 연결할 수 없습니다" | 서버가 꺼져 있습니다. 3장의 실행 방법으로 다시 실행 |
| `docker compose up` 에서 `port is already allocated` | 8000 포트를 다른 프로그램이 사용 중. 그 프로그램을 끄거나 `docker-compose.yml` 의 `"8000:8000"` 을 `"8080:8000"` 으로 바꾸고 http://localhost:8080 접속 |
| `docker: command not found` / daemon 오류 | Docker Desktop 을 설치하고 실행 상태인지 확인 |
| `start.sh: Permission denied` | `chmod +x start.sh` 후 다시 실행 |
| `python3: command not found` / 버전 오류 | Python 3.11 이상 설치 (Windows 는 설치 시 "Add to PATH" 체크) |
| AI 가 계속 `[MOCK AI]` 로 생성 | Claude API Key 미설정 또는 오류. 📜 로그에서 `api_error` 확인. "API Key 가 올바르지 않습니다" → 키 재입력 |
| "Claude API 사용량 한도" | 잠시 후 재시도, 또는 Anthropic Console 에서 한도/결제 확인 |
| 게시 실패: "공개 URL 의 이미지/영상이 필요" | Instagram/TikTok 은 공개 URL 필요. 콘텐츠에 미디어 URL 입력 또는 `PUBLIC_MEDIA_BASE_URL` 설정 |
| 게시 실패: HTTP 400/403 | 토큰 권한 부족 또는 만료. 설정에서 해당 SNS [연결] 을 다시 실행. 실패 이유는 콘텐츠 상세와 📜 로그에 기록됨 |
| TikTok "공개 범위 ... 를 사용할 수 없습니다" | 심사 전 앱입니다. `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` 유지 |
| OAuth 후 "invalid_state" | 15분 안에 로그인을 끝내지 못했거나 서버가 재시작됨. 다시 [연결] 클릭 |
| OAuth redirect_uri 불일치 | 개발자 포털에 등록한 주소와 `PUBLIC_BASE_URL` 이 정확히 같은지 확인 |
| 광고 작업이 BLOCKED | Budget Guard 한도 초과. 광고 → Budget Guard 에서 한도 확인 (의도된 안전장치) |
| 예약했는데 게시가 안 됨 | 서버가 켜져 있어야 합니다. 상태가 SCHEDULED 인지, 시간이 지났는지 확인 |
| 시간이 이상하게 보임 | 화면과 자동 작업 모두 `.env` 의 `DEFAULT_TIMEZONE`(기본 JST) 기준입니다. PC 시간대와 달라도 JST 로 표시됩니다 |
| 이미지 속 일본어가 □□ 로 깨짐 | 일본어 폰트가 없습니다. Docker 는 자동 설치됨. 직접 실행 시 Mac/Windows 는 기본 폰트를 자동 사용, Linux 는 `sudo apt install fonts-noto-cjk` 또는 `.env` 에 `FONT_PATH` 지정 |
| 영상이 만들어지지 않음 ("ffmpeg") | `pip install -r backend/requirements.txt` 를 다시 실행 (imageio-ffmpeg 가 ffmpeg 를 포함). 설정 화면의 "이미지·영상·음성 환경" 에서 확인 |
| 영상에 음성이 없음 | VOICEVOX 를 실행하고 `VOICEVOX_URL` 설정 (기본은 자막만) |
| 콘텐츠가 "Brand Guardian: 승인 단계로 보내지 않음" | 일본어 표현·금지어·과장 표현 문제입니다. 승인 대기 화면 아래 "보류한 콘텐츠" 에서 수정 후 [검토 요청]. 브랜드 프로필의 제품명을 일본어로 입력하면 줄어듭니다 |
| 처음부터 다시 시작하고 싶음 | ⚠️ 모든 데이터가 지워집니다: 서버 종료 후 `data/app.db*` 파일 삭제 → 재실행 |

그래도 안 되면 `logs/app.log` 의 마지막 부분을 확인하세요 (토큰은 자동으로 가려져 있어 공유해도 안전합니다).

---

## 12. 고급

### PostgreSQL 로 변경
1. `backend/requirements.txt` 의 `psycopg[binary]` 줄 주석 해제
2. `.env` 에 `DATABASE_URL=postgresql+psycopg://사용자:비밀번호@호스트:5432/DB이름`
3. Docker 를 쓴다면 `docker-compose.yml` 아래의 `db` 서비스 주석 해제 후 `docker compose up --build`
테이블은 시작 시 자동 생성됩니다. (기존 SQLite 데이터는 자동으로 옮겨지지 않습니다.)

### 테스트 실행
```bash
pip install -r backend/requirements-dev.txt
python -m pytest
```
실제 SNS/Claude API 는 호출하지 않습니다 (httpx MockTransport + 가짜 Claude 클라이언트).
포함: 에이전트 파이프라인(일본어 기본·플랫폼별 패키지) / 이미지·영상·자막·음성 / Brand Guardian 규칙 / JST 게시 시간 학습 / DB·자동 마이그레이션 / SNS connector(캐러셀 포함) / Scheduler·재시도 / Budget Guard / Dry Run / 전체 흐름 API / A/B 통계

### 개발 모드 (화면 수정 시)
```bash
cd backend && python -m uvicorn app.main:app --reload     # 터미널 1
cd frontend && npm install && npm run dev                  # 터미널 2 → http://localhost:5173
```

### 일본어 음성 (VOICEVOX) 켜기
1. Docker: `docker compose --profile voice up` (처음엔 엔진 이미지 다운로드로 시간이 걸립니다)
   Docker 없이: https://voicevox.hiroshiba.jp 에서 VOICEVOX 를 설치·실행 (기본 주소 http://localhost:50021)
2. `.env` 에 `VOICEVOX_URL=http://voicevox:50021` (Docker) 또는 `http://localhost:50021` (직접 실행) → 재시작
3. 설정 → "영상 음성" 에서 male/female, casual/energetic/calm/luxury 와 speaker ID 선택 ([음성 목록 보기])

### AI 이미지 (OpenAI) 켜기
`.env` 에 `IMAGE_PROVIDER=openai`, `OPENAI_API_KEY=...` → 재시작. 실패하면 자동으로 무료 템플릿 디자인으로 대체됩니다.

### Claude 모델 / 비용
- 기본 모델 `claude-opus-5-5`, `CLAUDE_EFFORT=medium`. 비용을 줄이려면 `CLAUDE_EFFORT=low`
- 하루 기본 사용량: 콘텐츠 패키지 1회(트렌드 조사 1 + 웹 검색 최대 5 + 전략 1 + 카피 1 + 스크립트 1 + 크리에이티브 1 + Guardian 1) + 분석 1~2회 + 리포트 1회 + 질문한 만큼
- 안전 정책으로 거절된 요청은 서버 측 fallback 모델로 자동 재시도합니다

### 알림 채널 추가 (Email / LINE 등)
`backend/app/services/notifiers.py` 에 `Notifier` 를 상속한 클래스를 만들고 `NOTIFIERS` 에 등록하면 설정 화면의 리포트 채널로 쓸 수 있습니다.

### 폴더 구조
```
├─ backend/
│  ├─ app/
│  │  ├─ main.py            # FastAPI 진입점 (화면 + API 제공)
│  │  ├─ api/               # REST API (content, calendar, ads, chat, reports, oauth ...)
│  │  ├─ core/              # 설정(.env), DB, 로그, 비밀값 마스킹, secret 저장소
│  │  ├─ models/            # DB 테이블
│  │  ├─ services/          # 승인 흐름, 게시기, 성과 수집, 광고, Budget Guard, 리포트, 알림
│  │  ├─ connectors/        # instagram.py facebook.py tiktok.py x.py meta_ads.py mock.py
│  │  ├─ agents/            # 일본 시장 에이전트: trend, team(전략/카피/스크립트/크리에이티브/가디언), pipeline, posting_times, rules
│  │  ├─ media/             # 이미지 렌더링, 영상(ffmpeg), VOICEVOX TTS, 일본어 폰트, 파일 저장
│  │  ├─ ai/                # Claude 클라이언트, 분석, AI 매니저, Mock AI
│  │  ├─ scheduler/         # APScheduler 자동 작업
│  │  └─ analytics/         # 성과 집계, A/B 통계
│  └─ requirements.txt
├─ frontend/                # React(Vite) 대시보드
├─ tests/                   # pytest
├─ assets/generated/        # AI 가 만든 이미지·영상·썸네일·자막 (Git 제외)
├─ data/                    # DB, 업로드, 리포트, secrets.env (Git 제외)
├─ logs/                    # app.log (Git 제외)
├─ .env.example             # 설정 예시 (복사해서 .env 로 사용)
├─ Dockerfile, docker-compose.yml
└─ start.sh, start.bat      # Docker 없이 실행
```

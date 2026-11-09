# 주요 기능의 지원 조건과 주의사항

조사일 2026-11-08. 각 항목의 근거를 [공식 명세] / [릴리스 노트·공지 날짜] / [프로젝트 기록]으로 구분했다.
[프로젝트 기록]은 이 저장소가 실계정·네이버 답변으로 확인한 내용이며 공식 문서에는 없다. 공식 근거가 없는 내용은 그렇게 표시했다.

## 1. 명세 JSON과 릴리스 노트가 다른 곳

| 항목 | 명세 JSON | 릴리스 노트·공지 | 판단 |
|---|---|---|---|
| ADVoost 플레이스 `useAdvoost` | 없음. 광고그룹 `fields` 허용값에도 없음 | 2026-09-16: `PUT /ncc/adgroups/{id}?fields=useAdvoost` 또는 전체 수정의 `adgroupAttrJson`으로 설정 | 릴리스 노트가 더 최신. 명세 미반영으로 봄 |
| 제외검색어 조회 type | 조회 경로에 `type=KEYWORD_PLUS_RESTRICT`만 표기 | 2024-09-13: `EXP_SEARCH`(확장검색) 추가 | 모델(`AdgroupRestrictKwd.type`)에는 둘 다 있음. 조회 경로에서 EXP_SEARCH로 부를 수 있는지는 **미확인** |
| 확장소재 PRICE_LINKS | 유형 허용값에 아직 있음 | 2025-02-05: 가격링크 등록 종료 | 등록 불가로 봐야 함 |
| 이미지 확장소재 등록 경로 | `POST /ncc/ad-extensions` | 2025-06-25 노트 본문에 `POST /ncc/ad-extensions/create`로 표기 | 명세에 `/create` 경로 없음. 노트의 오기로 보이나 **미확인** |
| STATS `pcNxAvgCpc`·`mblNxAvgCpc` | fields 허용값에 없음 | 2025-09-26: 신규 제공 | 명세 미반영 |
| 공유예산 삭제 설명 | "공유예산의 하루예산을 수정합니다"(복사 오류) | - | 경로·요약(summary=delete)으로 보아 삭제 |
| 쇼핑 상품소재 등록 형식 | 단건 본문(`AdRequest`), `isList` 파라미터 없음 | - | [프로젝트 기록] 쇼핑 소재는 배열 + `?isList=true`여야 함(공식 저장소 이슈 #188·#202 답변). 명세만으로는 **미확인** |
| 소재 입찰가 변경 | 소재 변경 fields 허용값: `userLock`, `inspect` | - | [프로젝트 기록] 네이버 문의 답변대로 `fields=adAttr`로 변경. 명세에 없음 |
| 상품 식별자 필드 | `AdRequest`에 `referenceKey` 필드 없음(소재 내용 `ad`는 JsonNode) | - | [프로젝트 기록] `referenceKey`=네이버쇼핑 상품 ID(nvMid). 명세만으로는 **미확인** |

## 2. 확장소재 유형별 조건

명세 허용값 36종: PHONE, LOCATION, BOOKING, TALK, CALCULATION, HEADLINE, DESCRIPTION, SUB_LINKS, PRICE_LINKS, PROMOTION, SHOPPING_EXTRA, POWER_LINK_IMAGE, IMAGE_SUB_LINKS, PLACE, CATALOG_*(9종), NAVER_TV_VIDEO, NAVER_BLOG_REVIEW, SHOPPING_BRAND_*(5종), PLACE_SMART_ORDER, PLACE_BEAUTY_STYLE, DESCRIPTION_EXTRA, SHOPPING_WEB, WEBSITE_INFO, TALKTALK_CONSULTATION.

| 유형 | 조건 | 근거 |
|---|---|---|
| PRICE_LINKS(가격링크) | 2025-02-05부터 등록 불가 | 릴리스 노트 2025-02-05 |
| WEBSITE_INFO(웹사이트정보) | API로 등록하면 "사이트 정보 수집·활용에 동의한 것으로 간주", 정보의 정확성·적법성 책임은 광고주 | 릴리스 노트 2025-05-14 |
| POWER_LINK_IMAGE, IMAGE_SUB_LINKS | `imagePath`에 Base64(JPEG·PNG, 최대 5MB, 214×214 고정). 이미지 서브링크는 최대 3개 | 릴리스 노트 2025-06-25 |
| TALKTALK_CONSULTATION(톡톡상담) | 필수: talkAccountId, url, description | 릴리스 노트 2026-06-04 |
| 노출 기간(periodStartDt·EndDt) | KST 자정을 UTC로 쓴 값만(예: `2026-06-01T15:00:00.000Z`), 아니면 400 | 공지 2026-06-10 |
| HEADLINE·DESCRIPTION·DESCRIPTION_EXTRA·SUB_LINKS 글자 수 | 공식 명세에 글자 수 없음(**미확인**) | [프로젝트 기록] 추가제목 15자, 홍보문구 14자, 추가설명 45자로 운영 |
| ADVoost 켜진 그룹 | 확장소재 추가 불가(4029) | 릴리스 노트 2026-09-16 |
| 문구 수정 | 공식 설명에 내용 변경 언급 없음 | [프로젝트 기록] 수정 불가 → 새로 만들고 예전 것 삭제 |

## 3. 플레이스

### 3-1. 검색광고 API로 할 수 있는 범위

| 구분 | 검색광고 API | 근거 |
|---|---|---|
| 플레이스 캠페인(campaignTp=PLACE) 만들기·켜기·예산 | 가능 | 명세 |
| 광고그룹: LOCAL_AD(플레이스 검색), PLACE(지역소상공인) | 가능 | 명세 adgroupType |
| 소재: LOCAL_AD, PLACE_AD | 가능 | 명세 Ad.type |
| 연동형 소재 ADVOOST_PLACE_AD | 조회만(시스템이 만듦) | 릴리스 노트 2026-09-16 |
| 플레이스 비즈채널 조회, 광고 가능한 플레이스 채널 조회 | 가능 | 명세(#44 channelTp=PLACE, #66) |
| 플레이스 확장소재(PLACE, PLACE_SMART_ORDER, PLACE_BEAUTY_STYLE) | 유형은 있음, 유형별 내용 형식은 **미확인** | 명세 허용값만 |
| 플레이스 검색 그룹 매체 타기팅(검색/콘텐츠, 네이버/파트너) | 가능 | 릴리스 노트 2024-11-13 |
| 플레이스 그룹 태그(PLACE_ADGROUP_TAG) | 타깃 유형에 있음, 형식 **미확인** | 명세 허용값만 |

### 3-2. 검색광고 API 밖 (스마트플레이스)

- 업체 등록·이름·주소·영업시간·사진·메뉴·가격·예약·리뷰 답글 = **스마트플레이스** 영역. 검색광고 API 명세에 해당 엔드포인트 없음.
- 검색광고 API는 스마트플레이스에 이미 있는 업체를 비즈채널(PLACE)로 연결해 광고만 관리한다.
- 업체 비즈채널을 API로 새로 "등록"할 수 있는지(`POST /ncc/channels`에 channelTp=PLACE): 명세의 `BusinessChannel.channelTp`에 PLACE가 있으나 등록 가능 여부·필수 값은 **미확인**.
- 스마트플레이스용 공개 API가 따로 있는지는 이번 조사 범위(검색광고 API) 밖이라 확인하지 않았다.

### 3-3. ADVoost 플레이스 (릴리스 노트 2026-09-16)

- 켜는 법: LOCAL_AD 그룹의 `adgroupAttrJson.useAdvoost=true`. 켜면 연동형 소재 1개 자동 생성(다시 켜면 재활성화), 끄면 연동형 소재가 OFF.
- 조건: 스마트플레이스 업체 이미지 1개 이상(없으면 3752, 반영까지 최대 10분), **병의원 업종 불가**(3756), 업체 정보 못 불러오면 3753.
- 켜진 그룹에서 막히는 것(400):

| 요청 | 코드 |
|---|---|
| 소재 추가 | 3839 |
| 확장소재 추가 | 4029 |
| 제외검색어 등록 | 3754, 4422 |
| 매체 타기팅 변경 | 4420 |
| 요일·시간 외 타기팅 변경(지역·연령·성별·상세위치) | 5117 |
| 고급옵션 변경(bidAmt, 매체 가중치, contentsNetworkBidAmt, useExpSearch, adRollingType 등) | 3755 |
| 태그 설정 | 4421 |
| 연동형 소재 직접 등록 / ON·OFF / 켜진 동안 삭제 | 3840 / 3838 / 3837 |
| adgroupAttrJson의 변경 불가 필드 수정 | 3749 |

- **광고비 주의**: 켜면 입찰가를 바꿀 수 없다(3755). 지출은 하루예산으로만 조절된다. 하루예산이 실제 과금 상한이 아니라는 점은 [05](05-service-usage.md#3-광고비-관련-확인된-사실과-설계-주의).

## 4. 쇼핑검색

- 캠페인 SHOPPING → 광고그룹 SHOPPING(쇼핑몰 상품형)·CATALOG(제품 카탈로그)·SHOPPING_BRAND(브랜드형) → 소재 SHOPPING_PRODUCT_AD·CATALOG_AD·SHOPPING_BRAND_* [명세].
- 쇼핑몰 비즈채널(MALL) 검수 통과가 필요하다 [명세 channelTp + 프로젝트 기록].
- 소재 입찰가는 소재의 `adAttr`("쇼핑 광고면 필수") [명세]. 바꾸는 방법(`fields=adAttr`)은 [프로젝트 기록]만 있음.
- 상품 식별자: [프로젝트 기록] `referenceKey`=네이버쇼핑 상품 ID(nvMid). 스마트스토어 상품 번호를 넣으면 실패('Invalid ad type', 10/31 실계정).
- 전환목표 자동입찰(Beta, 2025-10-15): 쇼핑몰 상품형 그룹 중 전환 로그를 수집하는 그룹만. `autobidStrategy`: `autobidTargetType=GRP`, `autobidBidGoal=NONE|MAX_CONV_VALUE`, `autobidBidType=CPC`, `autobidBidStrategy=NO_CAP`, `autobidBidStrategyValue=0`, `isAutobidActive`. 명세 모델에는 MAX_CLICK·TARGET_CPA·BID_CAP 등 더 많은 값이 있으나 릴리스 노트는 위 값만 "고정"으로 안내 → 다른 값 허용 여부 **미확인**.
  자동입찰은 "하루예산 내에서 기본입찰가·소재 노출 여부·실제 입찰가를 관리"한다(노트 문구).
- 이전 자동입찰 MAXCONV는 2025-08-13부터 설정 불가, 2025-09-10 NONE으로 전환 [공지 2025-07-30].
- 쇼핑 캠페인 추적 URL 파라미터 `trackingUrlCustomParams` 최대 5쌍, key·value 100byte [릴리스 노트 2024-11-20].
- 품질지수: 쇼핑몰 상품형·카탈로그는 2026-11-25부터 고정값 4(클릭기대지수로 전환) [공지 2026-10-29].

## 5. 파워링크

- 반응형 소재 RSA_AD(`assets` 사용) [릴리스 노트 2024-03-20, 명세].
- 확장검색 `useExpSearch`(기본 사용), `expSearchBudgetRatio`, 제외검색어 type EXP_SEARCH [2024-09-13].
- ADVoost Max `aiAdsOptIn`: 파워링크+확장검색 그룹만, **미지정 시 true** [2026-07-15]. → 광고그룹을 만들 때 값을 빼면 켜진 채로 만들어진다.
- 키워드 확장(Beta)·유사검색어 노출 옵션 종료(2024-08-19): keywordPlus 관련 필드 제거.
- 품질지수 종료(2026-07-29부터 고정값 4) — "애드부스트 검색 기술이 전체 검색어로 적용"되어서 [공지 2026-06-30].
- 키워드 등록 시 입찰가: [프로젝트 기록] 그룹 입찰가를 쓰더라도 `bidAmt`가 없으면 3916 오류.

## 6. 성과 데이터

- STATS: 약 2시간 지연, 무효 클릭 제거 등으로 최대 48시간 안에 바뀔 수 있음, `cycleBaseTm` 분 단위 [공지 2025-09-26].
- 대용량 보고서: 보관 14일, 데이터가 바뀌면 상태 CHANGED가 되고 조회 불가 → 다시 만들어야 함 [2025-09-26].
- 2026-03-30부터 보고서의 비용(COST)은 정수·**VAT 포함** [공지 2026-02-11]. 광고주센터 합계와 정확히 일치하지 않을 수 있음.
- 구매완료 전환 지표 purchaseCcnt·purchaseConvAmt(2026-03-30), purchaseRor(2026-05-13).
- 다운로드 URL에 `fileversion` 쿼리가 붙음(2025-10-19/27 이후 생성분).

## 7. 권한·계정

- API 키는 광고주센터에서 발급하고, `X-Customer`로 다룰 광고 계정을 고른다. 키 하나로 어떤 계정을 다룰 수 있는지는 2025-09 계정 통합 뒤 광고 계정·관리 계정 구성원 권한을 따른다(#98~#101). 권한 등급별로 허용되는 작업 목록은 공식 문서에 **없음**(미확인).
- 대행사 Agent 관리·영업권 관리계정 전환 방식은 "추후 가이드 예정"이라고만 공지됨(2025-08-12).

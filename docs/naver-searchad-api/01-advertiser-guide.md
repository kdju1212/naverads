# 광고주가 API로 할 수 있는 일 (주제별)

조사일 2026-11-08 · 근거: 공식 명세 JSON 9개 + 공식 릴리스 노트·공지(→ [README](README.md#출처)).
각 줄의 `#번호`는 [03-endpoints.md](03-endpoints.md)의 엔드포인트 번호다(공식 문서 링크도 거기 있다).

**읽는 법**
- 구분: 조회 / 생성 / 변경 / 삭제
- 광고비·노출 영향: **없음**(보기만 함) · **있음**(노출 범위·모양이 바뀜, 광고비가 늘거나 줄 수 있음) · **높음**(입찰가·예산·ON/OFF처럼 광고비에 바로 반영)
- "하루예산"은 네이버가 광고를 멈추는 기준값이지 **실제 과금의 절대 상한이 아니다.** 공식 명세는 하루예산을 "캠페인·광고그룹에 설정된 하루 예산 최대값"이라고만 설명하고, 초과 과금 여부·정도는 명세에 없다(미확인). 서비스 설계는 초과될 수 있다고 보고 만든다 → [05-service-usage.md](05-service-usage.md#3-광고비-관련-확인된-사실과-설계-주의)

광고 구조 한눈에 보기:

```
광고 계정 ─┬─ 비즈채널 (웹사이트·쇼핑몰·플레이스 업체·전화번호 …)  ← 광고가 연결될 "가게"
           └─ 캠페인 (파워링크 / 쇼핑검색 / 파워콘텐츠 / 브랜드검색 / 플레이스) ← 하루예산·기간
                └─ 광고그룹 ← 입찰가·하루예산·타기팅·ADVoost
                     ├─ 키워드 (파워링크 등) ← 키워드별 입찰가
                     ├─ 소재 (광고 문구 / 쇼핑 상품 / 플레이스 업체)
                     ├─ 확장소재 (추가제목·전화·서브링크·이미지 …)
                     └─ 제외검색어
```

---

## 1. 광고 계정·권한

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 내가 들어가 있는 광고 계정 목록 보기 | 조회 | 없음 | 2025-09-01 광고 계정 통합 뒤 새로 생긴 API. 응답 필드는 바뀔 수 있다고 공지됨 | [#98](03-endpoints.md#ep-098) |
| 광고 계정 하나의 구성원(누가 어떤 권한인지) 보기 | 조회 | 없음 | 내가 구성원인 계정만 | [#99](03-endpoints.md#ep-099) |
| 내가 들어가 있는 관리 계정(대행사 등) 보기 | 조회 | 없음 | 위와 같음 | [#100](03-endpoints.md#ep-100) |
| 관리 계정 아래 광고 계정 목록 보기 | 조회 | 없음 | 위와 같음 | [#101](03-endpoints.md#ep-101) |

- **API로 할 수 없는 것**: 구성원 초대·권한 변경, API 키 발급(광고주센터에서만).
- **폐기**: `ManagedCustomerLink`(`GET /customer-links`)는 2025-09-15 종료(공지 2025-08-07). 현재 명세에서도 빠짐.

## 2. 비즈채널 (광고를 연결할 웹사이트·쇼핑몰·업체)

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 비즈채널 목록·1개·유형별·ID별 보기 | 조회 | 없음 | 유형: SITE, PHONE, ADDRESS, BOOKING, TALK, MALL, CONTENTS, PLACE, CATALOG, NAVER_TV, BRAND_STORE, SHOPPING_BRAND | [#38](03-endpoints.md#ep-038) [#40](03-endpoints.md#ep-040) [#44](03-endpoints.md#ep-044) [#45](03-endpoints.md#ep-045) |
| 비즈채널 새로 등록 | 생성 | 간접 | 네이버 검수 필요. 웹사이트는 2024-02-07부터 사이트 이름(siteName) 필요 | [#39](03-endpoints.md#ep-039) |
| 이름·검수용 계정 정보 바꾸기 | 변경 | 간접 | fields: name, inspectId, inspectPw, secondary | [#43](03-endpoints.md#ep-043) |
| 반려된 비즈채널 재검수 요청 | 변경 | 간접 | | [#42](03-endpoints.md#ep-042) |
| 비즈채널 삭제(1개·여러 개) | 삭제 | 있음 | 연결된 광고가 노출되지 못할 수 있음 | [#41](03-endpoints.md#ep-041) [#46](03-endpoints.md#ep-046) |
| 플레이스 광고에 쓸 수 있는 업체 채널 보기 | 조회 | 없음 | | [#66](03-endpoints.md#ep-066) |

## 3. 캠페인

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 캠페인 목록·1개·ID별 보기 | 조회 | 없음 | 유형: WEB_SITE(파워링크), SHOPPING(쇼핑검색), POWER_CONTENTS, BRAND_SEARCH, PLACE | [#35](03-endpoints.md#ep-035) [#32](03-endpoints.md#ep-032) [#36](03-endpoints.md#ep-036) |
| 캠페인 새로 만들기 | 생성 | 있음 | 생성 필수: customerId, name, campaignTp. 하루예산·기간 선택 | [#30](03-endpoints.md#ep-030) |
| **캠페인 켜기/끄기** | 변경 | **높음** | `fields=userLock` | [#34](03-endpoints.md#ep-034) |
| **캠페인 하루예산 바꾸기** | 변경 | **높음** | `fields=budget`. 균등 소진(STANDARD)/빠른 소진(ACCELERATED) 선택 가능 | [#34](03-endpoints.md#ep-034) |
| 노출 기간 정하기 | 변경 | 있음 | `fields=period`. 2026-06-10부터 KST 자정 값만 허용(예: `2026-06-01T15:00:00.000Z`) | [#34](03-endpoints.md#ep-034) |
| 쇼핑 캠페인 추적 URL 파라미터 | 변경 | 없음 | `trackingUrlCustomParams`, 쇼핑검색만, 최대 5쌍(2024-11-20) | [#34](03-endpoints.md#ep-034) |
| 캠페인 삭제(1개·여러 개) | 삭제 | 있음 | **하위 광고그룹·키워드·소재 전부 삭제, 복구 불가**(2024-01-25) | [#33](03-endpoints.md#ep-033) [#37](03-endpoints.md#ep-037) |

## 4. 광고그룹

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 캠페인별·1개·ID별 광고그룹 보기 | 조회 | 없음 | 유형: WEB_SITE, SHOPPING, INFORMATION, PRODUCT, BRAND_SEARCH, PLACE, CATALOG, BRAND_ZONE, SHOPPING_BRAND, LOCAL_AD, BRAND_NEW, DOOH | [#19](03-endpoints.md#ep-019) [#11](03-endpoints.md#ep-011) [#18](03-endpoints.md#ep-018) |
| 광고그룹 새로 만들기 | 생성 | 있음 | 생성 필수: customerId, name, nccCampaignId, pcChannelId, mobileChannelId(비즈채널) | [#9](03-endpoints.md#ep-009) |
| **기본 입찰가 바꾸기** | 변경 | **높음** | `fields=bidAmt` | [#17](03-endpoints.md#ep-017) |
| **광고그룹 켜기/끄기** | 변경 | **높음** | `fields=userLock` | [#17](03-endpoints.md#ep-017) |
| **광고그룹 하루예산 바꾸기** | 변경 | **높음** | `fields=budget` | [#17](03-endpoints.md#ep-017) |
| PC·모바일·콘텐츠 매체 입찰 가중치 | 변경 | **높음** | `fields=networkBidWeight` | [#17](03-endpoints.md#ep-017) |
| 지역·시간·매체·성별 타기팅 | 변경 | 있음 | `fields=targetLocation/targetTime/targetMedia/targetGender` | [#17](03-endpoints.md#ep-017) |
| 확장검색 켜기/끄기·예산 비율 | 변경 | 있음 | `useExpSearch`, `expSearchBudgetRatio`(2024-10-02 도입, 파워링크) | [#12](03-endpoints.md#ep-012) |
| **ADVoost Max 켜기/끄기** | 변경 | **높음** | `aiAdsOptIn`, 파워링크+확장검색 그룹만, **값을 안 주면 true(켜짐)**(2026-07-15) | [#9](03-endpoints.md#ep-009) [#12](03-endpoints.md#ep-012) |
| **ADVoost 플레이스 켜기/끄기** | 변경 | **높음** | `adgroupAttrJson.useAdvoost`, LOCAL_AD 그룹만(2026-09-16). 명세 JSON에는 아직 없음 | [#12](03-endpoints.md#ep-012) |
| 쇼핑 전환목표 자동입찰 | 변경 | **높음** | `autobidStrategy`, 쇼핑몰 상품형 그룹만(2025-10-15 Beta) | [#9](03-endpoints.md#ep-009) [#12](03-endpoints.md#ep-012) |
| 광고그룹 삭제 | 삭제 | 있음 | 그룹 안 키워드·소재까지 삭제 | [#13](03-endpoints.md#ep-013) |
| 공유예산에 묶인 광고그룹 보기 | 조회 | 없음 | | [#10](03-endpoints.md#ep-010) |

## 5. 키워드와 입찰가

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 광고그룹별·1개·ID별 키워드 보기 | 조회 | 없음 | 응답에 광고 연관 지수(adRelevanceScore)·클릭 기대 지수(expectedClickScore) 포함(2025-12-11) | [#57](03-endpoints.md#ep-057) [#51](03-endpoints.md#ep-051) [#55](03-endpoints.md#ep-055) |
| 키워드 등록 | 생성 | 있음 | 한 번에 최대 100개 | [#58](03-endpoints.md#ep-058) |
| **키워드 입찰가 바꾸기** | 변경 | **높음** | `fields=bidAmt`(bidAmt·useGroupBidAmt 필요). 여러 개는 최대 200개 | [#53](03-endpoints.md#ep-053) [#54](03-endpoints.md#ep-054) |
| **키워드 켜기/끄기** | 변경 | **높음** | `fields=userLock` | [#53](03-endpoints.md#ep-053) [#54](03-endpoints.md#ep-054) |
| 키워드별 연결 URL | 변경 | 없음 | `fields=links` | [#53](03-endpoints.md#ep-053) |
| 반려 키워드 재검수 요청 | 변경 | 간접 | `fields=inspect` | [#53](03-endpoints.md#ep-053) |
| 키워드 삭제(1개·여러 개) | 삭제 | 있음 | | [#52](03-endpoints.md#ep-052) [#56](03-endpoints.md#ep-056) |
| 키워드 속성(관리 키워드 여부 등) 보기 | 조회 | 없음 | | [#63](03-endpoints.md#ep-063) [#64](03-endpoints.md#ep-064) |

- **API로 할 수 없는 것**: "지금 내 광고가 몇 위인지"(실시간 순위). 공식 API에 없다. 평균 노출 순위는 성과 통계(`avgRnk`, `pcNxAvgRnk`, `mblNxAvgRnk`)로만 본다.
- **자동입찰(파워링크)**: 키워드 순위 맞춤 자동입찰 기능은 API에 없다. `systemBiddingType`(NONE, ML)은 광고그룹 속성으로만 있다. 쇼핑 자동입찰 MAXCONV는 2025-09-10 종료.

## 6. 광고 소재와 확장소재

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 광고그룹별·1개·ID별 소재 보기 | 조회 | 없음 | | [#27](03-endpoints.md#ep-027) [#22](03-endpoints.md#ep-022) [#26](03-endpoints.md#ep-026) |
| 소재 등록 | 생성 | 있음 | 유형: TEXT_45, RSA_AD(반응형, 2024-03-20), SHOPPING_PRODUCT_AD, LOCAL_AD 등. **MEDICAL_AD(병의원)는 API 등록 불가**(2025-05-14) | [#21](03-endpoints.md#ep-021) |
| **소재 켜기/끄기** | 변경 | **높음** | `fields=userLock` | [#24](03-endpoints.md#ep-024) |
| 반려 소재 재검수 요청 | 변경 | 간접 | `fields=inspect` | [#24](03-endpoints.md#ep-024) |
| 소재를 다른 광고그룹으로 복사 | 생성 | 있음 | 복사본 ON/OFF 지정 | [#25](03-endpoints.md#ep-025) |
| 소재 삭제 | 삭제 | 있음 | | [#23](03-endpoints.md#ep-023) |
| 확장소재 보기(그룹별·1개·ID별·즐겨찾기별) | 조회 | 없음 | | [#8](03-endpoints.md#ep-008) [#2](03-endpoints.md#ep-002) [#6](03-endpoints.md#ep-006) [#7](03-endpoints.md#ep-007) |
| 확장소재 등록 | 생성 | 있음 | 유형별 조건은 [04-features.md](04-features.md#2-확장소재-유형별-조건) | [#1](03-endpoints.md#ep-001) |
| 확장소재 켜기/끄기·노출 기간 | 변경 | 있음 | `fields=userLock/period`(여러 개는 inspect도) | [#4](03-endpoints.md#ep-004) [#5](03-endpoints.md#ep-005) |
| 확장소재 삭제 | 삭제 | 있음 | | [#3](03-endpoints.md#ep-003) |
| 검수 결과·반려 사유 보기 | 조회 | 없음 | 비즈채널·소재·확장소재·키워드·애셋, 최근 3개월, 최대 100건(2025-12-03) | [#126](03-endpoints.md#ep-126) [#127](03-endpoints.md#ep-127) |

- **문구 수정은 없다**: 소재 변경 API의 fields 허용값은 `userLock`, `inspect`뿐이다. 문구를 바꾸려면 새로 등록 → 검수 통과 → 예전 것 끄기·삭제.
  확장소재 변경도 공식 설명상 `userLock`, `period`(여러 개는 `inspect`)만 언급된다. fields 없이 전체 변경 시 내용까지 바뀌는지는 **미확인**.

## 7. 쇼핑 상품소재

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 쇼핑 상품소재 등록 | 생성 | 있음 | 소재 유형 SHOPPING_PRODUCT_AD, 쇼핑몰(MALL) 비즈채널 검수 통과 필요. 상품 식별자 형식은 [04](04-features.md#4-쇼핑검색) | [#21](03-endpoints.md#ep-021) |
| 상품소재별 입찰가 | 변경 | **높음** | 소재 모델의 `adAttr`("쇼핑 광고면 필수"). 하지만 소재 변경의 fields 허용값에 adAttr가 없다 → [04](04-features.md#4-쇼핑검색) | [#24](03-endpoints.md#ep-024) |
| 상품 그룹 목록 보기 | 조회 | 없음 | | [#65](03-endpoints.md#ep-065) |
| 카탈로그 소재 태그(AD_TAG) | 변경 | 있음 | 쇼핑 카탈로그 소재만, 태그 3~10자, 최대 30개 | [#75](03-endpoints.md#ep-075) |
| 쇼핑 입찰가 예측 | 조회 | 없음 | | [#121](03-endpoints.md#ep-121) [#122](03-endpoints.md#ep-122) |
| 쇼핑 전환목표 자동입찰 | 변경 | **높음** | 4장 참고 | [#12](03-endpoints.md#ep-012) |

## 8. 플레이스

자세한 조건은 [04-features.md](04-features.md#3-플레이스).

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 플레이스 광고에 쓸 업체(비즈채널) 보기 | 조회 | 없음 | `channelTp=PLACE` / purchasable-place-channels | [#44](03-endpoints.md#ep-044) [#66](03-endpoints.md#ep-066) |
| 플레이스 캠페인·광고그룹 만들기 | 생성 | 있음 | campaignTp=PLACE → adgroupType=LOCAL_AD(플레이스 검색) 또는 PLACE(지역소상공인) | [#30](03-endpoints.md#ep-030) [#9](03-endpoints.md#ep-009) |
| 플레이스 소재 등록 | 생성 | 있음 | 소재 유형 LOCAL_AD / PLACE_AD | [#21](03-endpoints.md#ep-021) |
| 입찰가·하루예산·ON/OFF | 변경 | **높음** | 캠페인·광고그룹과 같은 API | [#34](03-endpoints.md#ep-034) [#17](03-endpoints.md#ep-017) |
| 매체 타기팅(검색·콘텐츠 / 네이버·파트너) | 변경 | 있음 | 플레이스 검색 그룹(2024-11-13) | [#75](03-endpoints.md#ep-075) |
| **ADVoost 플레이스 켜기/끄기** | 변경 | **높음** | 업체 이미지 1개 이상, 병의원 불가 | [#12](03-endpoints.md#ep-012) [#17](03-endpoints.md#ep-017) |
| 제외검색어 | 생성·삭제 | 있음 | ADVoost 켜진 그룹은 등록 불가 | [#14](03-endpoints.md#ep-014) |

- **검색광고 API로 할 수 없는 것 — 스마트플레이스 업체 정보 자체**: 업체 이름·주소·영업시간·사진·메뉴·리뷰 관리는 스마트플레이스(네이버 별도 서비스) 영역이다. 검색광고 API 명세에 이런 엔드포인트는 **없다**. 검색광고 API는 이미 등록된 업체를 "플레이스 비즈채널"로 보고 광고에 연결할 뿐이다. ADVoost 플레이스 소재도 스마트플레이스에 올린 업체 정보·이미지를 그대로 가져다 쓴다(릴리스 노트 2026-09-16).

## 9. 타기팅과 제외 설정

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 타기팅 코드표 보기(요일·시간·지역·연령·성별·기기 등) | 조회 | 없음 | 반경(PROXIMITY)은 조회 불가 | [#47](03-endpoints.md#ep-047) |
| 광고그룹 타기팅 보기 | 조회 | 없음 | 유형: SD(요일·시간), RL(지역), RP(반경), DV(기기), AG(연령), GN(성별), AD(오디언스), CA | [#50](03-endpoints.md#ep-050) |
| 광고그룹 타기팅 바꾸기(유형별) | 변경 | 있음 | **본문에 없는 코드는 모두 꺼진다** | [#49](03-endpoints.md#ep-049) |
| 타기팅별 입찰 가중치 | 변경 | **높음** | 가중치가 오르면 실제 입찰가가 오름 | [#48](03-endpoints.md#ep-048) |
| 타깃(매체·지역·시간·PC/모바일·성별·연령·기간·태그) 보기·바꾸기 | 조회·변경 | 있음 | targetTp 12종 | [#76](03-endpoints.md#ep-076) [#77](03-endpoints.md#ep-077) [#75](03-endpoints.md#ep-075) |
| 제외검색어 보기·등록·삭제 | 조회·생성·삭제 | 있음 | 파워링크(website) 그룹만. type: KEYWORD_PLUS_RESTRICT, EXP_SEARCH(2024-10-02) | [#15](03-endpoints.md#ep-015) [#14](03-endpoints.md#ep-014) [#16](03-endpoints.md#ep-016) |
| 노출 제한 IP 보기·등록·변경·삭제 | 전부 | 있음 | 부정 클릭 방지, 설명 25자 이내 | [#89](03-endpoints.md#ep-089)~[#93](03-endpoints.md#ep-093) [#88](03-endpoints.md#ep-088) |

- 타기팅을 바꾸는 길이 세 가지(광고그룹 fields, criterion, targets)다. 2022-04-27 타기팅 관리 방식 변경 이후 어느 쪽이 권장인지 명세만으로는 **미확인**.

## 10. 예산과 광고비

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 비즈머니(충전금) 잔액·잠금 상태 보기 | 조회 | 없음 | | [#94](03-endpoints.md#ep-094) |
| 비즈머니 충전·차감·일별 내역 보기 | 조회 | 없음 | 기간 지정 | [#95](03-endpoints.md#ep-095) [#96](03-endpoints.md#ep-096) [#97](03-endpoints.md#ep-097) |
| 공유예산 보기 | 조회 | 없음 | | [#67](03-endpoints.md#ep-067) [#71](03-endpoints.md#ep-071) [#31](03-endpoints.md#ep-031) [#10](03-endpoints.md#ep-010) |
| **공유예산 만들기·바꾸기·하루예산 바꾸기** | 생성·변경 | **높음** | | [#68](03-endpoints.md#ep-068) [#72](03-endpoints.md#ep-072) [#73](03-endpoints.md#ep-073) |
| 공유예산에서 캠페인·광고그룹 빼기, 공유예산 삭제 | 변경·삭제 | 있음 | 삭제의 공식 설명은 '하루예산 수정'으로 잘못 복사돼 있음 | [#69](03-endpoints.md#ep-069) [#70](03-endpoints.md#ep-070) [#74](03-endpoints.md#ep-074) |
| 세금계산서 발행처 위임 일자 보기 | 조회 | 없음 | | [#83](03-endpoints.md#ep-083) |

- **API로 할 수 없는 것**: 비즈머니 충전·환불. **폐기**: 비즈머니 사용 조회(`/billing/bizmoney/cost`) 2025-08-06 종료.
- 캠페인·광고그룹 하루예산은 3·4장.

## 11. 성과·통계·보고서

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 캠페인·광고그룹·키워드·소재 성과 보기 | 조회 | 없음 | 노출·클릭·비용·CTR·CPC·평균순위·전환·전환매출·ROAS·구매완료 전환(2026-03-30)·구매완료 ROAS(2026-05-13). 약 2시간 지연, 최대 48시간 안에 바뀔 수 있음 | [#107](03-endpoints.md#ep-107) [#108](03-endpoints.md#ep-108) [#109](03-endpoints.md#ep-109) |
| 대용량 보고서(하루 단위 TSV) 요청·조회·삭제 | 생성·조회·삭제 | 없음 | 13종(AD, AD_DETAIL, 전환, 확장소재, 검색어, 쇼핑 검색어, 쇼핑 브랜드, 타기팅). 보관 14일(2025-10-27) | [#102](03-endpoints.md#ep-102)~[#106](03-endpoints.md#ep-106) |
| 마스터 보고서(전체 광고 구조 파일) 요청·조회·삭제 | 생성·조회·삭제 | 없음 | 30종(item). 최근 100개까지 | [#110](03-endpoints.md#ep-110)~[#114](03-endpoints.md#ep-114) |
| 네이버 애널리틱스 신청·해지·현황 | 생성·변경·조회 | 없음 | 전환 추적 연동용 | [#80](03-endpoints.md#ep-080) [#81](03-endpoints.md#ep-081) [#82](03-endpoints.md#ep-082) |

- **폐기·변경**: 네이버페이 전환 보고서 2025-05-09 종료, 계정 마스터 보고서 2025-09-15 종료, 품질지수(Qi) 파워링크 2026-07-29·쇼핑 상품형/카탈로그 2026-11-25부터 고정값 4, 쇼핑 브랜드 검색상단노출률 2026-09-30부터 0, 최근 평균 순위·CPC(recentAvgRnk·recentAvgCpc)는 0 반환(2025-10-27), 확장소재 보고서 8번 열 2026-11-16 삭제.

## 12. 키워드 아이디어·입찰가 예측 도구

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 연관 키워드와 월간 검색수 보기 | 조회 | 없음 | 힌트 키워드·사이트·업종·시즌·이벤트 중 하나 이상. **호출 제한이 다른 기능의 1/5~1/6** | [#115](03-endpoints.md#ep-115) |
| 순위별 평균 입찰가(파워링크) | 조회 | 없음 | PC 순위는 1~10만(2025-05-13) | [#116](03-endpoints.md#ep-116) |
| 중간 입찰가·최소 노출 입찰가(파워링크) | 조회 | 없음 | | [#117](03-endpoints.md#ep-117) [#118](03-endpoints.md#ep-118) |
| 입찰가별 예상 노출·클릭·비용(파워링크) | 조회 | 없음 | 1개·여러 키워드 | [#119](03-endpoints.md#ep-119) [#120](03-endpoints.md#ep-120) |
| 쇼핑·파워콘텐츠 입찰가·성과 예측 | 조회 | 없음 | | [#121](03-endpoints.md#ep-121)~[#125](03-endpoints.md#ep-125) |

## 13. 자동화 (ADVoost 등)

| 기능 | 대상 | 설정 방법 | 영향 | 근거 |
|---|---|---|---|---|
| ADVoost Max | 파워링크 + 확장검색 광고그룹 | `aiAdsOptIn` (미지정 시 **true**) | **높음** | 릴리스 노트 2026-07-15, 명세 반영 |
| ADVoost 플레이스 | 플레이스 LOCAL_AD 광고그룹 | `adgroupAttrJson.useAdvoost` (미지정 시 false) | **높음** — 입찰가 등 고급옵션 변경 불가 | 릴리스 노트 2026-09-16, **명세 JSON 미반영** |
| 쇼핑 전환목표 자동입찰(Beta) | 쇼핑몰 상품형 광고그룹(전환 로그 수집 중) | `autobidStrategy` (목표 MAX_CONV_VALUE) | **높음** — 하루예산 안에서 입찰가·소재 노출을 네이버가 관리 | 릴리스 노트 2025-10-15 |
| 확장검색 | 파워링크 광고그룹 | `useExpSearch` | 있음 — 등록 안 한 검색어에도 노출 | 릴리스 노트 2024-09-13 |
| 시스템 입찰(systemBiddingType) | 광고그룹 | NONE / ML | 미확인 | 명세 필드만 있음, 설명 없음 |

- 2026-06-30 공지: "파워링크에 애드부스트 검색 기술이 전체 검색어로 적용"되어 품질지수가 종료됨. 즉 ADVoost는 광고그룹 설정과 별개로 노출 방식에도 쓰인다.

## 14. 그 밖의 기능

| 할 수 있는 일 | 구분 | 영향 | 제한·조건 | 엔드포인트 |
|---|---|---|---|---|
| 즐겨찾기(라벨) 보기·이름 바꾸기·넣고 빼기 | 조회·변경 | 없음 | | [#61](03-endpoints.md#ep-061) [#62](03-endpoints.md#ep-062) [#60](03-endpoints.md#ep-060) [#7](03-endpoints.md#ep-007) [#20](03-endpoints.md#ep-020) [#59](03-endpoints.md#ep-059) |
| 브랜드검색·신제품검색 계약 보기 | 조회 | 없음 | 2025-10-01 추가. 계약 체결·변경은 API에 없음 | [#78](03-endpoints.md#ep-078) [#79](03-endpoints.md#ep-079) [#28](03-endpoints.md#ep-028) [#29](03-endpoints.md#ep-029) |
| 심사용 서류 보기·등록·파일 업로드 | 조회·생성 | 간접 | | [#85](03-endpoints.md#ep-085) [#86](03-endpoints.md#ep-086) [#87](03-endpoints.md#ep-087) |
| 내 접속 IP 보기 | 조회 | 없음 | 명세에서 `#hidden` | [#84](03-endpoints.md#ep-084) |

# 엔드포인트별 상세 명세

> 이 파일은 공식 명세 JSON에서 자동으로 만들었다(작업명·쉬운 설명·구분·영향은 사람이 붙임). 다시 만드는 방법은 [README](README.md#다시-만들기).
> 경로는 공식 문서·실제 호출 기준(`/api` 접두어 없음). 모든 요청에 [공통 인증 헤더](02-auth-common.md)가 필요하다.
> 필수: ✔ = 명세 required, 생성/수정 = 모델 설명의 `#required-create`/`#required-update` 태그(조건부 필수).

## 목차

- **광고 관리(NCC)** (`ncc-heroes-ncc.json`)
  - [1. 확장소재 등록 — `POST /ncc/ad-extensions`](#ep-001)
  - [2. 확장소재 1개 조회 — `GET /ncc/ad-extensions/{adExtensionId}`](#ep-002)
  - [3. 확장소재 1개 삭제 — `DELETE /ncc/ad-extensions/{adExtensionId}`](#ep-003)
  - [4. 확장소재 1개 변경 — `PUT /ncc/ad-extensions/{adExtensionId}{?fields}`](#ep-004)
  - [5. 확장소재 여러 개 변경 — `PUT /ncc/ad-extensions{?fields}`](#ep-005)
  - [6. 확장소재 ID로 여러 개 조회 — `GET /ncc/ad-extensions{?ids}`](#ep-006)
  - [7. 즐겨찾기별 확장소재 조회 — `GET /ncc/ad-extensions{?nccLabelId}`](#ep-007)
  - [8. 광고그룹·캠페인별 확장소재 조회 — `GET /ncc/ad-extensions{?ownerId}`](#ep-008)
  - [9. 광고그룹 생성 — `POST /ncc/adgroups`](#ep-009)
  - [10. 공유예산에 묶인 광고그룹 조회 — `GET /ncc/adgroups/shared-budgets/{sharedBudgetId}`](#ep-010)
  - [11. 광고그룹 1개 조회 — `GET /ncc/adgroups/{adgroupId}`](#ep-011)
  - [12. 광고그룹 전체 변경 — `PUT /ncc/adgroups/{adgroupId}`](#ep-012)
  - [13. 광고그룹 삭제 — `DELETE /ncc/adgroups/{adgroupId}`](#ep-013)
  - [14. 제외검색어 등록 — `POST /ncc/adgroups/{adgroupId}/restricted-keywords`](#ep-014)
  - [15. 제외검색어 조회 — `GET /ncc/adgroups/{adgroupId}/restricted-keywords?type=KEYWORD_PLUS_RESTRICT`](#ep-015)
  - [16. 제외검색어 삭제 — `DELETE /ncc/adgroups/{adgroupId}/restricted-keywords{?ids}`](#ep-016)
  - [17. 광고그룹 일부 변경 — `PUT /ncc/adgroups/{adgroupId}{?fields}`](#ep-017)
  - [18. 광고그룹 ID로 여러 개 조회 — `GET /ncc/adgroups{?ids}`](#ep-018)
  - [19. 캠페인별 광고그룹 목록 — `GET /ncc/adgroups{?nccCampaignId,baseSearchId,recordSize,selector}`](#ep-019)
  - [20. 즐겨찾기별 광고그룹 조회 — `GET /ncc/adgroups{?nccLabelId}`](#ep-020)
  - [21. 소재 등록 — `POST /ncc/ads`](#ep-021)
  - [22. 소재 1개 조회 — `GET /ncc/ads/{adId}`](#ep-022)
  - [23. 소재 삭제 — `DELETE /ncc/ads/{adId}`](#ep-023)
  - [24. 소재 변경 — `PUT /ncc/ads/{adId}{?fields}`](#ep-024)
  - [25. 소재 복사 — `PUT /ncc/ads{?ids,targetAdgroupId,userLock}`](#ep-025)
  - [26. 소재 ID로 여러 개 조회 — `GET /ncc/ads{?ids}`](#ep-026)
  - [27. 광고그룹별 소재 목록 — `GET /ncc/ads{?nccAdgroupId}`](#ep-027)
  - [28. 신제품검색 계약 전체 조회 — `GET /ncc/brand-new/contracts`](#ep-028)
  - [29. 광고그룹별 신제품검색 계약 조회 — `GET /ncc/brand-new/contracts{?adgroupId}`](#ep-029)
  - [30. 캠페인 생성 — `POST /ncc/campaigns`](#ep-030)
  - [31. 공유예산에 묶인 캠페인 조회 — `GET /ncc/campaigns/shared-budgets/{sharedBudgetId}`](#ep-031)
  - [32. 캠페인 1개 조회 — `GET /ncc/campaigns/{campaignId}`](#ep-032)
  - [33. 캠페인 삭제 — `DELETE /ncc/campaigns/{campaignId}`](#ep-033)
  - [34. 캠페인 변경 — `PUT /ncc/campaigns/{campaignId}{?fields}`](#ep-034)
  - [35. 캠페인 목록 — `GET /ncc/campaigns{?campaignType,baseSearchId,recordSize,selector}`](#ep-035)
  - [36. 캠페인 ID로 여러 개 조회 — `GET /ncc/campaigns{?ids}`](#ep-036)
  - [37. 캠페인 여러 개 삭제 — `DELETE /ncc/campaigns{?ids}`](#ep-037)
  - [38. 비즈채널 목록 — `GET /ncc/channels`](#ep-038)
  - [39. 비즈채널 등록 — `POST /ncc/channels`](#ep-039)
  - [40. 비즈채널 1개 조회 — `GET /ncc/channels/{businessChannelId}`](#ep-040)
  - [41. 비즈채널 삭제 — `DELETE /ncc/channels/{businessChannelId}`](#ep-041)
  - [42. 비즈채널 재검수 요청 — `PUT /ncc/channels/{businessChannelId}/inspect`](#ep-042)
  - [43. 비즈채널 변경 — `PUT /ncc/channels/{businessChannelId}{?fields}`](#ep-043)
  - [44. 유형별 비즈채널 목록 — `GET /ncc/channels{?channelTp}`](#ep-044)
  - [45. 비즈채널 ID로 여러 개 조회 — `GET /ncc/channels{?ids}`](#ep-045)
  - [46. 비즈채널 여러 개 삭제 — `DELETE /ncc/channels{?ids}`](#ep-046)
  - [47. 타기팅 코드표 조회 — `GET /ncc/criterion-dictionary/{type}`](#ep-047)
  - [48. 타기팅 입찰 가중치 변경 — `PUT /ncc/criterion/{ownerId}/bidWeight{?codes,bidWeight}`](#ep-048)
  - [49. 타기팅 설정 변경 — `PUT /ncc/criterion/{ownerId}/{type}`](#ep-049)
  - [50. 타기팅 설정 조회 — `GET /ncc/criterion/{ownerId}{?type}`](#ep-050)
  - [51. 키워드 1개 조회 — `GET /ncc/keywords/{nccKeywordId}`](#ep-051)
  - [52. 키워드 1개 삭제 — `DELETE /ncc/keywords/{nccKeywordId}`](#ep-052)
  - [53. 키워드 1개 변경 — `PUT /ncc/keywords/{nccKeywordId}{?fields}`](#ep-053)
  - [54. 키워드 여러 개 변경 — `PUT /ncc/keywords{?fields}`](#ep-054)
  - [55. 키워드 ID로 여러 개 조회 — `GET /ncc/keywords{?ids}`](#ep-055)
  - [56. 키워드 여러 개 삭제 — `DELETE /ncc/keywords{?ids}`](#ep-056)
  - [57. 광고그룹별 키워드 목록 — `GET /ncc/keywords{?nccAdgroupId,baseSearchId,recordSize,selector}`](#ep-057)
  - [58. 키워드 등록 — `POST /ncc/keywords{?nccAdgroupId}`](#ep-058)
  - [59. 즐겨찾기별 키워드 조회 — `GET /ncc/keywords{?nccLabelId}`](#ep-059)
  - [60. 즐겨찾기에 넣기·빼기 — `PUT /ncc/label-refs`](#ep-060)
  - [61. 즐겨찾기 목록 — `GET /ncc/labels`](#ep-061)
  - [62. 즐겨찾기 이름 변경 — `PUT /ncc/labels`](#ep-062)
  - [63. 키워드 정보 조회(본문 방식) — `POST /ncc/managedKeyword`](#ep-063)
  - [64. 키워드 정보 조회 — `GET /ncc/managedKeyword{?keywords}`](#ep-064)
  - [65. 상품 그룹 목록 — `GET /ncc/product-groups`](#ep-065)
  - [66. 광고 가능한 플레이스 채널 조회 — `GET /ncc/purchasable-place-channels{?type}`](#ep-066)
  - [67. 공유예산 목록 — `GET /ncc/shared-budgets`](#ep-067)
  - [68. 공유예산 만들기 — `POST /ncc/shared-budgets`](#ep-068)
  - [69. 공유예산에서 광고그룹 빼기 — `PUT /ncc/shared-budgets/adgroups{?ids}`](#ep-069)
  - [70. 공유예산에서 캠페인 빼기 — `PUT /ncc/shared-budgets/campaigns{?ids}`](#ep-070)
  - [71. 공유예산 1개 조회 — `GET /ncc/shared-budgets/{sharedBudgetId}`](#ep-071)
  - [72. 공유예산 변경 — `PUT /ncc/shared-budgets/{sharedBudgetId}`](#ep-072)
  - [73. 공유예산 하루예산 변경 — `PUT /ncc/shared-budgets{?fields}`](#ep-073)
  - [74. 공유예산 삭제 — `DELETE /ncc/shared-budgets{?ids}`](#ep-074)
  - [75. 타깃 변경 — `PUT /ncc/targets/{targetId}`](#ep-075)
  - [76. 타깃 조회 — `GET /ncc/targets{?ownerId,types}`](#ep-076)
  - [77. 타깃 여러 개 조회 — `GET /ncc/targets{?ownerIds}`](#ep-077)
  - [78. 브랜드검색 계약 전체 조회 — `GET /ncc/time-contracts`](#ep-078)
  - [79. 광고그룹별 브랜드검색 계약 조회 — `GET /ncc/time-contracts{?adgroupId}`](#ep-079)
- **도구(Tool)** (`ncc-heroes-tool.json`)
  - [80. 애널리틱스 신청 — `POST /tool/analyticses{?field}`](#ep-080)
  - [81. 애널리틱스 해지·변경 — `PUT /tool/analyticses{?modifyType}`](#ep-081)
  - [82. 애널리틱스 현황 조회 — `GET /tool/analyticses{?searchType}`](#ep-082)
  - [83. 세금계산서 발행처 위임 일자 조회 — `GET /tool/bill-recipient-histories/latest`](#ep-083)
  - [84. 내 접속 IP 조회 — `GET /tool/client-ip`](#ep-084)
  - [85. 서류 관리 현황 조회 — `GET /tool/document`](#ep-085)
  - [86. 서류 내용 등록 — `POST /tool/document`](#ep-086)
  - [87. 서류 파일 업로드 — `POST /tool/file/upload{?data}`](#ep-087)
  - [88. 노출 제한 IP 변경 이력 — `GET /tool/ip-exclusion-histories{?page,rpp,searchStartDate,searchEndDate}`](#ep-088)
  - [89. 노출 제한 IP 목록 — `GET /tool/ip-exclusions`](#ep-089)
  - [90. 노출 제한 IP 등록 — `POST /tool/ip-exclusions`](#ep-090)
  - [91. 노출 제한 IP 변경 — `PUT /tool/ip-exclusions`](#ep-091)
  - [92. 노출 제한 IP 1개 삭제 — `DELETE /tool/ip-exclusions/{id}`](#ep-092)
  - [93. 노출 제한 IP 여러 개 삭제 — `DELETE /tool/ip-exclusions{?ids}`](#ep-093)
- **비즈머니(Billing)** (`ncc-heroes-billing.json`)
  - [94. 비즈머니 잔액 조회 — `GET /billing/bizmoney`](#ep-094)
  - [95. 비즈머니 충전 내역 — `GET /billing/bizmoney/histories/charge{?searchStartDt,searchEndDt}`](#ep-095)
  - [96. 비즈머니 차감 내역 — `GET /billing/bizmoney/histories/exhaust{?searchStartDt,searchEndDt}`](#ep-096)
  - [97. 일별 비즈머니 현황 — `GET /billing/bizmoney/histories/period{?searchStartDt,searchEndDt}`](#ep-097)
- **광고 계정·관리 계정(AdAccounts·ManagerAccounts)** (`atower.json`)
  - [98. 내 광고 계정 목록 — `GET /ad-accounts`](#ep-098)
  - [99. 광고 계정 구성원 조회 — `GET /ad-accounts/{adAccountNo}/members`](#ep-099)
  - [100. 내 관리 계정 목록 — `GET /manager-accounts`](#ep-100)
  - [101. 관리 계정의 하위 광고 계정 — `GET /manager-accounts/{managerAccountNo}/child-ad-accounts`](#ep-101)
- **통계·대용량 보고서(Stat·StatReport)** (`ncc-report.json`)
  - [102. 대용량 보고서 작업 목록 — `GET /stat-reports`](#ep-102)
  - [103. 대용량 보고서 요청 — `POST /stat-reports`](#ep-103)
  - [104. 대용량 보고서 전체 삭제 — `DELETE /stat-reports`](#ep-104)
  - [105. 대용량 보고서 1개 조회 — `GET /stat-reports/{reportJobId}`](#ep-105)
  - [106. 대용량 보고서 1개 삭제 — `DELETE /stat-reports/{reportJobId}`](#ep-106)
  - [107. 성과 요약(1개 대상) — `GET /stats{?id,fields,timeRange,datePreset,timeIncrement,breakdown}`](#ep-107)
  - [108. 성과 요약(여러 대상) — `GET /stats{?ids,fields,timeRange,datePreset,timeIncrement,breakdown}`](#ep-108)
  - [109. 유형별 성과(1개 대상) — `GET /stats{?id,statType}`](#ep-109)
- **마스터 보고서(MasterReport)** (`master-report.json`)
  - [110. 마스터 보고서 작업 목록 — `GET /master-reports`](#ep-110)
  - [111. 마스터 보고서 전체 삭제 — `DELETE /master-reports`](#ep-111)
  - [112. 마스터 보고서 요청 — `POST /master-reports`](#ep-112)
  - [113. 마스터 보고서 1개 삭제 — `DELETE /master-reports/{id}`](#ep-113)
  - [114. 마스터 보고서 1개 조회 — `GET /master-reports/{id}`](#ep-114)
- **키워드 도구(RelKwdStat)** (`ncc-keywordstool.json`)
  - [115. 연관 키워드·검색량 조회 — `GET /keywordstool`](#ep-115)
- **입찰가·성과 예측(Estimate)** (`estimate.json`)
  - [116. 순위별 평균 입찰가 예측(파워링크) — `POST /estimate/average-position-bid/{type}`](#ep-116)
  - [117. 중간 입찰가 예측(파워링크) — `POST /estimate/median-bid/{type}`](#ep-117)
  - [118. 최소 노출 입찰가 예측(파워링크) — `POST /estimate/exposure-minimum-bid/{type}`](#ep-118)
  - [119. 입찰가별 성과 예측(파워링크) — `POST /estimate/performance/{type}`](#ep-119)
  - [120. 입찰가별 성과 예측(여러 키워드) — `POST /estimate/performance-bulk`](#ep-120)
  - [121. 순위별 평균 입찰가 예측(쇼핑) — `POST /npla-estimate/average-position-bid/{type}`](#ep-121)
  - [122. 최소 노출 입찰가 예측(쇼핑) — `POST /npla-estimate/exposure-minimum-bid/{type}`](#ep-122)
  - [123. 순위별 평균 입찰가 예측(파워콘텐츠) — `POST /npc-estimate/average-position-bid/{type}`](#ep-123)
  - [124. 최소 노출 입찰가 예측(파워콘텐츠) — `POST /npc-estimate/exposure-minimum-bid/{type}`](#ep-124)
  - [125. 성과 예측(파워콘텐츠) — `POST /npc-estimate/performance`](#ep-125)
- **검수 이력(InspectHistory)** (`ncc-inspect-history.json`)
  - [126. 검수 이력 여러 개 조회 — `POST /ncc/inspect-history`](#ep-126)
  - [127. 검수 이력 1개 조회 — `GET /ncc/inspect-history/{id}`](#ep-127)

## 광고 관리(NCC)
원본: `assets/json/ncc-heroes-ncc.json`

<a id="ep-001"></a>
### 1. 확장소재 등록

`POST /ncc/ad-extensions`

- **쉬운 설명**: 광고그룹·캠페인에 추가제목·홍보문구·서브링크·이미지 같은 확장소재를 새로 붙인다
- **구분**: 생성 · **광고비·노출 영향**: 있음 — 검수 통과·ON이면 광고 모양이 바뀌고 클릭이 늘 수 있음
- **공식 설명**: 새로운 확장 소재를 생성합니다. ownerId는 확장 소재가 소속될 광고 객체(캠페인, 광고그룹)입니다. Registers a new AD extension to the specified campaign, adgroup or ad
- **공식 요약(summary)**: create · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fad-extensions>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adExtensionRequest` | 본문 | ✔ | [AdExtensionRequest](06-models.md#model-adextensionrequest) |  | adExtensionRequest |

본문 모델 `AdExtensionRequest`의 필수 필드: 명세 required = enable; 생성 시 = mobileChannelId, ownerId, pcChannelId, schedule, type, userLock; 수정 시 = nccAdExtensionId

**응답**: [AdExtension](06-models.md#model-adextension) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/ad-extensions
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "mobileChannelId": "<mobileChannelId>",
  "ownerId": "<ownerId>",
  "pcChannelId": "<pcChannelId>",
  "schedule": {},
  "type": "PHONE",
  "userLock": false
}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-002"></a>
### 2. 확장소재 1개 조회

`GET /ncc/ad-extensions/{adExtensionId}`

- **쉬운 설명**: 확장소재 하나의 내용·상태·검수 결과를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 특정 확장 소재(adExtensionId)의 정보를 조회합니다. Retrieves information on an AD extension
- **공식 요약(summary)**: get · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fad-extensions~2F%7BadExtensionId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adExtensionId` | 경로 | ✔ | string |  | adExtensionId |

**응답**: [AdExtension](06-models.md#model-adextension) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ad-extensions/<adExtensionId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-003"></a>
### 3. 확장소재 1개 삭제

`DELETE /ncc/ad-extensions/{adExtensionId}`

- **쉬운 설명**: 확장소재 하나를 지운다(되돌릴 수 없음)
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 노출되던 확장소재가 사라짐
- **공식 설명**: 확장 소재를 삭제합니다. Deletes a registered AD extension
- **공식 요약(summary)**: delete · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fad-extensions~2F%7BadExtensionId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adExtensionId` | 경로 |  | string |  | The unique ID of the AD extension |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/ad-extensions/<adExtensionId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-004"></a>
### 4. 확장소재 1개 변경

`PUT /ncc/ad-extensions/{adExtensionId}{?fields}`

- **쉬운 설명**: 확장소재 하나의 ON/OFF·노출 기간을 바꾼다(fields 없으면 전체 변경)
- **구분**: 변경 · **광고비·노출 영향**: 있음 — ON/OFF·기간에 따라 노출이 바뀜
- **공식 설명**: 특정 확장 소재의 정보를 변경합니다. field 파라미터가 없을 경우 확장 소재 정보 전체를 변경합니다. field 파라미터가 있을 경우 확장 소재의 특정 정보만 변경합니다. Change an AD extension The parameter field, you can enter one of the following: 'userLock', 'period'
- **공식 요약(summary)**: update · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fad-extensions~2F%7BadExtensionId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adExtensionId` | 경로 | ✔ | string |  | adExtensionId |
| `fields` | 쿼리 |  | string 배열 |  | fields |
| `adExtensionRequest` | 본문 | ✔ | [AdExtensionRequest](06-models.md#model-adextensionrequest) |  | adExtensionRequest |

본문 모델 `AdExtensionRequest`의 필수 필드: 명세 required = enable; 생성 시 = mobileChannelId, ownerId, pcChannelId, schedule, type, userLock; 수정 시 = nccAdExtensionId

**응답**: [AdExtension](06-models.md#model-adextension) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/ad-extensions/<adExtensionId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "nccAdExtensionId": "<nccAdExtensionId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-005"></a>
### 5. 확장소재 여러 개 변경

`PUT /ncc/ad-extensions{?fields}`

- **쉬운 설명**: 여러 확장소재의 ON/OFF·검수 요청·노출 기간을 한 번에 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 있음 — ON/OFF·기간에 따라 노출이 바뀜
- **공식 설명**: 여러개의 확장 소재를 변경합니다. field 파라미터가 없을 경우 확장 소재 정보 전체를 변경합니다. field 파라미터가 있을 경우 확장 소재의 특정 정보만 변경합니다. 'userLock': On/Off 설정 변경 'period': 노출 기간 설정 Change multiple AD extensions The parameter field, you can enter one of the following: 'userLock', 'inspect', 'period'
- **공식 요약(summary)**: update items · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fad-extensions%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adExtensionRequestList` | 본문 | ✔ | [AdExtensionRequest[]](06-models.md#model-adextensionrequest) |  | adExtensionRequestList |
| `fields` | 쿼리 | ✔ | string |  | fields |

본문 모델 `AdExtensionRequest`의 필수 필드: 명세 required = enable; 생성 시 = mobileChannelId, ownerId, pcChannelId, schedule, type, userLock; 수정 시 = nccAdExtensionId

**응답**: [AdExtension[]](06-models.md#model-adextension) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/ad-extensions?fields=<fields>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {
    "nccAdExtensionId": "<nccAdExtensionId>"
  }
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-006"></a>
### 6. 확장소재 ID로 여러 개 조회

`GET /ncc/ad-extensions{?ids}`

- **쉬운 설명**: 확장소재 ID 목록으로 내용을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 다수의 확장 소재 ID를 이용하여 조회합니다. Retrieves information on multiple AD extensions
- **공식 요약(summary)**: list (by ids) · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fad-extensions%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids |

**응답**: [AdExtension[]](06-models.md#model-adextension) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ad-extensions?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-007"></a>
### 7. 즐겨찾기별 확장소재 조회

`GET /ncc/ad-extensions{?nccLabelId}`

- **쉬운 설명**: 즐겨찾기(라벨)에 넣어 둔 확장소재 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 특정 즐겨찾기(label id)로 등록한 확장소재 목록을 조회합니다. Returns the list of AD extensions of input label id.
- **공식 요약(summary)**: list (by label id) · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fad-extensions%7B%3FnccLabelId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccLabelId` | 쿼리 | ✔ | string |  | nccLabelId |

**응답**: [AdExtension[]](06-models.md#model-adextension) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ad-extensions?nccLabelId=<nccLabelId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-008"></a>
### 8. 광고그룹·캠페인별 확장소재 조회

`GET /ncc/ad-extensions{?ownerId}`

- **쉬운 설명**: 특정 캠페인·광고그룹(또는 소재)에 붙은 확장소재 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 확장 소재가 속한 특정 광고 객체(캠페인, 광고그룹, 소재)의 ID(ownerId)를 이용하여 조회합니다. Retrieves information on multiple AD extensions The ownerId value indicates either campaign id or adgroup id.
- **공식 요약(summary)**: list (by owner id) · 태그: AdExtension
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fad-extensions%7B%3FownerId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ownerId` | 쿼리 | ✔ | string |  | ownerId |

**응답**: [AdExtension[]](06-models.md#model-adextension) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ad-extensions?ownerId=<ownerId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-009"></a>
### 9. 광고그룹 생성

`POST /ncc/adgroups`

- **쉬운 설명**: 캠페인 안에 광고그룹을 새로 만든다(입찰가·하루예산·비즈채널·타기팅 등)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — ON으로 만들면 바로 노출·과금될 수 있음
- **공식 설명**: Create a new adgroup
- **공식 요약(summary)**: create · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fadgroups>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `group` | 본문 | ✔ | [AdgroupRequest](06-models.md#model-adgrouprequest) |  | group |

본문 모델 `AdgroupRequest`의 필수 필드: 생성 시 = customerId, mobileChannelId, name, nccCampaignId, pcChannelId; 수정 시 = bidAmt, contentsNetworkBidAmt, contentsNetworkBidWeight, dailyBudget, mobileNetworkBidWeight, nccAdgroupId, pcNetworkBidWeight, useCntsNetworkBidAmt, useCntsNetworkBidWeight, useDailyBudget, userLock

**응답**: [Adgroup](06-models.md#model-adgroup) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/adgroups
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "customerId": 0,
  "mobileChannelId": "<mobileChannelId>",
  "name": "<name>",
  "nccCampaignId": "<nccCampaignId>",
  "pcChannelId": "<pcChannelId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-010"></a>
### 10. 공유예산에 묶인 광고그룹 조회

`GET /ncc/adgroups/shared-budgets/{sharedBudgetId}`

- **쉬운 설명**: 공유예산 하나에 연결된 광고그룹 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공유예산에 연결된 광고그룹 리스트를 조회합니다. Returns a list of adgroups associated with shared budget.
- **공식 요약(summary)**: list (by sharedBudgetId) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups~2Fshared-budgets~2F%7BsharedBudgetId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `sharedBudgetId` | 경로 | ✔ | string |  | sharedBudgetId |

**응답**: [Adgroup[]](06-models.md#model-adgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups/shared-budgets/<sharedBudgetId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-011"></a>
### 11. 광고그룹 1개 조회

`GET /ncc/adgroups/{adgroupId}`

- **쉬운 설명**: 광고그룹 하나의 설정(입찰가·예산·상태·ADVoost 등)을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the adgroup of input ID
- **공식 요약(summary)**: get · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups~2F%7BadgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adgroupId` | 경로 |  | string |  | The unique ID of the adgroup. |

**응답**: [Adgroup](06-models.md#model-adgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups/<adgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-012"></a>
### 12. 광고그룹 전체 변경

`PUT /ncc/adgroups/{adgroupId}`

- **쉬운 설명**: 광고그룹 설정 전체를 보낸 값으로 바꾼다(ADVoost Max·플레이스 ADVoost 포함)
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 입찰가·예산·ON/OFF·자동화 설정이 한꺼번에 바뀔 수 있음
- **공식 설명**: Change the Ad Group
- **공식 요약(summary)**: update · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fadgroups~2F%7BadgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `group` | 본문 | ✔ | [AdgroupRequest](06-models.md#model-adgrouprequest) |  | group |
| `adgroupId` | 경로 | ✔ | string |  | The unique ID of the Ad Group. |

본문 모델 `AdgroupRequest`의 필수 필드: 생성 시 = customerId, mobileChannelId, name, nccCampaignId, pcChannelId; 수정 시 = bidAmt, contentsNetworkBidAmt, contentsNetworkBidWeight, dailyBudget, mobileNetworkBidWeight, nccAdgroupId, pcNetworkBidWeight, useCntsNetworkBidAmt, useCntsNetworkBidWeight, useDailyBudget, userLock

**응답**: [Adgroup](06-models.md#model-adgroup) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/adgroups/<adgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "bidAmt": 0,
  "contentsNetworkBidAmt": 0,
  "contentsNetworkBidWeight": 0,
  "dailyBudget": 0,
  "mobileNetworkBidWeight": 0,
  "nccAdgroupId": "<nccAdgroupId>",
  "pcNetworkBidWeight": 0,
  "useCntsNetworkBidAmt": false,
  "useCntsNetworkBidWeight": false,
  "useDailyBudget": false,
  "userLock": false
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-013"></a>
### 13. 광고그룹 삭제

`DELETE /ncc/adgroups/{adgroupId}`

- **쉬운 설명**: 광고그룹과 그 안의 키워드·소재를 지운다(되돌릴 수 없음)
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 그 그룹 광고가 전부 사라짐
- **공식 설명**: Remove a Ad Group
- **공식 요약(summary)**: delete · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fadgroups~2F%7BadgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adgroupId` | 경로 |  | string |  | The unique ID of the adgroup. |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/adgroups/<adgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-014"></a>
### 14. 제외검색어 등록

`POST /ncc/adgroups/{adgroupId}/restricted-keywords`

- **쉬운 설명**: 이 검색어로는 광고가 나오지 않게 막는다(파워링크 그룹만)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — 노출이 줄어듦(낭비 클릭 감소)
- **공식 설명**: Create impression-restricted keywords for the adgroup. This feature is only available for adgroups of website campaign types.
- **공식 요약(summary)**: create (negative search terms) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fadgroups~2F%7BadgroupId%7D~2Frestricted-keywords>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `restrictedKeywords` | 본문 | ✔ | [AdgroupRestrictKwd[]](06-models.md#model-adgrouprestrictkwd) |  | restrictedKeywords |
| `adgroupId` | 경로 | ✔ | string |  | The unique ID of the Ad Group. |

**응답**: [AdgroupRestrictKwd[]](06-models.md#model-adgrouprestrictkwd) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/adgroups/<adgroupId>/restricted-keywords
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-015"></a>
### 15. 제외검색어 조회

`GET /ncc/adgroups/{adgroupId}/restricted-keywords?type=KEYWORD_PLUS_RESTRICT`

- **쉬운 설명**: 광고그룹에 등록한 제외검색어 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns a list of impression-restricted keywords. This feature is only available for adgroups of website campaign types.
- **공식 요약(summary)**: list (negative search terms) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups~2F%7BadgroupId%7D~2Frestricted-keywords%3Ftype=KEYWORD_PLUS_RESTRICT>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 쿼리 |  | string | KEYWORD_PLUS_RESTRICT | Type of the restricted keyword. default value is 'KEYWORD_PLUS_RESTRICT'. Such type of the restricted keyword is applied to 'Smart Block' and 'Close Variant'. 제외 키워드의 type입니다. 기본값은 'KEYWORD_PLUS_RESTRICT' 입니다. 해당 type의 제외 키워드는 스마트블록 및 유사검색어에 적용됩니다. |
| `adgroupId` | 경로 | ✔ | string |  | The unique ID of the Ad Group. |

**응답**: [AdgroupRestrictKwd[]](06-models.md#model-adgrouprestrictkwd) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups/<adgroupId>/restricted-keywords?type=KEYWORD_PLUS_RESTRICT
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-016"></a>
### 16. 제외검색어 삭제

`DELETE /ncc/adgroups/{adgroupId}/restricted-keywords{?ids}`

- **쉬운 설명**: 제외검색어를 지워서 다시 그 검색어에 광고가 나올 수 있게 한다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 노출이 다시 늘 수 있음
- **공식 설명**: Remove impression-restricted keywords. This feature is only available for adgroups of website campaign types.
- **공식 요약(summary)**: delete (negative search terms) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fadgroups~2F%7BadgroupId%7D~2Frestricted-keywords%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adgroupId` | 경로 | ✔ | string |  | The unique ID of the Ad Group. |
| `ids` | 쿼리 | ✔ | string |  | IDs of the impression-restricted keywods |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/adgroups/<adgroupId>/restricted-keywords?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-017"></a>
### 17. 광고그룹 일부 변경

`PUT /ncc/adgroups/{adgroupId}{?fields}`

- **쉬운 설명**: 광고그룹의 입찰가·ON/OFF·하루예산·매체 가중치·지역·시간·매체·성별 중 하나만 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 입찰가·예산·ON/OFF가 바로 광고비에 반영
- **공식 설명**: Change the Ad Group. The parameter fields, enter the name of the Ad Group field you want to change.
- **공식 요약(summary)**: update (by fields) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fadgroups~2F%7BadgroupId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `group` | 본문 | ✔ | [AdgroupRequest](06-models.md#model-adgrouprequest) |  | group |
| `fields` | 쿼리 |  | string | bidAmt, userLock, budget, networkBidWeight, targetLocation, targetTime, targetMedia, targetGender | Field name of the Ad Group you want to modify |
| `adgroupId` | 경로 | ✔ | string |  | The unique ID of the Ad Group. |

본문 모델 `AdgroupRequest`의 필수 필드: 생성 시 = customerId, mobileChannelId, name, nccCampaignId, pcChannelId; 수정 시 = bidAmt, contentsNetworkBidAmt, contentsNetworkBidWeight, dailyBudget, mobileNetworkBidWeight, nccAdgroupId, pcNetworkBidWeight, useCntsNetworkBidAmt, useCntsNetworkBidWeight, useDailyBudget, userLock

**응답**: [Adgroup](06-models.md#model-adgroup) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/adgroups/<adgroupId>?fields=bidAmt
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "bidAmt": 0,
  "contentsNetworkBidAmt": 0,
  "contentsNetworkBidWeight": 0,
  "dailyBudget": 0,
  "mobileNetworkBidWeight": 0,
  "nccAdgroupId": "<nccAdgroupId>",
  "pcNetworkBidWeight": 0,
  "useCntsNetworkBidAmt": false,
  "useCntsNetworkBidWeight": false,
  "useDailyBudget": false,
  "userLock": false
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-018"></a>
### 18. 광고그룹 ID로 여러 개 조회

`GET /ncc/adgroups{?ids}`

- **쉬운 설명**: 광고그룹 ID 목록으로 설정을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of adgroups of input adgroup ids
- **공식 요약(summary)**: list (by ids) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | IDs of the Ad Group |

**응답**: [Adgroup[]](06-models.md#model-adgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-019"></a>
### 19. 캠페인별 광고그룹 목록

`GET /ncc/adgroups{?nccCampaignId,baseSearchId,recordSize,selector}`

- **쉬운 설명**: 캠페인 안의 광고그룹 목록을 본다(나눠 받기 가능)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of partially AdGroups of input campaign id
- **공식 요약(summary)**: list (by campaign id) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups%7B%3FnccCampaignId,baseSearchId,recordSize,selector%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccCampaignId` | 쿼리 | ✔ | string |  | ID of the new clickchoice campaign |
| `baseSearchId` | 쿼리 |  | string |  | The query criteria AdGroup ID value. |
| `recordSize` | 쿼리 |  | integer(int32) |  | The number of list of AdGroups to receive the response. You can enter between 1 to 1000 |
| `selector` | 쿼리 |  | string | PREVIOUS, NEXT | If, please enter the value of the “PREVIOUS” to the selector parameter if you want to read the previous data. |

**응답**: [Adgroup[]](06-models.md#model-adgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups?nccCampaignId=<nccCampaignId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-020"></a>
### 20. 즐겨찾기별 광고그룹 조회

`GET /ncc/adgroups{?nccLabelId}`

- **쉬운 설명**: 즐겨찾기(라벨)에 넣어 둔 광고그룹 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of adgroups of input label id
- **공식 요약(summary)**: list (by label id) · 태그: Adgroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fadgroups%7B%3FnccLabelId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccLabelId` | 쿼리 | ✔ | string |  | ID of the new clickchoice label |

**응답**: [Adgroup[]](06-models.md#model-adgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/adgroups?nccLabelId=<nccLabelId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-021"></a>
### 21. 소재 등록

`POST /ncc/ads`

- **쉬운 설명**: 광고그룹에 광고 문구(소재)나 쇼핑 상품소재를 새로 등록한다
- **구분**: 생성 · **광고비·노출 영향**: 있음 — 검수 통과·ON이면 노출 시작
- **공식 설명**: create an ad
- **공식 요약(summary)**: create · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fads>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ad` | 본문 | ✔ | [AdRequest](06-models.md#model-adrequest) |  | ad |

본문 모델 `AdRequest`의 필수 필드: 생성 시 = ad, nccAdgroupId, type; 수정 시 = adAttr, nccAdId

**응답**: [Ad](06-models.md#model-ad) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/ads
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "ad": {},
  "nccAdgroupId": "<nccAdgroupId>",
  "type": "TEXT_45"
}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-022"></a>
### 22. 소재 1개 조회

`GET /ncc/ads/{adId}`

- **쉬운 설명**: 소재 하나의 문구·상태·검수 결과를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 입력한 ID에 해당하는 소재를 조회합니다. Return the ad of the adId
- **공식 요약(summary)**: get · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fads~2F%7BadId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adId` | 경로 | ✔ | string |  | ID of new clickchoice ad |

**응답**: [Ad](06-models.md#model-ad) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ads/<adId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-023"></a>
### 23. 소재 삭제

`DELETE /ncc/ads/{adId}`

- **쉬운 설명**: 소재 하나를 지운다(되돌릴 수 없음)
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 그 소재 노출이 멈춤
- **공식 설명**: remove an ad of the adId
- **공식 요약(summary)**: delete · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fads~2F%7BadId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adId` | 경로 | ✔ | string |  | ID of the ad |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/ads/<adId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-024"></a>
### 24. 소재 변경

`PUT /ncc/ads/{adId}{?fields}`

- **쉬운 설명**: 소재의 ON/OFF를 바꾸거나 검수를 다시 요청한다(명세 허용값: userLock, inspect)
- **구분**: 변경 · **광고비·노출 영향**: 있음 — ON/OFF가 바로 노출에 반영
- **공식 설명**: 광고 소재의 정보를 변경합니다. Update the fields of the ads
- **공식 요약(summary)**: update · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fads~2F%7BadId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ad` | 본문 | ✔ | [AdRequest](06-models.md#model-adrequest) |  | ad |
| `fields` | 쿼리 | ✔ | string | userLock, inspect | The field to modify |
| `adId` | 경로 | ✔ | string |  | ID of the ad |

본문 모델 `AdRequest`의 필수 필드: 생성 시 = ad, nccAdgroupId, type; 수정 시 = adAttr, nccAdId

**응답**: [Ad](06-models.md#model-ad) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/ads/<adId>?fields=userLock
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "adAttr": {},
  "nccAdId": "<nccAdId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-025"></a>
### 25. 소재 복사

`PUT /ncc/ads{?ids,targetAdgroupId,userLock}`

- **쉬운 설명**: 소재를 다른 광고그룹으로 복사한다(복사본 ON/OFF 지정)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — ON으로 복사하면 그 그룹에서 노출 시작
- **공식 설명**: 광고 소재를 원하는 광고그룹에 복사합니다. Copy ads to another adgroup
- **공식 요약(summary)**: copy · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fads%7B%3Fids,targetAdgroupId,userLock%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids |
| `targetAdgroupId` | 쿼리 | ✔ | string |  | targetAdgroupId |
| `userLock` | 쿼리 | ✔ | string |  | userLock |

**응답**: [Ad[]](06-models.md#model-ad) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/ads?ids=<ids>&targetAdgroupId=<targetAdgroupId>&userLock=<userLock>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-026"></a>
### 26. 소재 ID로 여러 개 조회

`GET /ncc/ads{?ids}`

- **쉬운 설명**: 소재 ID 목록으로 내용을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 입력한 ID 목록의 소재를 조회합니다. Return the list of ads
- **공식 요약(summary)**: list · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fads%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 |  | string |  | IDs of the ad |

**응답**: [Ad[]](06-models.md#model-ad) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ads
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-027"></a>
### 27. 광고그룹별 소재 목록

`GET /ncc/ads{?nccAdgroupId}`

- **쉬운 설명**: 광고그룹 안의 소재 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 광고그룹에 포함된 소재 목록을 조회합니다. Returns the list of ads of the adgroup id
- **공식 요약(summary)**: list (by adgroup id) · 태그: Ad
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fads%7B%3FnccAdgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccAdgroupId` | 쿼리 |  | string |  | ID of the adgroup |

**응답**: [Ad[]](06-models.md#model-ad) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/ads
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-028"></a>
### 28. 신제품검색 계약 전체 조회

`GET /ncc/brand-new/contracts`

- **쉬운 설명**: 계정의 신제품검색(브랜드 신제품) 계약 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 해당 계정의 모든 신제품 검색 계약을 조회 한다 Returns the list of time contracts of customer
- **공식 요약(summary)**: list · 태그: BrandNewContract
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fbrand-new~2Fcontracts>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [BrandNewContract[]](06-models.md#model-brandnewcontract) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/brand-new/contracts
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-029"></a>
### 29. 광고그룹별 신제품검색 계약 조회

`GET /ncc/brand-new/contracts{?adgroupId}`

- **쉬운 설명**: 광고그룹 하나의 신제품검색 계약을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 해당 계정의 특정 광고그룹 하위의 신제품 검색 계약을 조회한다. Returns the list of time contracts of adgroup
- **공식 요약(summary)**: list (by adgroup id) · 태그: BrandNewContract
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fbrand-new~2Fcontracts%7B%3FadgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adgroupId` | 쿼리 | ✔ | string |  | adgroupId |

**응답**: [BrandNewContract[]](06-models.md#model-brandnewcontract) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/brand-new/contracts?adgroupId=<adgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-030"></a>
### 30. 캠페인 생성

`POST /ncc/campaigns`

- **쉬운 설명**: 파워링크·쇼핑·플레이스 등 캠페인을 새로 만든다(하루예산·기간)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — ON으로 만들면 하위 광고가 노출·과금될 수 있음
- **공식 설명**: 새로운 캠페인을 생성합니다. Create a new campaign
- **공식 요약(summary)**: create · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fcampaigns>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `campaign` | 본문 | ✔ | [CampaignRequest](06-models.md#model-campaignrequest) |  | campaign |

본문 모델 `CampaignRequest`의 필수 필드: 생성 시 = campaignTp, customerId, name; 수정 시 = nccCampaignId, userLock

**응답**: [Campaign](06-models.md#model-campaign) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/campaigns
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "campaignTp": "WEB_SITE",
  "customerId": 0,
  "name": "<name>"
}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-031"></a>
### 31. 공유예산에 묶인 캠페인 조회

`GET /ncc/campaigns/shared-budgets/{sharedBudgetId}`

- **쉬운 설명**: 공유예산 하나에 연결된 캠페인 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공유예산에 연결된 캠페인 리스트를 조회합니다. Returns a list of campaigns associated with shared budget.
- **공식 요약(summary)**: list (by sharedBudgetId) · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcampaigns~2Fshared-budgets~2F%7BsharedBudgetId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `sharedBudgetId` | 경로 | ✔ | string |  | sharedBudgetId |

**응답**: [Campaign[]](06-models.md#model-campaign) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/campaigns/shared-budgets/<sharedBudgetId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-032"></a>
### 32. 캠페인 1개 조회

`GET /ncc/campaigns/{campaignId}`

- **쉬운 설명**: 캠페인 하나의 설정(하루예산·상태·기간)을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 단일 개체의 캠페인을 조회합니다. Returns the campaign of input ID
- **공식 요약(summary)**: get · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcampaigns~2F%7BcampaignId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `campaignId` | 경로 | ✔ | string |  | 캠페인 ID The unique ID of the Campaign |

**응답**: [Campaign](06-models.md#model-campaign) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/campaigns/<campaignId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-033"></a>
### 33. 캠페인 삭제

`DELETE /ncc/campaigns/{campaignId}`

- **쉬운 설명**: 캠페인과 그 안의 모든 광고그룹·키워드·소재를 영구 삭제한다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 캠페인 광고 전부 사라짐(복구 불가)
- **공식 설명**: 지정한 캠페인을 영구적으로 삭제합니다. 하위 요소가 존재하는 경우, 모든 하위요소는 함께 삭제됩니다.
- **공식 요약(summary)**: delete · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fcampaigns~2F%7BcampaignId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `campaignId` | 경로 | ✔ | string |  | campaignId |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/campaigns/<campaignId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-034"></a>
### 34. 캠페인 변경

`PUT /ncc/campaigns/{campaignId}{?fields}`

- **쉬운 설명**: 캠페인의 ON/OFF·하루예산·노출 기간을 바꾼다(fields 없으면 전체 변경)
- **구분**: 변경 · **광고비·노출 영향**: 높음 — ON·예산 증액은 광고비 증가로 이어질 수 있음
- **공식 설명**: 캠페인을 수정합니다. fields 파라미터가 없을 경우 캠페인 전체가 변경됩니다. fields 파라미터에 입력하는 값의 유형에 따라 수정되는 캠페인의 필드가 결정됩니다. Change the Campaign. The parameter fields, enter the name of the Campaign field you want to change. or you can modify the campaign entire information if you give the full campaign json when calling api
- **공식 요약(summary)**: update · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fcampaigns~2F%7BcampaignId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `campaign` | 본문 | ✔ | [CampaignRequest](06-models.md#model-campaignrequest) |  | campaign |
| `fields` | 쿼리 |  | string | userLock, budget, period | Field name of the Campaign you want to modify |
| `campaignId` | 경로 | ✔ | string |  | The unique ID of the Campaign. |

본문 모델 `CampaignRequest`의 필수 필드: 생성 시 = campaignTp, customerId, name; 수정 시 = nccCampaignId, userLock

**응답**: [Campaign](06-models.md#model-campaign) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/campaigns/<campaignId>?fields=userLock
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "nccCampaignId": "<nccCampaignId>",
  "userLock": false
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-035"></a>
### 35. 캠페인 목록

`GET /ncc/campaigns{?campaignType,baseSearchId,recordSize,selector}`

- **쉬운 설명**: 계정의 캠페인 목록을 본다(유형별, 나눠 받기 가능)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 조회 조건에 해당하는 캠페인 목록을 조회합니다. Returns the list of partially campaigns of customer
- **공식 요약(summary)**: list (by customer id, campaign type) · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcampaigns%7B%3FcampaignType,baseSearchId,recordSize,selector%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `campaignType` | 쿼리 |  | string |  | 캠페인 유형값. Campaign Type value. |
| `baseSearchId` | 쿼리 |  | string |  | 기준이 되는 캠페인 ID. The query criteria Campaign ID value. |
| `recordSize` | 쿼리 |  | integer(int32) |  | 조회하는 캠페인 개수. 1 ~ 1000 사이의 값을 가집니다. The number of list of Campaigns to receive the response. You can enter between 1 to 2000 |
| `selector` | 쿼리 |  | string | PREVIOUS, NEXT | baseSearchId기준으로 전방, 또는 후방 탐색을 결정합니다. If, please enter the value of the “PREVIOUS” to the selector parameter if you want to read the previous data. |

**응답**: [Campaign[]](06-models.md#model-campaign) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/campaigns
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-036"></a>
### 36. 캠페인 ID로 여러 개 조회

`GET /ncc/campaigns{?ids}`

- **쉬운 설명**: 캠페인 ID 목록으로 설정을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 입력된 아이디에 해당하는 캠페인 목록을 조회합니다. Returns the list of campaigns of input campaign ids.
- **공식 요약(summary)**: list (by ids) · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcampaigns%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | 조회하고자 하는 캠페인의 ID 목록. IDs of the campaign. |

**응답**: [Campaign[]](06-models.md#model-campaign) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/campaigns?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-037"></a>
### 37. 캠페인 여러 개 삭제

`DELETE /ncc/campaigns{?ids}`

- **쉬운 설명**: 여러 캠페인과 하위 광고를 한 번에 영구 삭제한다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 복구 불가
- **공식 설명**: 뉴 클릭초이스 다수의 캠페인 삭제
- **공식 요약(summary)**: delete items · 태그: Campaign
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fcampaigns%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string 배열 |  | ids |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/campaigns?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-038"></a>
### 38. 비즈채널 목록

`GET /ncc/channels`

- **쉬운 설명**: 등록된 비즈채널(웹사이트·쇼핑몰·플레이스·전화번호 등) 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of business channel.
- **공식 요약(summary)**: list · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fchannels>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [BusinessChannel[]](06-models.md#model-businesschannel) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/channels
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-039"></a>
### 39. 비즈채널 등록

`POST /ncc/channels`

- **쉬운 설명**: 광고에 연결할 웹사이트·쇼핑몰·전화번호 등을 새로 등록한다(검수 필요)
- **구분**: 생성 · **광고비·노출 영향**: 간접 — 검수 통과 전엔 그 채널로 광고 불가
- **공식 설명**: Create a new business channel.
- **공식 요약(summary)**: create · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fchannels>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `channel` | 본문 | ✔ | [BusinessChannel](06-models.md#model-businesschannel) |  | channel |

본문 모델 `BusinessChannel`의 필수 필드: 수정 시 = nccBusinessChannelId

**응답**: [BusinessChannel](06-models.md#model-businesschannel) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/channels
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-040"></a>
### 40. 비즈채널 1개 조회

`GET /ncc/channels/{businessChannelId}`

- **쉬운 설명**: 비즈채널 하나의 정보·검수 상태를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the business channel of input business channel id.
- **공식 요약(summary)**: get · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fchannels~2F%7BbusinessChannelId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `businessChannelId` | 경로 |  | string |  | The unique ID of the business channel. |

**응답**: [BusinessChannel](06-models.md#model-businesschannel) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/channels/<businessChannelId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-041"></a>
### 41. 비즈채널 삭제

`DELETE /ncc/channels/{businessChannelId}`

- **쉬운 설명**: 비즈채널 하나를 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 연결된 광고가 노출되지 못할 수 있음
- **공식 설명**: Remove a business channel
- **공식 요약(summary)**: delete · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fchannels~2F%7BbusinessChannelId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `businessChannelId` | 경로 |  | string |  | The unique ID of the business channel. |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/channels/<businessChannelId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-042"></a>
### 42. 비즈채널 재검수 요청

`PUT /ncc/channels/{businessChannelId}/inspect`

- **쉬운 설명**: 검수에서 보류·반려된 비즈채널을 다시 검수해 달라고 요청한다
- **구분**: 변경 · **광고비·노출 영향**: 간접 — 통과하면 광고 가능
- **공식 설명**: request reinspect of business channel.
- **공식 요약(summary)**: request inspect · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fchannels~2F%7BbusinessChannelId%7D~2Finspect>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `channel` | 본문 | ✔ | [BusinessChannel](06-models.md#model-businesschannel) |  | channel |
| `businessChannelId` | 경로 |  | string |  | The unique ID of the business channel. |

본문 모델 `BusinessChannel`의 필수 필드: 수정 시 = nccBusinessChannelId

**응답**: [BusinessChannel](06-models.md#model-businesschannel) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/channels/<businessChannelId>/inspect
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "nccBusinessChannelId": "<nccBusinessChannelId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-043"></a>
### 43. 비즈채널 변경

`PUT /ncc/channels/{businessChannelId}{?fields}`

- **쉬운 설명**: 비즈채널 이름·검수용 계정 정보 등을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 간접
- **공식 설명**: Change the business channel The parameter field, you can enter one of the following: 'name', 'inspectId', 'inspectPw', 'secondary'
- **공식 요약(summary)**: update · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fchannels~2F%7BbusinessChannelId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `businessChannelId` | 경로 | ✔ | string |  | businessChannelId |
| `fields` | 쿼리 | ✔ | string 배열 |  | fields |
| `channel` | 본문 | ✔ | [BusinessChannel](06-models.md#model-businesschannel) |  | channel |

본문 모델 `BusinessChannel`의 필수 필드: 수정 시 = nccBusinessChannelId

**응답**: [BusinessChannel](06-models.md#model-businesschannel) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/channels/<businessChannelId>?fields=<fields>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "nccBusinessChannelId": "<nccBusinessChannelId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-044"></a>
### 44. 유형별 비즈채널 목록

`GET /ncc/channels{?channelTp}`

- **쉬운 설명**: 웹사이트·쇼핑몰·플레이스 등 유형을 골라 비즈채널을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the business channel list of channel type.
- **공식 요약(summary)**: list(by channel Type) · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fchannels%7B%3FchannelTp%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `channelTp` | 쿼리 | ✔ | string | SITE, PHONE, ADDRESS, BOOKING, TALK, MALL, CONTENTS, PLACE, CATALOG, NAVER_TV, BRAND_STORE, SHOPPING_BRAND | Type of the business channel |

**응답**: [BusinessChannel[]](06-models.md#model-businesschannel) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/channels?channelTp=SITE
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-045"></a>
### 45. 비즈채널 ID로 여러 개 조회

`GET /ncc/channels{?ids}`

- **쉬운 설명**: 비즈채널 ID 목록으로 정보를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the business channel list of input business channel ids.
- **공식 요약(summary)**: list(by ids) · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fchannels%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | IDs of the new clickchoice business channel |

**응답**: [BusinessChannel[]](06-models.md#model-businesschannel) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/channels?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-046"></a>
### 46. 비즈채널 여러 개 삭제

`DELETE /ncc/channels{?ids}`

- **쉬운 설명**: 여러 비즈채널을 한 번에 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 있음
- **공식 설명**: Remove business channels in id list.
- **공식 요약(summary)**: delete(by ids) · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fchannels%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | IDs of the new clickchoice business channel |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/channels?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-047"></a>
### 47. 타기팅 코드표 조회

`GET /ncc/criterion-dictionary/{type}`

- **쉬운 설명**: 지역·연령·성별·요일·시간·기기 등 타기팅에 쓸 수 있는 코드 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 광고그룹에서 지원되는 타게팅 코드를 조회할 수 있습니다. 반경(PROXIMITY)는 조회할 수 없습니다. You can check the target code supported by the adgroup. The PROXIMITY cannot be inquired.
- **공식 요약(summary)**: get Criterion dictionary code · 태그: Criterion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcriterion-dictionary~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 |  | string |  | Criterion code 종류. dictionary code |

**응답**: [CriterionDictionary[]](06-models.md#model-criteriondictionary) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/criterion-dictionary/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-048"></a>
### 48. 타기팅 입찰 가중치 변경

`PUT /ncc/criterion/{ownerId}/bidWeight{?codes,bidWeight}`

- **쉬운 설명**: 특정 지역·시간·기기 등에 입찰가를 더 주거나 덜 준다(%)
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 가중치가 오르면 실제 입찰가가 오름
- **공식 설명**: 등록된 타겟팅의 입찰가 가중치를 변경할 수 있습니다. You can change the weighting of registered criterion.
- **공식 요약(summary)**: update bidWeight · 태그: Criterion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fcriterion~2F%7BownerId%7D~2FbidWeight%7B%3Fcodes,bidWeight%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ownerId` | 경로 |  | string |  | 타겟팅이 속한 광고그룹 ID. ID of ad group |
| `codes` | 쿼리 |  | ref |  | 타겟팅 코드를 여러개 입력할 수 있습니다. The list of dictionary Code List |
| `bidWeight` | 쿼리 |  | integer(int32) |  | 입찰가중치를 50부터 500까지 설정할 수 있습니다. You can set the bidWeight from 50 to 500. |

**응답**: [Criterion[]](06-models.md#model-criterion) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/criterion/<ownerId>/bidWeight
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-049"></a>
### 49. 타기팅 설정 변경

`PUT /ncc/criterion/{ownerId}/{type}`

- **쉬운 설명**: 광고그룹의 지역·연령·성별·요일·시간·기기 타기팅을 유형별로 바꾼다(빠진 코드는 꺼짐)
- **구분**: 변경 · **광고비·노출 영향**: 있음 — 노출 대상이 넓어지거나 좁아짐
- **공식 설명**: 타겟팅 유형별로 타겟팅을 변경할 수 있습니다. 타겟팅 변경 시 Request Body에 포함되지 않는 코드는 모드 사용안함 처리가 되니 주의를 요합니다. 반경 타겟팅 추가의 경우 dictionaryCode에 ‘Proximity’ 문자열을 입력해 주세요. 서버에 저장후 정상적인 code로 반환이 됩니다. Targeting can be changed by targeting type. Please note that when you change the targeting, all code that is not included in the Request Body will be disabled. If you want to add a Proximity target, enter the “Proximity” string in dictionaryCode. It will be saved on the server and returned to normal code..
- **공식 요약(summary)**: update Criterion · 태그: Criterion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fcriterion~2F%7BownerId%7D~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `requests` | 본문 | ✔ | [CriterionRequest[]](06-models.md#model-criterionrequest) |  | requests |
| `ownerId` | 경로 |  | string |  | 타겟팅이 속한 광고그룹 ID. ID of ad group |
| `type` | 경로 |  | string | SD, AG, GN, AD, RL, RP, DV | criterion dictionary type |

**응답**: [Criterion[]](06-models.md#model-criterion) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/criterion/<ownerId>/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-050"></a>
### 50. 타기팅 설정 조회

`GET /ncc/criterion/{ownerId}{?type}`

- **쉬운 설명**: 광고그룹에 걸린 타기팅 설정을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 광고그룹에 속한 타겟팅 정보를 반환합니다. Returns the list of Criterion
- **공식 요약(summary)**: list (by id) · 태그: Criterion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fcriterion~2F%7BownerId%7D%7B%3Ftype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ownerId` | 경로 |  | string |  | 타겟팅이 속한 광고그룹 ID. ID of ad group |
| `type` | 쿼리 |  | string | SD, AG, GN, AD, RL, RP, DV | criterion dictionary type |

**응답**: [Criterion[]](06-models.md#model-criterion) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/criterion/<ownerId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-051"></a>
### 51. 키워드 1개 조회

`GET /ncc/keywords/{nccKeywordId}`

- **쉬운 설명**: 키워드 하나의 입찰가·상태·지표를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Return an AdKeyword of input AdKeywordId.
- **공식 요약(summary)**: get · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fkeywords~2F%7BnccKeywordId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccKeywordId` | 경로 | ✔ | string |  | The unique Id of the keyword |

**응답**: [AdKeyword](06-models.md#model-adkeyword) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/keywords/<nccKeywordId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-052"></a>
### 52. 키워드 1개 삭제

`DELETE /ncc/keywords/{nccKeywordId}`

- **쉬운 설명**: 키워드 하나를 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 그 키워드 노출이 멈춤
- **공식 설명**: Remove a AdKeyword.
- **공식 요약(summary)**: delete · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fkeywords~2F%7BnccKeywordId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccKeywordId` | 경로 |  | string |  | The unique Id of the keyword. |

**응답**: OK (명세 응답 코드: 200, 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/keywords/<nccKeywordId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-053"></a>
### 53. 키워드 1개 변경

`PUT /ncc/keywords/{nccKeywordId}{?fields}`

- **쉬운 설명**: 키워드 하나의 ON/OFF·입찰가·연결 URL·검수 요청을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 입찰가·ON/OFF가 바로 광고비에 반영
- **공식 설명**: Change the AD Keyword The parameter field, you can enter one of the following: 'userLock', 'bidAmt', 'links', 'inspect' - if field is userLock then Adkeyword.userlock is required - if field is bidAmt then Adkeywords.bidAmt and Adkeyword.useGroupBidAmt are required - if field is links then Adkeyword.links is required and links is json-formatted string - if field is attr then Adkeyword.attr is required and attr is json-formatted string - if field is inspect then Adkeyword's status sholud have pendded.
- **공식 요약(summary)**: update · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fkeywords~2F%7BnccKeywordId%7D%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `keyword` | 본문 | ✔ | [KeywordRequest](06-models.md#model-keywordrequest) |  | keyword |
| `nccKeywordId` | 경로 | ✔ | string |  | The unique Id of the keyword. |
| `fields` | 쿼리 |  | string | 'userLock', 'bidAmt', 'links', 'inspect' | update target |

본문 모델 `KeywordRequest`의 필수 필드: 생성 시 = keyword; 수정 시 = attr, nccAdgroupId, nccKeywordId

**응답**: [AdKeyword](06-models.md#model-adkeyword) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/keywords/<nccKeywordId>?fields='userLock'
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "attr": {},
  "nccAdgroupId": "<nccAdgroupId>",
  "nccKeywordId": "<nccKeywordId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-054"></a>
### 54. 키워드 여러 개 변경

`PUT /ncc/keywords{?fields}`

- **쉬운 설명**: 키워드 최대 200개의 ON/OFF·입찰가·연결 URL·검수 요청을 한 번에 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 입찰가·ON/OFF가 바로 광고비에 반영
- **공식 설명**: Change AD Keywords.(fields=userLock, bidAmt, inspect, links) The maximum number of requests is 200. - if field is userLock then Adkeyword.userlock is required - if field is bidAmt then Adkeywords.bidAmt and Adkeyword.useGroupBidAmt are required - if field is links then Adkeyword.links is required and links is json-formatted string - if field is attr then Adkeyword.attr is required and attr is json-formatted string - if field is inspect then Adkeyword's status sholud have pendded.
- **공식 요약(summary)**: update-items · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fkeywords%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccKeywords` | 본문 | ✔ | [KeywordRequest[]](06-models.md#model-keywordrequest) |  | nccKeywords |
| `fields` | 쿼리 |  | string | 'userLock', 'bidAmt', 'links', 'inspect' | update target |

본문 모델 `KeywordRequest`의 필수 필드: 생성 시 = keyword; 수정 시 = attr, nccAdgroupId, nccKeywordId

**응답**: [AdKeyword[]](06-models.md#model-adkeyword) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/keywords?fields='userLock'
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {
    "attr": {},
    "nccAdgroupId": "<nccAdgroupId>",
    "nccKeywordId": "<nccKeywordId>"
  }
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-055"></a>
### 55. 키워드 ID로 여러 개 조회

`GET /ncc/keywords{?ids}`

- **쉬운 설명**: 키워드 ID 목록으로 정보를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of AdKeyword of input AdKeyword Ids.
- **공식 요약(summary)**: list (by ids) · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fkeywords%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids of the AdKeywordId |

**응답**: [AdKeyword[]](06-models.md#model-adkeyword) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/keywords?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-056"></a>
### 56. 키워드 여러 개 삭제

`DELETE /ncc/keywords{?ids}`

- **쉬운 설명**: 여러 키워드를 한 번에 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 있음
- **공식 설명**: remove requested keywords.
- **공식 요약(summary)**: delete-items · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fkeywords%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids of the AdKeywordId |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/keywords?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-057"></a>
### 57. 광고그룹별 키워드 목록

`GET /ncc/keywords{?nccAdgroupId,baseSearchId,recordSize,selector}`

- **쉬운 설명**: 광고그룹 안의 키워드 목록을 본다(나눠 받기 가능)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the partially keyword list of input AdGroup Id.
- **공식 요약(summary)**: list (by adgroup id) · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fkeywords%7B%3FnccAdgroupId,baseSearchId,recordSize,selector%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccAdgroupId` | 쿼리 | ✔ | string |  | The unique ID of the AdGroup. |
| `baseSearchId` | 쿼리 |  | string |  | The query criteria Adkeyword ID value. |
| `recordSize` | 쿼리 |  | integer(int32) |  | The number of list of Adkeywords to receive the response. You can enter between 1 to 1000 |
| `selector` | 쿼리 |  | string | PREVIOUS, NEXT | If, please enter the value of the “PREVIOUS” to the selector parameter if you want to read the previous data. |

**응답**: [AdKeyword[]](06-models.md#model-adkeyword) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/keywords?nccAdgroupId=<nccAdgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-058"></a>
### 58. 키워드 등록

`POST /ncc/keywords{?nccAdgroupId}`

- **쉬운 설명**: 광고그룹에 키워드를 최대 100개 새로 등록한다(입찰가 포함)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — 검수 통과·ON이면 노출·과금 시작
- **공식 설명**: Create AD Keyword. The maximum number of requests is 100.
- **공식 요약(summary)**: create · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fkeywords%7B%3FnccAdgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `kwdRequests` | 본문 | ✔ | [KeywordRequest[]](06-models.md#model-keywordrequest) |  | kwdRequests |
| `nccAdgroupId` | 쿼리 | ✔ | string |  | nccAdgroupId |

본문 모델 `KeywordRequest`의 필수 필드: 생성 시 = keyword; 수정 시 = attr, nccAdgroupId, nccKeywordId

**응답**: [AdKeyword[]](06-models.md#model-adkeyword) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/keywords?nccAdgroupId=<nccAdgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {
    "keyword": "<keyword>"
  }
]
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-059"></a>
### 59. 즐겨찾기별 키워드 조회

`GET /ncc/keywords{?nccLabelId}`

- **쉬운 설명**: 즐겨찾기(라벨)에 넣어 둔 키워드 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of AdKeyword of input label id.
- **공식 요약(summary)**: list (by label id) · 태그: AdKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fkeywords%7B%3FnccLabelId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `nccLabelId` | 쿼리 | ✔ | string |  | nccLabelId |

**응답**: [AdKeyword[]](06-models.md#model-adkeyword) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/keywords?nccLabelId=<nccLabelId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-060"></a>
### 60. 즐겨찾기에 넣기·빼기

`PUT /ncc/label-refs`

- **쉬운 설명**: 광고그룹·소재·키워드를 즐겨찾기(라벨)에 넣거나 뺀다
- **구분**: 변경 · **광고비·노출 영향**: 없음
- **공식 설명**: Create or Delete label references to Adgroups or Ads or Keywords.
- **공식 요약(summary)**: update · 태그: LabelRef
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Flabel-refs>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `labelRefs` | 본문 | ✔ | [LabelRef[]](06-models.md#model-labelref) |  | labelRefs |

**응답**: [LabelRef[]](06-models.md#model-labelref) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/label-refs
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-061"></a>
### 61. 즐겨찾기 목록

`GET /ncc/labels`

- **쉬운 설명**: 계정의 즐겨찾기(라벨) 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves information on the entire labels of an advertiser.
- **공식 요약(summary)**: list · 태그: Label
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Flabels>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [Label[]](06-models.md#model-label) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/labels
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-062"></a>
### 62. 즐겨찾기 이름 변경

`PUT /ncc/labels`

- **쉬운 설명**: 즐겨찾기(라벨) 이름을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 없음
- **공식 설명**: Renames a label. Any names which are already used in other labels within one advertiser cannot be used.
- **공식 요약(summary)**: update · 태그: Label
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Flabels>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `label` | 본문 | ✔ | [Label](06-models.md#model-label) |  | label |

**응답**: [Label](06-models.md#model-label) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/labels
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-063"></a>
### 63. 키워드 정보 조회(본문 방식)

`POST /ncc/managedKeyword`

- **쉬운 설명**: 키워드가 성인·브랜드 등 관리 키워드인지 등 키워드 속성을 본다(긴 목록용)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: POST version of /managedKeyword. Accepts keywords in JSON body to avoid URL length limits.
- **공식 요약(summary)**: list (by keywords, POST) · 태그: ManagedKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2FmanagedKeyword>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `request` | 본문 | ✔ | [ManagedKeywordRequest](06-models.md#model-managedkeywordrequest) |  | request |

**응답**: [ManagedKeywordResponse[]](06-models.md#model-managedkeywordresponse) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/managedKeyword
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-064"></a>
### 64. 키워드 정보 조회

`GET /ncc/managedKeyword{?keywords}`

- **쉬운 설명**: 키워드 속성(관리 키워드 여부 등)을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the list of ManagedKeyword List of input keywords
- **공식 요약(summary)**: list (by keywords) · 태그: ManagedKeyword
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2FmanagedKeyword%7B%3Fkeywords%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `keywords` | 쿼리 |  | string |  |  |

**응답**: [ManagedKeywordResponse[]](06-models.md#model-managedkeywordresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/managedKeyword
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-065"></a>
### 65. 상품 그룹 목록

`GET /ncc/product-groups`

- **쉬운 설명**: 계정에 등록된 상품 그룹(쇼핑) 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 계정에 등록된 상품 그룹의 목록은 API를 이용하여 조회할 수 있습니다. The list of product groups registered in the account can be inquired using the API below
- **공식 요약(summary)**: get · 태그: ProductGroup
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fproduct-groups>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [ProductGroup[]](06-models.md#model-productgroup) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/product-groups
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-066"></a>
### 66. 광고 가능한 플레이스 채널 조회

`GET /ncc/purchasable-place-channels{?type}`

- **쉬운 설명**: 플레이스 광고에 쓸 수 있는 플레이스 비즈채널 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns the business channel list of purchasable place type.
- **공식 요약(summary)**: list(by channel Type) · 태그: BusinessChannel
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fpurchasable-place-channels%7B%3Ftype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 쿼리 |  | integer(int32) |  | type |

**응답**: [BusinessChannel[]](06-models.md#model-businesschannel) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/purchasable-place-channels
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-067"></a>
### 67. 공유예산 목록

`GET /ncc/shared-budgets`

- **쉬운 설명**: 여러 캠페인·광고그룹이 함께 쓰는 공유예산 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공유예산의 리스트를 조회합니다. Returns the list of Shared budget.
- **공식 요약(summary)**: get · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fshared-budgets>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [SharedBudget[]](06-models.md#model-sharedbudget) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/shared-budgets
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-068"></a>
### 68. 공유예산 만들기

`POST /ncc/shared-budgets`

- **쉬운 설명**: 여러 캠페인·광고그룹이 함께 쓰는 예산을 새로 만든다
- **구분**: 생성 · **광고비·노출 영향**: 높음 — 예산 한도 구조가 바뀜
- **공식 설명**: 공유예산을 생성합니다. Create the shared budget.
- **공식 요약(summary)**: create · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Fshared-budgets>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `request` | 본문 | ✔ | [SharedBudgetRequest](06-models.md#model-sharedbudgetrequest) |  | request |

본문 모델 `SharedBudgetRequest`의 필수 필드: 생성 시 = customerId; 수정 시 = sharedBudgetId

**응답**: [SharedBudget](06-models.md#model-sharedbudget) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/shared-budgets
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "customerId": 0
}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-069"></a>
### 69. 공유예산에서 광고그룹 빼기

`PUT /ncc/shared-budgets/adgroups{?ids}`

- **쉬운 설명**: 광고그룹을 공유예산에서 제외한다
- **구분**: 변경 · **광고비·노출 영향**: 있음 — 그 그룹의 예산 기준이 바뀜
- **공식 설명**: 공유예산에 연결된 광고그룹을 공유예산에서 제외합니다. Remove adgroups connected to a shared budget from the shared budget.
- **공식 요약(summary)**: exclude adgroups · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fshared-budgets~2Fadgroups%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids |

**응답**: Created (명세 응답 코드: 201, 204, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/shared-budgets/adgroups?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-070"></a>
### 70. 공유예산에서 캠페인 빼기

`PUT /ncc/shared-budgets/campaigns{?ids}`

- **쉬운 설명**: 캠페인을 공유예산에서 제외한다
- **구분**: 변경 · **광고비·노출 영향**: 있음 — 그 캠페인의 예산 기준이 바뀜
- **공식 설명**: 공유예산에 연결된 캠페인을 공유예산에서 제외합니다. Remove campaigns connected to a shared budget from the shared budget.
- **공식 요약(summary)**: exclude campaigns · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fshared-budgets~2Fcampaigns%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids |

**응답**: Created (명세 응답 코드: 201, 204, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/shared-budgets/campaigns?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-071"></a>
### 71. 공유예산 1개 조회

`GET /ncc/shared-budgets/{sharedBudgetId}`

- **쉬운 설명**: 공유예산 하나의 금액·연결 대상을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 단건 공유예산을 조회합니다. Returns the Shared budget of input shared budget Id.
- **공식 요약(summary)**: get (by id) · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Fshared-budgets~2F%7BsharedBudgetId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `sharedBudgetId` | 경로 | ✔ | string |  | sharedBudgetId |

**응답**: [SharedBudget](06-models.md#model-sharedbudget) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/shared-budgets/<sharedBudgetId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-072"></a>
### 72. 공유예산 변경

`PUT /ncc/shared-budgets/{sharedBudgetId}`

- **쉬운 설명**: 공유예산 설정을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 예산 증액 시 광고비 증가 가능
- **공식 설명**: 공유예산을 수정합니다. Change the shared budget.
- **공식 요약(summary)**: update · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fshared-budgets~2F%7BsharedBudgetId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `sharedBudgetId` | 경로 | ✔ | string |  | sharedBudgetId |
| `request` | 본문 | ✔ | [SharedBudgetRequest](06-models.md#model-sharedbudgetrequest) |  | request |

본문 모델 `SharedBudgetRequest`의 필수 필드: 생성 시 = customerId; 수정 시 = sharedBudgetId

**응답**: [SharedBudget](06-models.md#model-sharedbudget) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/shared-budgets/<sharedBudgetId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{
  "sharedBudgetId": "<sharedBudgetId>"
}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-073"></a>
### 73. 공유예산 하루예산 변경

`PUT /ncc/shared-budgets{?fields}`

- **쉬운 설명**: 공유예산의 하루예산 금액을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 높음 — 예산 증액 시 광고비 증가 가능
- **공식 설명**: 공유예산의 하루예산을 수정합니다. Modify the daily budget of the shared budget.
- **공식 요약(summary)**: update budget · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Fshared-budgets%7B%3Ffields%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `fields` | 쿼리 | ✔ | string 배열 |  | fields |
| `sharedBudgets` | 본문 | ✔ | [SharedBudgetRequest[]](06-models.md#model-sharedbudgetrequest) |  | sharedBudgets |

본문 모델 `SharedBudgetRequest`의 필수 필드: 생성 시 = customerId; 수정 시 = sharedBudgetId

**응답**: [SharedBudget[]](06-models.md#model-sharedbudget) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/shared-budgets?fields=<fields>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {
    "sharedBudgetId": "<sharedBudgetId>"
  }
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-074"></a>
### 74. 공유예산 삭제

`DELETE /ncc/shared-budgets{?ids}`

- **쉬운 설명**: 공유예산을 지운다(명세 설명은 '하루예산 수정'으로 잘못 복사돼 있음)
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 연결 대상의 예산 기준이 바뀜(동작 세부는 미확인)
- **공식 설명**: 공유예산의 하루예산을 수정합니다. Modify the daily budget of the shared budget.
- **공식 요약(summary)**: delete · 태그: SharedBudget
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fncc~2Fshared-budgets%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | ids |

**응답**: No Content (명세 응답 코드: 204, 401, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /ncc/shared-budgets?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-075"></a>
### 75. 타깃 변경

`PUT /ncc/targets/{targetId}`

- **쉬운 설명**: 광고그룹·소재의 타깃 설정(매체·지역·시간·쇼핑 카탈로그 태그 등)을 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 있음 — 노출 범위가 바뀜
- **공식 설명**: 타겟팅을 변경합니다. 타겟팅 유형 중 AD_TAG는 쇼핑 캠페인 하위의 카탈로그 광고 소재에 적용되며, 그외 소재에 등록할 때 오류가 발생합니다. 등록가능항 태그의 길이는 최소 3자 부터 최대 10자이며, 최대 30개까지 등록 가능합니다. Change a target. Among the targeting types, AD_TAG is applied to catalog creatives under shopping campaigns, and an error occurs when registering for other creatives. The length of registerable tag is minimum 3 characters to maximum 10 characters. Up to 30 tags can be registered.
- **공식 요약(summary)**: update · 태그: Target
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Fncc~2Ftargets~2F%7BtargetId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `targetId` | 경로 | ✔ | string |  | targetId |
| `target` | 본문 | ✔ | [TargetRequest](06-models.md#model-targetrequest) |  | target |

**응답**: [Target](06-models.md#model-target) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /ncc/targets/<targetId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-076"></a>
### 76. 타깃 조회

`GET /ncc/targets{?ownerId,types}`

- **쉬운 설명**: 광고그룹·소재 하나의 타깃 설정을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves information on multiple Targets The ownerId value indicates either adgroup id or ad id.
- **공식 요약(summary)**: list (by owner id) · 태그: Target
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Ftargets%7B%3FownerId,types%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ownerId` | 쿼리 | ✔ | string |  | ownerId |
| `types` | 쿼리 |  | string 배열 |  | types |

**응답**: [Target[]](06-models.md#model-target) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/targets?ownerId=<ownerId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-077"></a>
### 77. 타깃 여러 개 조회

`GET /ncc/targets{?ownerIds}`

- **쉬운 설명**: 여러 광고그룹·소재의 타깃 설정을 한 번에 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves information on multiple Targets The owner ID list value indicates either adgroup id or ad id.
- **공식 요약(summary)**: list (by owner id list) · 태그: Target
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Ftargets%7B%3FownerIds%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ownerIds` | 쿼리 | ✔ | string |  |  |

**응답**: [Target[]](06-models.md#model-target) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/targets?ownerIds=<ownerIds>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-078"></a>
### 78. 브랜드검색 계약 전체 조회

`GET /ncc/time-contracts`

- **쉬운 설명**: 계정의 브랜드검색 계약 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 해당 계정의 모든 계약을 조회 한다 Returns the list of time contracts of customer
- **공식 요약(summary)**: list · 태그: TimeContract
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Ftime-contracts>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [TimeContract[]](06-models.md#model-timecontract) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/time-contracts
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-079"></a>
### 79. 광고그룹별 브랜드검색 계약 조회

`GET /ncc/time-contracts{?adgroupId}`

- **쉬운 설명**: 광고그룹 하나의 브랜드검색 계약을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 해당 계정의 특정 광고그룹 하위의 계약을 조회한다. Returns the list of time contracts of adgroup
- **공식 요약(summary)**: list (by adgroup id) · 태그: TimeContract
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Ftime-contracts%7B%3FadgroupId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adgroupId` | 쿼리 | ✔ | string |  |  |

**응답**: [TimeContract[]](06-models.md#model-timecontract) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/time-contracts?adgroupId=<adgroupId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 도구(Tool)
원본: `assets/json/ncc-heroes-tool.json`

<a id="ep-080"></a>
### 80. 애널리틱스 신청

`POST /tool/analyticses{?field}`

- **쉬운 설명**: 네이버 애널리틱스(전환 추적 등) 서비스를 신청한다
- **구분**: 생성 · **광고비·노출 영향**: 없음(추적 설정)
- **공식 설명**: Analytics 신청
- **공식 요약(summary)**: Analytics · 태그: AnalyticsController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Ftool~2Fanalyticses%7B%3Ffield%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `field` | 쿼리 |  | string |  | field |
| `analyticses` | 본문 | ✔ | [Analytics[]](06-models.md#model-analytics) |  | analyticses |

**응답**: [Analytics[]](06-models.md#model-analytics) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /tool/analyticses
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-081"></a>
### 81. 애널리틱스 해지·변경

`PUT /tool/analyticses{?modifyType}`

- **쉬운 설명**: 애널리틱스 해지, 전환일 변경, 해지 취소를 한다
- **구분**: 변경 · **광고비·노출 영향**: 없음(추적 설정)
- **공식 설명**: Analytics 해지, 전환일 변경, 해지취소
- **공식 요약(summary)**: Analytics · 태그: AnalyticsController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Ftool~2Fanalyticses%7B%3FmodifyType%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `modifyType` | 쿼리 |  | string |  | modifyType |
| `analyticses` | 본문 | ✔ | [Analytics[]](06-models.md#model-analytics) |  | analyticses |

**응답**: [Analytics[]](06-models.md#model-analytics) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /tool/analyticses
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-082"></a>
### 82. 애널리틱스 현황 조회

`GET /tool/analyticses{?searchType}`

- **쉬운 설명**: 애널리틱스 신청 현황을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Analytics 서비스 현황 전체
- **공식 요약(summary)**: Analytics · 태그: AnalyticsController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fanalyticses%7B%3FsearchType%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `searchType` | 쿼리 |  | string |  | searchType |

**응답**: [Analytics[]](06-models.md#model-analytics) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/analyticses
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-083"></a>
### 83. 세금계산서 발행처 위임 일자 조회

`GET /tool/bill-recipient-histories/latest`

- **쉬운 설명**: 세금계산서 발행처 위임 최근 일자를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공식 자료에서 확인되지 않음
- **공식 요약(summary)**: getByCustomerId · 태그: 세금계산서 발행처 위임 일자 조회
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fbill-recipient-histories~2Flatest>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [BillRecipientHis](06-models.md#model-billrecipienthis) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/bill-recipient-histories/latest
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-084"></a>
### 84. 내 접속 IP 조회

`GET /tool/client-ip`

- **쉬운 설명**: API를 부른 쪽의 IP를 본다(명세에서 #hidden 표시)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공식 자료에서 확인되지 않음
- **공식 요약(summary)**: get Client IP · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fclient-ip>

**파라미터**

없음(공통 인증 헤더만)

**응답**: object (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/client-ip
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-085"></a>
### 85. 서류 관리 현황 조회

`GET /tool/document`

- **쉬운 설명**: 광고 심사용 제출 서류 현황을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 서류관리 현황 전체
- **공식 요약(summary)**: Document · 태그: 서류 관리-DocumentController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fdocument>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [Document[]](06-models.md#model-document) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/document
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-086"></a>
### 86. 서류 내용 등록

`POST /tool/document`

- **쉬운 설명**: 광고 심사용 서류 내용을 등록한다
- **구분**: 생성 · **광고비·노출 영향**: 간접 — 검수 통과에 필요할 수 있음
- **공식 설명**: 서류내용 등록
- **공식 요약(summary)**: Document · 태그: 서류 관리-DocumentController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Ftool~2Fdocument>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `documents` | 본문 | ✔ | [Document[]](06-models.md#model-document) |  | documents |

**응답**: [Document[]](06-models.md#model-document) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /tool/document
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

[
  {}
]
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-087"></a>
### 87. 서류 파일 업로드

`POST /tool/file/upload{?data}`

- **쉬운 설명**: 심사용 서류 파일을 올린다
- **구분**: 생성 · **광고비·노출 영향**: 간접
- **공식 설명**: 파일 업로드
- **공식 요약(summary)**: Document · 태그: 서류 관리-DocumentController
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Ftool~2Ffile~2Fupload%7B%3Fdata%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `file` | 폼 | ✔ | file |  | file |
| `data` | 쿼리 | ✔ | string |  | data |

**응답**: [Document](06-models.md#model-document) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /tool/file/upload?data=<data>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-088"></a>
### 88. 노출 제한 IP 변경 이력

`GET /tool/ip-exclusion-histories{?page,rpp,searchStartDate,searchEndDate}`

- **쉬운 설명**: 노출 제한 IP를 바꾼 이력을 본다(명세에서 #hidden 표시)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 공식 자료에서 확인되지 않음
- **공식 요약(summary)**: 사용자 제한 IP 이력 · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fip-exclusion-histories%7B%3Fpage,rpp,searchStartDate,searchEndDate%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `page` | 쿼리 | ✔ | integer(int32) |  | page |
| `rpp` | 쿼리 | ✔ | integer(int32) |  | rpp |
| `searchStartDate` | 쿼리 | ✔ | string(date-time) |  | searchStartDate |
| `searchEndDate` | 쿼리 | ✔ | string(date-time) |  | searchEndDate |

**응답**: [IpExclusionHistory[]](06-models.md#model-ipexclusionhistory) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/ip-exclusion-histories?page=<page>&rpp=<rpp>&searchStartDate=<searchStartDate>&searchEndDate=<searchEndDate>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-089"></a>
### 89. 노출 제한 IP 목록

`GET /tool/ip-exclusions`

- **쉬운 설명**: 내 광고를 보지 못하게 막은 IP 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Get the registered restricted IP of user.
- **공식 요약(summary)**: get · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Ftool~2Fip-exclusions>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [IpExclusion[]](06-models.md#model-ipexclusion) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /tool/ip-exclusions
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-090"></a>
### 90. 노출 제한 IP 등록

`POST /tool/ip-exclusions`

- **쉬운 설명**: 특정 IP에 광고가 노출되지 않게 막는다(부정 클릭 방지)
- **구분**: 생성 · **광고비·노출 영향**: 있음 — 해당 IP 노출·클릭 차단
- **공식 설명**: Register the restrict IP of user.
- **공식 요약(summary)**: create · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Ftool~2Fip-exclusions>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ip` | 본문 | ✔ | [IpExclusion](06-models.md#model-ipexclusion) |  | ip |

**응답**: [IpExclusion](06-models.md#model-ipexclusion) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /tool/ip-exclusions
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-091"></a>
### 91. 노출 제한 IP 변경

`PUT /tool/ip-exclusions`

- **쉬운 설명**: 노출 제한 IP를 바꾼다
- **구분**: 변경 · **광고비·노출 영향**: 있음
- **공식 설명**: Register the restrict IP of user.
- **공식 요약(summary)**: update · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/PUT/~2Ftool~2Fip-exclusions>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ip` | 본문 | ✔ | [IpExclusion](06-models.md#model-ipexclusion) |  | ip |

**응답**: [IpExclusion](06-models.md#model-ipexclusion) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
PUT /tool/ip-exclusions
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(수정 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-092"></a>
### 92. 노출 제한 IP 1개 삭제

`DELETE /tool/ip-exclusions/{id}`

- **쉬운 설명**: 노출 제한 IP 하나를 풀어 준다
- **구분**: 삭제 · **광고비·노출 영향**: 있음 — 그 IP에 다시 노출
- **공식 설명**: Remove a restricted IP.
- **공식 요약(summary)**: delete · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Ftool~2Fip-exclusions~2F%7Bid%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 경로 | ✔ | integer(int64) |  | id |

**응답**: [IpExclusion](06-models.md#model-ipexclusion) (명세 응답 코드: 200, 401, 204, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /tool/ip-exclusions/<id>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-093"></a>
### 93. 노출 제한 IP 여러 개 삭제

`DELETE /tool/ip-exclusions{?ids}`

- **쉬운 설명**: 노출 제한 IP 여러 개를 풀어 준다
- **구분**: 삭제 · **광고비·노출 영향**: 있음
- **공식 설명**: Remove business IPs in id list.
- **공식 요약(summary)**: delete(by ids) · 태그: IpExclusion
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Ftool~2Fip-exclusions%7B%3Fids%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | integer(int64) 배열 |  | ids |

**응답**: No Content (명세 응답 코드: 401, 204, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /tool/ip-exclusions?ids=<ids>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 비즈머니(Billing)
원본: `assets/json/ncc-heroes-billing.json`

<a id="ep-094"></a>
### 94. 비즈머니 잔액 조회

`GET /billing/bizmoney`

- **쉬운 설명**: 광고비 충전금(비즈머니) 잔액과 잠금 상태를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Returns amount of bizmoney and a status of locks.
- **공식 요약(summary)**: get · 태그: Bizmoney
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fbilling~2Fbizmoney>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [Bizmoney](06-models.md#model-bizmoney) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /billing/bizmoney
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-095"></a>
### 95. 비즈머니 충전 내역

`GET /billing/bizmoney/histories/charge{?searchStartDt,searchEndDt}`

- **쉬운 설명**: 기간별 비즈머니 충전 내역을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: bizmoney charging history
- **공식 요약(summary)**: get(charge) · 태그: Bizmoney
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fbilling~2Fbizmoney~2Fhistories~2Fcharge%7B%3FsearchStartDt,searchEndDt%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `searchStartDt` | 쿼리 | ✔ | string |  | Period start date (KST, YYYYMMDD) |
| `searchEndDt` | 쿼리 | ✔ | string |  | Period end date (KST, YYYYMMDD) |

**응답**: [BillingHistoryForChargeApi[]](06-models.md#model-billinghistoryforchargeapi) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /billing/bizmoney/histories/charge?searchStartDt=<searchStartDt>&searchEndDt=<searchEndDt>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-096"></a>
### 96. 비즈머니 차감 내역

`GET /billing/bizmoney/histories/exhaust{?searchStartDt,searchEndDt}`

- **쉬운 설명**: 기간별 광고비로 빠져나간 비즈머니 내역을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: bizmoney deduction history
- **공식 요약(summary)**: get(exhaust) · 태그: Bizmoney
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fbilling~2Fbizmoney~2Fhistories~2Fexhaust%7B%3FsearchStartDt,searchEndDt%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `searchStartDt` | 쿼리 | ✔ | string |  | Period start date (KST, YYYYMMDD) |
| `searchEndDt` | 쿼리 | ✔ | string |  | Period end date (KST, YYYYMMDD) |

**응답**: [BillingStatActivityApi[]](06-models.md#model-billingstatactivityapi) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /billing/bizmoney/histories/exhaust?searchStartDt=<searchStartDt>&searchEndDt=<searchEndDt>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-097"></a>
### 97. 일별 비즈머니 현황

`GET /billing/bizmoney/histories/period{?searchStartDt,searchEndDt}`

- **쉬운 설명**: 날짜별 비즈머니 잔액·사용 현황을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Daily BizMoney Status
- **공식 요약(summary)**: get(period) · 태그: Bizmoney
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fbilling~2Fbizmoney~2Fhistories~2Fperiod%7B%3FsearchStartDt,searchEndDt%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `searchStartDt` | 쿼리 | ✔ | string |  | Period start date(KST, YYYYMMDD) |
| `searchEndDt` | 쿼리 | ✔ | string |  | Period end date(KST, YYYYMMDD) |

**응답**: [BillingStatAccountApi[]](06-models.md#model-billingstataccountapi) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /billing/bizmoney/histories/period?searchStartDt=<searchStartDt>&searchEndDt=<searchEndDt>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 광고 계정·관리 계정(AdAccounts·ManagerAccounts)
원본: `assets/json/atower.json`

<a id="ep-098"></a>
### 98. 내 광고 계정 목록

`GET /ad-accounts`

- **쉬운 설명**: 내가 구성원으로 들어가 있는 광고 계정 목록을 본다(2025-09 계정 통합 후)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 자신이 권한을 가진 (구성원으로 포함된) 광고계정 목록 조회 Retrieve a list of ad accounts in which you have access (as a member)
- **공식 요약(summary)**: list · 태그: AdAccounts
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fad-accounts>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `page` | 쿼리 |  | integer(int32) |  | 페이지네이션을 위한 페이지 번호 The page number for pagination |
| `size` | 쿼리 |  | integer(int32) |  | 페이지당 항목 수 (최대 1000개) The number of items per page (max 1000) |

**응답**: [AdAccountsResponse](06-models.md#model-adaccountsresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ad-accounts
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-099"></a>
### 99. 광고 계정 구성원 조회

`GET /ad-accounts/{adAccountNo}/members`

- **쉬운 설명**: 광고 계정 하나의 구성원(권한) 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 자신이 권한을 가진 특정 광고 계정의 구성원 조회 Returns a paginated list of members belonging to the specified ad account.
- **공식 요약(summary)**: Retrieve Ad Account Member List · 태그: AdAccounts
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fad-accounts~2F%7BadAccountNo%7D~2Fmembers>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `adAccountNo` | 경로 | ✔ | integer(int64) |  | 지정한 광고계정 번호 Ad Account Number |

**응답**: [AdAccountMember[]](06-models.md#model-adaccountmember) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ad-accounts/<adAccountNo>/members
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-100"></a>
### 100. 내 관리 계정 목록

`GET /manager-accounts`

- **쉬운 설명**: 내가 구성원인 관리 계정(대행사 등) 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 자신이 권한을 가진 (구성원으로 포함된) 관리 계정 목록 조회 Retrieve a list of manager accounts in which you have access (as a member)
- **공식 요약(summary)**: list · 태그: ManagerAccounts
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fmanager-accounts>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `page` | 쿼리 |  | integer(int32) |  | 페이지네이션을 위한 페이지 번호 The page number for pagination |
| `size` | 쿼리 |  | integer(int32) |  | 페이지당 항목 수 (최대 1000개) The number of items per page (max 1000) |

**응답**: [ManagerAccountsResponse](06-models.md#model-manageraccountsresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /manager-accounts
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-101"></a>
### 101. 관리 계정의 하위 광고 계정

`GET /manager-accounts/{managerAccountNo}/child-ad-accounts`

- **쉬운 설명**: 관리 계정 아래에서 관리할 수 있는 광고 계정 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 지정된 관리 계정에 속한 하위 광고 계정의 페이지네이션된 목록 Returns a paginated list of child ad accounts belonging to the specified manager account.
- **공식 요약(summary)**: Retrieve Child Ad Account List · 태그: ManagerAccounts
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fmanager-accounts~2F%7BmanagerAccountNo%7D~2Fchild-ad-accounts>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `managerAccountNo` | 경로 |  | integer(int32) |  | 지정한 관리계정 번호 managerAccount no |
| `page` | 쿼리 |  | integer(int32) |  | 페이지네이션을 위한 페이지 번호 The page number for pagination |
| `size` | 쿼리 |  | integer(int32) |  | 페이지당 항목 수 (최대 1000개) The number of items per page (max 1000) |

**응답**: [ChildAdAccountResponse](06-models.md#model-childadaccountresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /manager-accounts/<managerAccountNo>/child-ad-accounts
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 통계·대용량 보고서(Stat·StatReport)
원본: `assets/json/ncc-report.json`

<a id="ep-102"></a>
### 102. 대용량 보고서 작업 목록

`GET /stat-reports`

- **쉬운 설명**: 요청해 둔 대용량 성과 보고서 작업 목록을 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves all of the registered Report Jobs
- **공식 요약(summary)**: list · 태그: StatReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fstat-reports>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [ReportJobResponse[]](06-models.md#model-reportjobresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /stat-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-103"></a>
### 103. 대용량 보고서 요청

`POST /stat-reports`

- **쉬운 설명**: 하루 단위 상세 성과 보고서(TSV) 생성을 요청한다
- **구분**: 생성 · **광고비·노출 영향**: 없음
- **공식 설명**: Registers a Report Job
- **공식 요약(summary)**: create · 태그: StatReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fstat-reports>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `statReportJob` | 본문 | ✔ | [StatReportJob](06-models.md#model-statreportjob) |  | statReportJob |

**응답**: [ReportJobResponse](06-models.md#model-reportjobresponse) (명세 응답 코드: 200, 201, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /stat-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-104"></a>
### 104. 대용량 보고서 전체 삭제

`DELETE /stat-reports`

- **쉬운 설명**: 요청해 둔 대용량 보고서 작업을 모두 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 없음
- **공식 설명**: Delete Report Jobs
- **공식 요약(summary)**: delete · 태그: StatReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fstat-reports>

**파라미터**

없음(공통 인증 헤더만)

**응답**: No Content (명세 응답 코드: 401, 204, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /stat-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-105"></a>
### 105. 대용량 보고서 1개 조회

`GET /stat-reports/{reportJobId}`

- **쉬운 설명**: 보고서 작업 상태와 내려받기 주소를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves a registered Report Job
- **공식 요약(summary)**: get · 태그: StatReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fstat-reports~2F%7BreportJobId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `reportJobId` | 경로 | ✔ | ref |  | ID of a Report Job |

**응답**: [ReportJobResponse](06-models.md#model-reportjobresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /stat-reports/<reportJobId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-106"></a>
### 106. 대용량 보고서 1개 삭제

`DELETE /stat-reports/{reportJobId}`

- **쉬운 설명**: 보고서 작업 하나를 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 없음
- **공식 설명**: Deletes a Report Job
- **공식 요약(summary)**: delete · 태그: StatReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fstat-reports~2F%7BreportJobId%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `reportJobId` | 경로 | ✔ | ref |  | ID of a Report Job |

**응답**: No Content (명세 응답 코드: 401, 204, 403)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /stat-reports/<reportJobId>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-107"></a>
### 107. 성과 요약(1개 대상)

`GET /stats{?id,fields,timeRange,datePreset,timeIncrement,breakdown}`

- **쉬운 설명**: 캠페인·광고그룹·키워드·소재 하나의 노출·클릭·비용·전환 등을 기간별로 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Receive the Summary Report per single entity
- **공식 요약(summary)**: get (by id) · 태그: Stat
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fstats%7B%3Fid,fields,timeRange,datePreset,timeIncrement,breakdown%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 쿼리 | ✔ | string |  | Entity Id (campaign id, Ad group id, Ad keyword id, Ad id, Criterion id) |
| `fields` | 쿼리 | ✔ | string | impCnt, clkCnt, salesAmt, ctr, cpc, avgRnk, ccnt, recentAvgRnk, recentAvgCpc, pcNxAvgRnk, mblNxAvgRnk, crto, convAmt, ror, cpConv, viewCnt, purchaseCcnt, purchaseConvAmt, purchaseRor | Fields to be retrieved (JSON format string). For example, ["impCnt","clkCnt","salesAmt","crto"] |
| `timeRange` | 쿼리 |  | string |  | Hours of stats based on KST (JSON format string). This parameter is ignored if datePreset is provided For example, {"since":"YYYY-MM-DD","until":"YYYY-MM-DD"} |
| `datePreset` | 쿼리 |  | string | today, yesterday, last7days, last30days, lastweek, lastmonth, lastquarter | Predefined period of stats. This parameter is ignored if timeRange is provided |
| `timeIncrement` | 쿼리 |  | string | 1, allDays | Selection of daily aggregated stats(1) or summary stats(allDays). Default value is 1 |
| `breakdown` | 쿼리 |  | string | pcMblTp, dayw, hh24, regnNo | Stat classification type. Dose not support more than one breakdown. Default value is empty |

**응답**: [StatResponse](06-models.md#model-statresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /stats?id=<id>&fields=impCnt
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-108"></a>
### 108. 성과 요약(여러 대상)

`GET /stats{?ids,fields,timeRange,datePreset,timeIncrement,breakdown}`

- **쉬운 설명**: 여러 대상의 성과를 한 번에 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Receive the Summary Report per multiple entities
- **공식 요약(summary)**: get (by ids) · 태그: Stat
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fstats%7B%3Fids,fields,timeRange,datePreset,timeIncrement,breakdown%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `ids` | 쿼리 | ✔ | string |  | Entity Id List (campaign id, Ad group id, Ad keyword id, Ad id, Criterion id) |
| `fields` | 쿼리 | ✔ | string | impCnt, clkCnt, salesAmt, ctr, cpc, avgRnk, ccnt, recentAvgRnk, recentAvgCpc, pcNxAvgRnk, mblNxAvgRnk, crto, convAmt, ror, cpConv, viewCnt, purchaseCcnt, purchaseConvAmt, purchaseRor | Fields to be retrieved (JSON format string). For example, ["impCnt","clkCnt","salesAmt","crto"] |
| `timeRange` | 쿼리 |  | string |  | Hours of stats based on KST (JSON format string). This parameter is ignored if datePreset is provided For example, {"since":"YYYY-MM-DD","until":"YYYY-MM-DD"} |
| `datePreset` | 쿼리 |  | string | today, yesterday, last7days, last30days, lastweek, lastmonth, lastquarter | Predefined period of stats. This parameter is ignored if timeRange is provided |
| `timeIncrement` | 쿼리 |  | string | allDays | Selection of daily aggregated stats(1) or summary stats(allDays). Default value is allDays |
| `breakdown` | 쿼리 |  | string | pcMblTp, dayw, hh24, regnNo | Stat classification type. Dose not support more than one breakdown. Default value is empty |

**응답**: [StatResponse](06-models.md#model-statresponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /stats?ids=<ids>&fields=impCnt
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-109"></a>
### 109. 유형별 성과(1개 대상)

`GET /stats{?id,statType}`

- **쉬운 설명**: 정해진 통계 유형(statType)으로 대상 하나의 성과를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Receive the Customized Report per stat type and single entity
- **공식 요약(summary)**: get (by statType) · 태그: Stat
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fstats%7B%3Fid,statType%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 쿼리 | ✔ | string |  | Entity Id |
| `statType` | 쿼리 | ✔ | string |  | Predefined stat type. For example, NPLA_SCH_KEYWORD |

**응답**: [StatTypeResponse[]](06-models.md#model-stattyperesponse) (명세 응답 코드: 200, 401, 403, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /stats?id=<id>&statType=<statType>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 마스터 보고서(MasterReport)
원본: `assets/json/master-report.json`

<a id="ep-110"></a>
### 110. 마스터 보고서 작업 목록

`GET /master-reports`

- **쉬운 설명**: 요청해 둔 마스터 보고서(전체 광고 구조 파일) 작업 목록을 본다(최근 최대 100개)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Get all list of "Master Report" Jobs LIST (maximum 100 jobs) which recently created
- **공식 요약(summary)**: list · 태그: MasterReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fmaster-reports>

**파라미터**

없음(공통 인증 헤더만)

**응답**: [MasterReportJob[]](06-models.md#model-masterreportjob) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /master-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-111"></a>
### 111. 마스터 보고서 전체 삭제

`DELETE /master-reports`

- **쉬운 설명**: 마스터 보고서 작업을 모두 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 없음
- **공식 설명**: Delete all "Master Report" jobs.
- **공식 요약(summary)**: delete all · 태그: MasterReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fmaster-reports>

**파라미터**

없음(공통 인증 헤더만)

**응답**: response message (명세 응답 코드: 204, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /master-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-112"></a>
### 112. 마스터 보고서 요청

`POST /master-reports`

- **쉬운 설명**: 캠페인·광고그룹·키워드·소재 등 전체 구조를 파일로 받기 위한 작업을 만든다
- **구분**: 생성 · **광고비·노출 영향**: 없음
- **공식 설명**: Create "Master Report" job
- **공식 요약(summary)**: create · 태그: MasterReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fmaster-reports>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `Job` | 본문 |  | [RequestJob](06-models.md#model-requestjob) |  | "item" is mandatory parameter. "fromTime" is optional parameter. the others aren't required. "fromTime" is a specific period of time at starts (ISO 8601 UTC). If "fromTime" is input, the Delta master report is generated between "fromTime" and now. If "fromTime" is not input, the master report is generated without Delta data. |

**응답**: [MasterReportJob](06-models.md#model-masterreportjob) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /master-reports
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-113"></a>
### 113. 마스터 보고서 1개 삭제

`DELETE /master-reports/{id}`

- **쉬운 설명**: 마스터 보고서 작업 하나를 지운다
- **구분**: 삭제 · **광고비·노출 영향**: 없음
- **공식 설명**: Delete by "Master Report" job id.
- **공식 요약(summary)**: delete (by id) · 태그: MasterReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/DELETE/~2Fmaster-reports~2F%7Bid%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 경로 | ✔ | string |  | Valid Master Report Job Id |

**응답**: response message (명세 응답 코드: 204, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
DELETE /master-reports/<id>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-114"></a>
### 114. 마스터 보고서 1개 조회

`GET /master-reports/{id}`

- **쉬운 설명**: 마스터 보고서 작업 상태와 내려받기 주소를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Get a "Master Report" Job details by specific ID.
- **공식 요약(summary)**: get (by id) · 태그: MasterReport
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fmaster-reports~2F%7Bid%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 경로 | ✔ | string |  | Valid Master Report Job Id. |

**응답**: [MasterReportJob](06-models.md#model-masterreportjob) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /master-reports/<id>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 키워드 도구(RelKwdStat)
원본: `assets/json/ncc-keywordstool.json`

<a id="ep-115"></a>
### 115. 연관 키워드·검색량 조회

`GET /keywordstool`

- **쉬운 설명**: 힌트 키워드·사이트·업종·시즌으로 연관 키워드와 월간 검색수·클릭 지표를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: Retrieves related keywords and their statistical indicators by query parameters. To determine search types and conditions, a user requests data by combining at least one parameter among `business ID`, `ncc business channel ID`, `keyword hints`, `season`, `event ID` and by using several conditional parameters.
- **공식 요약(summary)**: list · 태그: RelKwdStat
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fkeywordstool>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `siteId` | 쿼리 |  | string |  | Buisness chanel ID(nccBusinessChannelId) restricted for site channel type (channelTp= “SITE”) |
| `biztpId` | 쿼리 |  | integer |  | Business type id |
| `hintKeywords` | 쿼리 |  | string |  | Keyword list for hint. The list delimiter is comma (e.g. 꽃배달,flower,화환,bouquet), up to 5 keywords could be listed. |
| `event` | 쿼리 |  | integer |  | Seasonal theme |
| `month` | 쿼리 |  | integer |  | Month (e.g. 12) |
| `showDetail` | 쿼리 |  | integer |  | Set `showDetail` = 1 to fetch detailed statistic information per each related keyword (query count, click count, CTR, competitiveness index, depth) as well as relavent keywords list. For fetching related keywords and monthly query count info only, set `showDetail` = 0. |

**응답**: [RelKwdStat[]](06-models.md#model-relkwdstat) (명세 응답 코드: 200)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /keywordstool
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 입찰가·성과 예측(Estimate)
원본: `assets/json/estimate.json`

<a id="ep-116"></a>
### 116. 순위별 평균 입찰가 예측(파워링크)

`POST /estimate/average-position-bid/{type}`

- **쉬운 설명**: 키워드를 몇 위에 올리려면 평균 얼마를 써야 했는지 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate bid by average position statistics.
- **공식 요약(summary)**: get (average position bid) · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Festimate~2Faverage-position-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `req` | 본문 | ✔ | [RequestWithPosition](06-models.md#model-requestwithposition) |  | requst `keyword` or `nccKeywordId` with expected `position` |

**응답**: [EstimateBidWithPostion](06-models.md#model-estimatebidwithpostion) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /estimate/average-position-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-117"></a>
### 117. 중간 입찰가 예측(파워링크)

`POST /estimate/median-bid/{type}`

- **쉬운 설명**: 키워드의 중간 입찰가를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate bid by median
- **공식 요약(summary)**: get (median bid) · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Festimate~2Fmedian-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `req` | 본문 | ✔ | [Request](06-models.md#model-request) |  | requst `keyword` or `nccKeywordId` |

**응답**: [EstimateBid](06-models.md#model-estimatebid) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /estimate/median-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-118"></a>
### 118. 최소 노출 입찰가 예측(파워링크)

`POST /estimate/exposure-minimum-bid/{type}`

- **쉬운 설명**: 키워드가 노출되려면 최소 얼마가 필요한지 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate the minimum bid is always exposure.
- **공식 요약(summary)**: get (exposure minimum bid) · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Festimate~2Fexposure-minimum-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `req` | 본문 | ✔ | [Request](06-models.md#model-request) |  | requst `keyword` or `nccKeywordId` |

**응답**: [EstimateBid](06-models.md#model-estimatebid) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /estimate/exposure-minimum-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-119"></a>
### 119. 입찰가별 성과 예측(파워링크)

`POST /estimate/performance/{type}`

- **쉬운 설명**: 입찰가를 이만큼 쓰면 노출·클릭·비용이 얼마나 될지 예측한다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate performance data by expect bid.
- **공식 요약(summary)**: get (performance) · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Festimate~2Fperformance~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `req` | 본문 | ✔ | [RequestPerformance](06-models.md#model-requestperformance) |  | requst `keyword` or `nccKeywordId` and bid array |

**응답**: [ResponsePerformance](06-models.md#model-responseperformance) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /estimate/performance/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-120"></a>
### 120. 입찰가별 성과 예측(여러 키워드)

`POST /estimate/performance-bulk`

- **쉬운 설명**: 여러 키워드·입찰가 조합의 예상 노출·클릭·비용을 한 번에 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate performance data by keyword and bid.
- **공식 요약(summary)**: get (performance-bulk) · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Festimate~2Fperformance-bulk>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `req` | 본문 | ✔ | [RequestPerformanceBulk](06-models.md#model-requestperformancebulk) |  | requst array of `keyword`,`bid`,`device` |

**응답**: [ResponsePerformanceBulk](06-models.md#model-responseperformancebulk) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /estimate/performance-bulk
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-121"></a>
### 121. 순위별 평균 입찰가 예측(쇼핑)

`POST /npla-estimate/average-position-bid/{type}`

- **쉬운 설명**: 쇼핑 상품소재를 몇 위에 올리려면 평균 얼마였는지 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate bid by average position statistics.
- **공식 요약(summary)**: get (average position bid) - NPLA · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fnpla-estimate~2Faverage-position-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, product | the type of keys. `id` means keys are Ad.nccAdId. `product` means keys are Ad.productId |
| `req` | 본문 | ✔ | [RequestWithPosition](06-models.md#model-requestwithposition) |  | requst `productId` or `nccAdId` with expected `position` |

**응답**: [NPLAEstimateBidByPosition](06-models.md#model-nplaestimatebidbyposition) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /npla-estimate/average-position-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-122"></a>
### 122. 최소 노출 입찰가 예측(쇼핑)

`POST /npla-estimate/exposure-minimum-bid/{type}`

- **쉬운 설명**: 쇼핑 상품소재 노출에 필요한 최소 입찰가를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate the minimum bid is always exposure.
- **공식 요약(summary)**: get (exposure minimum bid) - NPLA · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fnpla-estimate~2Fexposure-minimum-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, product | the type of keys. `id` means keys are Ad.nccAdId. `product` means keys are Ad.productId |
| `req` | 본문 | ✔ | [NPLARequest](06-models.md#model-nplarequest) |  | requst `product` or `nccAdId` |

**응답**: [NPLAEstimateBid](06-models.md#model-nplaestimatebid) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /npla-estimate/exposure-minimum-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-123"></a>
### 123. 순위별 평균 입찰가 예측(파워콘텐츠)

`POST /npc-estimate/average-position-bid/{type}`

- **쉬운 설명**: 파워콘텐츠 키워드 순위별 평균 입찰가를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate bid by average position statistics.
- **공식 요약(summary)**: get (average position bid) - NPC · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fnpc-estimate~2Faverage-position-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `payload` | 본문 | ✔ | [NpcRequestAveragePositionBid](06-models.md#model-npcrequestaveragepositionbid) |  | requst `keyword` or `nccKeywordId` with expected `position` |

**응답**: [NpcEstimateBid](06-models.md#model-npcestimatebid) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /npc-estimate/average-position-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-124"></a>
### 124. 최소 노출 입찰가 예측(파워콘텐츠)

`POST /npc-estimate/exposure-minimum-bid/{type}`

- **쉬운 설명**: 파워콘텐츠 노출에 필요한 최소 입찰가를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate the minimum bid is always exposure.
- **공식 요약(summary)**: get (exposure minimum bid) - NPC · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fnpc-estimate~2Fexposure-minimum-bid~2F%7Btype%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `type` | 경로 | ✔ | string | id, keyword | the type of keys. `id` means keys are AdKeyowrd.nccKeywordId. `keyword` means keys are AdKeyword.Keyword |
| `payload` | 본문 | ✔ | [NpcRequestMinMaxBid](06-models.md#model-npcrequestminmaxbid) |  | requst `keyword` or `nccKeywordId` |

**응답**: [NpcEstimateBid](06-models.md#model-npcestimatebid) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /npc-estimate/exposure-minimum-bid/<type>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-125"></a>
### 125. 성과 예측(파워콘텐츠)

`POST /npc-estimate/performance`

- **쉬운 설명**: 파워콘텐츠 키워드의 예상 성과를 본다
- **구분**: 조회 · **광고비·노출 영향**: 없음(예측만)
- **공식 설명**: estimate performance data by keyword.
- **공식 요약(summary)**: get (performance) - NPC · 태그: Estimate
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fnpc-estimate~2Fperformance>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `payload` | 본문 | ✔ | [NpcRequestPerformance](06-models.md#model-npcrequestperformance) |  | request `keyword` array, level and device |

**응답**: [NpcResponsePerformance](06-models.md#model-npcresponseperformance) (명세 응답 코드: 200, default)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /npc-estimate/performance
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더

{}
```
(본문 출처: 명세 필드로 만든 가상값(생성 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고))

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


## 검수 이력(InspectHistory)
원본: `assets/json/ncc-inspect-history.json`

<a id="ep-126"></a>
### 126. 검수 이력 여러 개 조회

`POST /ncc/inspect-history`

- **쉬운 설명**: 비즈채널·소재·확장소재·키워드의 검수 결과와 반려 사유를 최대 100개 본다(최근 3개월)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 여러건의 검수이력을 조회합니다. View multiple inspection histories.
- **공식 요약(summary)**: Inspection history inquiry · 태그: InspectHistory
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/POST/~2Fncc~2Finspect-history>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `[]` | 본문 | ✔ |  |  | 조회할 ID 목록 List of IDs to search Example(["id1","id2"]) |

**응답**: [InspectCommentResponse](06-models.md#model-inspectcommentresponse) (명세 응답 코드: 400, 200, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
POST /ncc/inspect-history
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고

<a id="ep-127"></a>
### 127. 검수 이력 1개 조회

`GET /ncc/inspect-history/{id}`

- **쉬운 설명**: 대상 하나의 검수 결과와 반려 사유를 본다(최근 3개월)
- **구분**: 조회 · **광고비·노출 영향**: 없음
- **공식 설명**: 특정 ID에 해당하는 검수이력을 조회합니다. View the inspection history corresponding to a specific ID.
- **공식 요약(summary)**: Inspection history single inquiry · 태그: InspectHistory
- **공식 문서**: <https://naver.github.io/searchad-apidoc/#/operations/GET/~2Fncc~2Finspect-history~2F%7Bid%7D>

**파라미터**

| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |
|---|---|---|---|---|---|
| `id` | 경로 | ✔ | string |  | 조회할 ID ID to search |

**응답**: [InspectCommentResponse](06-models.md#model-inspectcommentresponse) (명세 응답 코드: 400, 200, 404)

요청 예시(가상값, 공통 인증 헤더 생략):
```http
GET /ncc/inspect-history/<id>
X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더
```

응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고


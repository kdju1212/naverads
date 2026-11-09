# 요청·응답 모델(필드 표)

> 공식 명세 JSON의 definitions에서 자동으로 만들었다. 필수 열: ✔ = 명세 required, 생성/수정 = 설명의 `#required-create`/`#required-update`, 숨김 = `#hidden-*`(요청에 넣지 않는 값 등).

<a id="model-adextensionrequest"></a>
## AdExtensionRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adExtension` | [JsonNode](06-models.md#model-jsonnode) | 숨김:request |  | The creative of the AD extension The format of this value is JSON |
| `enable` | boolean | ✔ |  |  |
| `inspectRequestMsg` | string |  |  | The message of inspect when you requested to inspect this AD extension |
| `mobileChannelId` | string | 숨김:update 생성 |  | 확장 소재와 연결된 모바일 비즈채널의 고유 ID입니다. The unique ID of mobile Biz Channel which produces the creative |
| `nccAdExtensionId` | string | 숨김:create 수정 |  | The unique ID of the AD extension |
| `ownerId` | string | 숨김:update 생성 |  | 캠페인, 광고 그룹, 광고 소재등 확장 소재가 연결된 광고 Entity의 고유 ID입니다. The unique ID of owner entity which is either campaign or adgroup containing this AD extension |
| `pcChannelId` | string | 숨김:update 생성 |  | 확장 소재와 연결된 PC 비즈채널의 고유 ID입니다. The unique ID of PC Biz Channel which produces the creative |
| `periodEndDt` | string |  |  | 확장 소재의 노출 종료일입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. The date on which the AD extension ends. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-30T15:00:00.000Z). |
| `periodStartDt` | string |  |  | 확장 소재의 노출 시작일입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. The date on which the AD extension starts. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-01T15:00:00.000Z). |
| `preNccAdExtensionId` | string |  |  |  |
| `schedule` | [JsonNode](06-models.md#model-jsonnode) | 숨김:update 생성 |  | 확장 소재의 노출을 요일과 시간 별로 설정한 값입니다. 요일및 시간 계산은 https://github.com/naver/searchad-apidoc/wiki/FAQ 에서 확인할 수 있습니다. The schedule of the AD extension The format of this value is JSON - Every day and time : null - Partially applied : {"SUN":16777215,"MON":16777215,"TUE":16777215,"WED":16777215,"THU":16777215,"FRI":16777215,"SAT":16777215} - Each key is the day of week and value is the sum of bit operation wi |
| `type` | string | 숨김:update 생성 | PHONE, LOCATION, BOOKING, TALK, CALCULATION, HEADLINE, DESCRIPTION, SUB_LINKS, PRICE_LINKS, PROMOTION, SHOPPING_EXTRA, POWER_LINK_IMAGE, IMAGE_SUB_LINKS, PLACE, CATALOG_RELEASE_DATE, CATALOG_EXTRA, CATALOG_DETAIL, CATALOG_IMAGE, CATALOG_PROMOTION, CATALOG_EVENT, CATALOG_MOVIE, CATALOG_PURCHASE_CONDITION, CATALOG_BRAND_MESSAGE, NAVER_TV_VIDEO, NAVER_BLOG_REVIEW, SHOPPING_BRAND_VIDEO, SHOPPING_BRAND_IMAGE, SHOPPING_BRAND_BROADCAST, PLACE_SMART_ORDER, SHOPPING_BRAND_EVENT, PLACE_BEAUTY_STYLE, DESCRIPTION_EXTRA, SHOPPING_BRAND_DAY, SHOPPING_WEB, WEBSITE_INFO, TALKTALK_CONSULTATION | 확장 소재의 종류를 나타냅니다.(https://github.com/naver/searchad-apidoc/wiki/FAQ) "API를 이용하여 생성 불가능한 유형: \n- SHOPPING_EXTRA\n- CATALOG_EXTRA\n- CATALOG_EVENT\n- CATALOG_PURCHASE_CONDITION\n- SHOPPING_BRAND_BROADCAST\n- SHOPPING_BRAND_EVENT\n- PLACE_SMART_ORDER,NAVER_BLOG_REVIEW\n- POWER_LINK_IMAGE\n- IMAGE_SUB_LINKS\n- CATALOG_IMAGE\n- NAVER_TV_VIDEO\n- SHOPPING_BRAND_IMAGE\n- SHOPPING_BRAND_VIDEO\n "The type  |
| `usePeriod` | boolean |  |  | 노출 기간 설정 사용여부를 나타냅니다. true: 사용, false: 사용안함 use period. true: use, false: unuse If this field is blank, and then set to the default value(false). |
| `userLock` | boolean | 숨김:update 생성 |  | 확장 소재의 On/Off 노출 설정입니다. true일 경우 노출이 중지됩니다. false일 경우 노출이 가능합니다. This field can be used for ENABLED or PAUSED of the AD extension |

<a id="model-adextension"></a>
## AdExtension

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adExtension` | string |  |  | 확장 소재의 소재 데이터가 JSON 구조로 저장되어 있습니다. The creative of the AD extension The format of this value is JSON |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique ID of the customer |
| `editTm` | string |  |  | 최근 수정 시각 입니다. Recently modified time (RFC 3339 datetime) |
| `enable` | boolean | 숨김:request 숨김:response |  | 외부 데이터와 연결된 확장 소재의 경우 연결 상태를 나타냅니다. Enable or Pause this ad extension by the system. false:'DISABLED', true:'ENABLED'. |
| `inspectStatus` | string |  | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | 확장 소재의 검수 상태입니다. 검수상태는 아래의 값을 가질수 있습니다. The inspect status of the AD extension |
| `mobileChannelId` | string |  |  | 확장 소재와 연결된 모바일 비즈채널의 고유 ID입니다. The unique ID of mobile Biz Channel which produces the creative |
| `nccAdExtensionId` | string |  |  | 확장 소재의 고유 ID입니다. The unique ID of the AD extension |
| `ownerId` | string |  |  | 캠페인, 광고 그룹, 광고 소재등 확장 소재가 연결된 광고 Entity의 고유 ID입니다. The unique ID of owner entity which is either campaign or adgroup containing this AD extension |
| `pcChannelId` | string |  |  | 확장 소재와 연결된 PC 비즈채널의 고유 ID입니다. The unique ID of PC Biz Channel which produces the creative |
| `periodEndDt` | string |  |  | 확장 소재의 노출 종료일입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. The date on which the AD extension ends. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-30T15:00:00.000Z). |
| `periodStartDt` | string |  |  | 확장 소재의 노출 시작일입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. The date on which the AD extension starts. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-01T15:00:00.000Z). |
| `regTm` | string |  |  | 확장 소재가 등록된 시각입니다. Time that the AD extension has been registered (RFC 3339 datetime). |
| `schedule` | string | 생성 |  | 확장 소재의 노출을 요일과 시간 별로 설정한 값입니다. 요일및 시간 계산은 https://github.com/naver/searchad-apidoc/wiki/FAQ 에서 확인할 수 있습니다. The schedule of the AD extension The format of this value is JSON - Every day and time : null - Partially applied : {"SUN":16777215,"MON":16777215,"TUE":16777215,"WED":16777215,"THU":16777215,"FRI":16777215,"SAT":16777215} - Each key is the day of week and value is the sum of bit operation wi |
| `status` | string |  | ELIGIBLE, LIMITED_ELIGIBLE, PAUSED, DELETED | 확장 소재의 계산된 상태를 나타냅니다. 상태 값은 아래의 값중 하나를 가질 수 있습니다.(https://github.com/naver/searchad-apidoc/wiki/FAQ) Status of this AD extension |
| `statusReason` | string |  | ELIGIBLE, CAMPAIGN_DELETED, CAMPAIGN_PAUSED, CAMPAIGN_PENDING, CAMPAIGN_ENDED, CAMPAIGN_LIMITED_BY_BUDGET, CAMPAIGN_LIMITED_BY_SHARED_BUDGET, BUSINESS_CHANNEL_PAUSED, BUSINESS_CHANNEL_DISAPPROVED, BUSINESS_CHANNEL_UNDER_REVIEW, BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_APPROVED, PC_BUSINESS_CHANNEL_DISAPPROVED, PC_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_UNDER_REVIEW, MOBILE_BUSINESS_CHANNEL_APPROVED, MOBILE_BUSINESS_CHANNEL_DISAPPROVED, MOBILE_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, MOBILE_BUSINESS_CHANNEL_UNDER_REVIEW, GROUP_DELETED, GROUP_PAUSED, GROUP_LIMITED_BY_BUDGET, GROUP_LIMITED_BY_SHARED_BUDGET, GROUP_PAUSED_BY_INVALID_TARGET, KEYWORD_DELETED, KEYWORD_PAUSED, KEYWORD_DISAPPROVED, KEYWORD_DENIED, KEYWORD_UNDER_REVIEW, AD_DELETED, AD_PAUSED, AD_ABNORMAL_INTERLOCK, AD_DISAPPROVED, AD_UNDER_REVIEW, AD_NOT_ENOUGH_ASSETS, SHARED_BUDGET_LIMITED_BY_BUDGET, SHARED_BUDGET_DELETED, AD_EXTENSION_DELETED, AD_EXTENSION_PAUSED, AD_EXTENSION_NOT_SCHEDULED, AD_EXTENSION_DISAPPROVED, AD_EXTENSION_UNDER_REVIEW, AD_EXTENSION_PENDING, AD_EXTENSION_ABNORMAL_INTERLOCK, LACK_OF_ACCOUNT_BALANCE, REFUND_IN_PROGRESS, ENABLED, ASSET_DELETED, ASSET_DISAPPROVED, ASSET_UNDER_REVIEW | 확장 소재 상태에 대한 사유를 나타냅니다. 사유는 아래의 값중 하나를 가질 수 있습니다. Status reason of this AD extension.(https://github.com/naver/searchad-apidoc/wiki/FAQ) |
| `type` | string | 숨김:update 생성 | PHONE, LOCATION, BOOKING, TALK, CALCULATION, HEADLINE, DESCRIPTION, SUB_LINKS, PRICE_LINKS, PROMOTION, SHOPPING_EXTRA, POWER_LINK_IMAGE, IMAGE_SUB_LINKS, PLACE, CATALOG_RELEASE_DATE, CATALOG_EXTRA, CATALOG_DETAIL, CATALOG_IMAGE, CATALOG_PROMOTION, CATALOG_EVENT, CATALOG_MOVIE, CATALOG_PURCHASE_CONDITION, CATALOG_BRAND_MESSAGE, NAVER_TV_VIDEO, NAVER_BLOG_REVIEW, SHOPPING_BRAND_VIDEO, SHOPPING_BRAND_IMAGE, SHOPPING_BRAND_BROADCAST, PLACE_SMART_ORDER, SHOPPING_BRAND_EVENT, PLACE_BEAUTY_STYLE, DESCRIPTION_EXTRA, SHOPPING_BRAND_DAY, SHOPPING_WEB, WEBSITE_INFO, TALKTALK_CONSULTATION | 확장 소재의 종류를 나타냅니다.(https://github.com/naver/searchad-apidoc/wiki/FAQ) The type of the AD extension API를 이용하여 생성 불가능한 유형: - SHOPPING_EXTRA - CATALOG_EXTRA - CATALOG_EVENT - CATALOG_PURCHASE_CONDITION - SHOPPING_BRAND_BROADCAST - SHOPPING_BRAND_EVENT - PLACE_SMART_ORDER,NAVER_BLOG_REVIEW - POWER_LINK_IMAGE - IMAGE_SUB_LINKS - CATALOG_IMAGE - NAVER_TV_VIDEO - SHOPPING_BRAND_IMAGE - SHOPPING_BRAND_VIDE |
| `usePeriod` | boolean | 생성 |  | 노출 기간 설정 사용여부를 나타냅니다. true: 사용, false: 사용안함 use period. true: use, false: unuse If this field is blank, and then set to the default value(false). |
| `userLock` | boolean |  |  | 확장 소재의 On/Off 노출 설정입니다. true일 경우 노출이 중지됩니다. false일 경우 노출이 가능합니다. This field can be used for ENABLED or PAUSED of the AD extension |

<a id="model-adgrouprequest"></a>
## AdgroupRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adRollingType` | string |  | ROUND_ROBIN, PERFORMANCE | 광고 소재의 롤링 유형입니다. The rolled type of the creative. |
| `adgroupAttrJson` | [JsonNode](06-models.md#model-jsonnode) | 숨김:update |  | adgroup attribute json. The 'media' and 'templateId' properties are required if the campaign type is 'BRAND_SEARCH', and the 'media' property can have values 'PC' and 'MOBILE'. The 'contentsType' property is required if the campaign type is 'POWER_CONTENTS'. The 'contentsType' property can have the values 'INFORMATION' and 'PRODUCT'. |
| `adgroupType` | string |  | WEB_SITE, SHOPPING, INFORMATION, PRODUCT, BRAND_SEARCH, PLACE, CATALOG, BRAND_ZONE, SHOPPING_BRAND, LOCAL_AD, BRAND_NEW, DOOH | 광고그룹의 종류를 나타냅니다. The type of the adgroup. |
| `aiAdsOptIn` | boolean |  |  | ADVoost Max 설정입니다. 파워링크 + 확장검색을 사용하는 광고그룹만 설정할 수 있으며, 미지정 시 true로 처리됩니다. ADVoost Max setting. It can be set only for ad groups using PowerLink and Extended Search. (Default: true if not specified) |
| `autobidStrategy` | [AutobidStrategyRequest](06-models.md#model-autobidstrategyrequest) |  |  | 광고 그룹의 자동 입찰 전략입니다.. (쇼핑 검색 캠페인의 상품몰 유형만 유효합니다.) This is the automatic bidding strategy for ad groups. (Valid only for Shopping Search campaigns of the product mall type.) |
| `bidAmt` | integer(int32) | 수정 |  | 광고그룹의 키워드에 적용되는 입찰가를 나타냅니다. Max CPC (cost per click) bid. At the Ad group level, this represents the default bid applicable for keywords in this Ad Group. You can enter between 70 to 100000. When you create a new Ad Group, If this field is blank, and then set to the default value (70). |
| `contentsNetworkBidAmt` | integer(int32) | 수정 |  | 컨텐츠 네트워크 입찰가를 나타냅니다. Max CPC (cost per click) bid used in contents networks. You can enter between 70 to 100000. When you create a new Ad Group, If this field is blank, and then set to the default value.(70). This field isn't use to Adgroup of Shopping campaign type. |
| `contentsNetworkBidWeight` | integer(int32) | 수정 |  | 컨텐츠 네트워크 가중치 값을 나타냅니다. 기본 값은 사용안함입니다. 쇼핑 캠페인이외 다른 캠페인에서는 무시됩니다. Bids weights used in content networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100). |
| `customerId` | integer(int64) | 숨김:request 생성 |  | 광고 계정 고유 번호입니다. The unique ID of the customer. |
| `dailyBudget` | integer(int64) | 수정 |  | 광고 그룹의 하루 예산을 나타냅니다. The maximum budget of the use of the Ad Group during the day. You can enter between 70 to 1000000000. When you create a new Ad Group, If this field is blank, and then set to the default value.(0). |
| `expSearchBudgetRatio` | integer(int32) |  |  | 광고주가 설정하는 기존 예산 중 확장 검색 에 사용할 예산 비율.(기본: 100%) Percentage of the existing budget set by the advertiser to use for Extended Search (Default: 100%) |
| `keywordGroup` | string 배열 |  |  | Keyword Group For New Product Search Type |
| `keywordGroupCategoryId` | string |  |  | Keyword Group Category Id For New Product Search Type |
| `mobileChannelId` | string | 생성 |  | 모바일 비즈니스 채널의 고유 ID입니다. The unique ID of the mobile buisness channel containing this Ad Group. If necessary this ad group will need to enter the ID of the type of case belong to the campaign "SITE" type of channel type of web site, enter the ID of the channel type of case "MALL" type belonging to the shopping kind of campaign there is. |
| `mobileNetworkBidWeight` | integer(int32) | 수정 |  | 모바일 네트워크 가중치 값을 나타냅니다. Bids weights used in mobile networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100). |
| `name` | string | 생성 |  | 광고그룹의 이름입니다. Name of this Ad Group. This field is required and should not be null for ADD operations. |
| `nccAdgroupId` | string | 숨김:create 수정 |  | 광고그룹의 고유 ID입니다. The unique ID of this Ad Group |
| `nccCampaignId` | string | 생성 |  | 광고그룹이 속한 캠페인의 고유 ID입니다. The unique ID of the campaign with which this Ad Group is associated. |
| `nccProductGroupId` | string |  |  |  |
| `pcChannelId` | string | 생성 |  | PC 비즈니스 채널의 고유 ID입니다. The unique ID of the pc buisness channel containing this Ad Group. If necessary this ad group will need to enter the ID of the type of case belong to the campaign "SITE" type of channel type of web site, enter the ID of the channel type of case "MALL" type belonging to the shopping kind of campaign there is. |
| `pcNetworkBidWeight` | integer(int32) | 수정 |  | PC 네트워크 가중치 값을 나타냅니다. Bids weights used in PC networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100) |
| `sharedBudgetId` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 번호입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget ID in use. Null if you are not using shared budgets. |
| `sharedBudgetName` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 이름입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget name in use. Null if you are not using shared budgets. |
| `sharedDailyBudget` | integer(int64) |  |  | 광고그룹이 속한 공유예산의 하루예산입니다. Shared Daily budget |
| `sharedExpSearchBudgetRatio` | integer(int32) |  |  | 공유예산:광고주가 설정하는 기존 예산 중 확장 검색 에 사용할 예산 비율.(기본: 100%) Shared Budget: The percentage of existing budgets set by advertisers that will be used for Extended Search . (Default: 100%) |
| `systemBiddingType` | string |  | NONE, ML | 광고그룹의 자동입찰 속성을 나타냅니다. The type of adgroup system bidding. |
| `targets` | [TargetRequest[]](06-models.md#model-targetrequest) |  |  | 광고그룹의 타겟팅 정보를 나타냅니다. Each targeting information in the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default targetting |
| `useCntsNetworkBidAmt` | boolean | 수정 |  | 컨텐츠 네트워크 입찰가 사용 여부를 나타냅니다. Whether to use separate bids for the content network. When you create a new Ad Group, If this field is blank, and then set to the default value.(false). |
| `useCntsNetworkBidWeight` | boolean | 수정 |  | 컨텐츠 네트워크 입찰 가중치 사용여부를 나타냅니다. Whether to use separate bids for the content network. When you create a new Ad Group, If this field is blank, and then set to the default value.(false). |
| `useDailyBudget` | boolean | 수정 |  | 광고그룹의 하루 최대 예산을 사용할지 여부를 나타냅니다. Whether to use maximum budget of a day of the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default value.(false) |
| `useExpSearch` | boolean |  |  | 광고 그룹 테이블에 '확장 검색 사용 여부' 필드 USE_EXP_SEARCH 추가:1 : 사용, 0 : 사용 안 함 Add 'Enable Extended Search' field USE_EXP_SEARCH to the Advertising Group table 1:1:Enable, 0:Disable (Default: Enable) |
| `userLock` | boolean | 수정 |  | 광고그룹의 On/Off 노출 설정입니다. true일 경우 노출이 중지됩니다. false일 경우 노출이 가능합니다. This field can be used for ENABLED or PAUSED of the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default value.(false) |

<a id="model-adgroup"></a>
## Adgroup

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adRollingType` | string |  | ROUND_ROBIN, PERFORMANCE | 광고 소재의 롤링 유형입니다. The rolled type of the creative. |
| `adgroupAttrJson` | [JsonNode](06-models.md#model-jsonnode) | 숨김:update |  | 광고그룹 속성 Json 입니다. 애드그룹 속성 JSON. 캠페인 유형이 'BRAND_SEARCH'인 경우 'media' 및 'templateId' 속성이 필수이며, 'media' 속성에는 'PC' 및 'MOBILE' 값을 가질 수 있습니다. 캠페인 유형이 'POWER_CONTENTS'인 경우 'contentsType' 속성이 필요합니다. 'contentsType' 속성은 '정보' 및 '제품' 값을 가질 수 있습니다. adgroup attribute json. The 'media' and 'templateId' properties are required if the campaign type is 'BRAND_SEARCH', and the 'media' property can have values 'PC' an |
| `adgroupType` | string |  | WEB_SITE, SHOPPING, INFORMATION, PRODUCT, BRAND_SEARCH, PLACE, CATALOG, BRAND_ZONE, SHOPPING_BRAND, LOCAL_AD, BRAND_NEW, DOOH | 광고그룹의 종류를 나타냅니다. The type of the adgroup. |
| `aiAdsOptIn` | boolean |  |  | ADVoost Max 설정입니다. 파워링크 + 확장검색을 사용하는 광고그룹만 활성화할 수 있습니다. ADVoost Max setting. It can be enabled only for ad groups using PowerLink and Extended Search. |
| `autobidStrategy` | [AutobidStrategyRequest](06-models.md#model-autobidstrategyrequest) |  |  | 광고 그룹의 자동 입찰 전략입니다.. (쇼핑 검색 캠페인의 상품몰 유형만 유효합니다.) This is the automatic bidding strategy for ad groups. (Valid only for Shopping Search campaigns of the product mall type.) |
| `bidAmt` | integer(int32) |  |  | 광고그룹의 키워드에 적용되는 입찰가를 나타냅니다. Max CPC (cost per click) bid. At the Ad group level, this represents the default bid applicable for keywords in this Ad Group. You can enter between 70 to 100000. When you create a new Ad Group, If this field is blank, and then set to the default value (70). |
| `budgetLock` | boolean |  |  | 노출 잠김 여부입니다. Daily budget status of this AdGroup. |
| `contentsNetworkBidAmt` | integer(int32) | 수정 |  | 컨텐츠 네트워크 입찰가를 나타냅니다. Max CPC (cost per click) bid used in contents networks. You can enter between 70 to 100000. When you create a new Ad Group, If this field is blank, and then set to the default value.(70). This field isn't use to Adgroup of Shopping campaign type. |
| `contentsNetworkBidWeight` | integer(int32) | 수정 |  | 컨텐츠 네트워크 가중치 값을 나타냅니다. 기본 값은 사용안함입니다. 쇼핑 캠페인이외 다른 캠페인에서는 무시됩니다. Bids weights used in content networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100). |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique ID of the customer. |
| `dailyBudget` | integer(int64) | 수정 |  | 광고 그룹의 하루 예산을 나타냅니다. The maximum budget of the use of the Ad Group during the day. You can enter between 70 to 1000000000. When you create a new Ad Group, If this field is blank, and then set to the default value.(0). |
| `editTm` | string | 숨김:request |  | 광고 그룹 최근 수정 시각입니다. Recently modified time (RFC 3339 datetime). |
| `expSearchBudgetRatio` | integer(int32) |  |  | 광고주가 설정하는 기존 예산 중 확장 검색 에 사용할 예산 비율.(기본: 100%) Percentage of the existing budget set by the advertiser to use for Extended Search (Default: 100%) |
| `mobileChannelId` | string |  |  | 모바일 비즈니스 채널의 고유 ID입니다. The unique ID of the mobile buisness channel containing this Ad Group. If necessary this ad group will need to enter the ID of the type of case belong to the campaign "SITE" type of channel type of web site, enter the ID of the channel type of case "MALL" type belonging to the shopping kind of campaign there is. |
| `mobileNetworkBidWeight` | integer(int32) | 수정 |  | 모바일 네트워크 가중치 값을 나타냅니다. Bids weights used in mobile networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100). |
| `name` | string |  |  | 광고그룹의 이름입니다. Name of this Ad Group. This field is required and should not be null for ADD operations. |
| `nccAdgroupId` | string |  |  | 광고그룹의 고유 ID입니다. The unique ID of this Ad Group |
| `nccCampaignId` | string |  |  | 광고그룹이 속한 캠페인의 고유 ID입니다. The unique ID of the campaign with which this Ad Group is associated. |
| `numberInUse` | integer(int32) |  |  | 공유예산에 속한 광고 그룹의 개수입니다. Number of entities using the shared budget |
| `pcChannelId` | string |  |  | PC 비즈니스 채널의 고유 ID입니다. The unique ID of the pc buisness channel containing this Ad Group. If necessary this ad group will need to enter the ID of the type of case belong to the campaign "SITE" type of channel type of web site, enter the ID of the channel type of case "MALL" type belonging to the shopping kind of campaign there is. |
| `pcNetworkBidWeight` | integer(int32) | 수정 |  | PC 네트워크 가중치 값을 나타냅니다. Bids weights used in PC networks. You can enter between 10 to 500. When you create a new Ad Group, If this field is blank, and then set to the default value.(100) |
| `productGroup` | [ProductGroup](06-models.md#model-productgroup) |  |  | Bundle unit for managing Naver shopping-linked products to be exposed along with the material |
| `regTm` | string | 숨김:request |  | 광고그룹 등록 시각입니다. Time that the Ad Group has been created. (RFC 3339 datetime). |
| `sharedBudgetExpectCost` | integer(int64) |  |  | 광고그룹이 속한 공유예산의 예상 과금액입니다. Expected cost of the shared budget |
| `sharedBudgetId` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 번호입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget ID in use. Null if you are not using shared budgets. |
| `sharedBudgetLock` | boolean |  |  | 광고그룹이 속한 공유예산의 잠김 여부입니다. Whether the shared budget is locked or not |
| `sharedBudgetName` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 이름입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget name in use. Null if you are not using shared budgets. |
| `sharedDailyBudget` | integer(int64) |  |  | 광고그룹이 속한 공유예산의 하루예산입니다. Shared Daily budget |
| `sharedExpSearchBudgetRatio` | integer(int32) |  |  | 공유예산:광고주가 설정하는 기존 예산 중 확장 검색 에 사용할 예산 비율.(기본: 100%) Shared Budget: The percentage of existing budgets set by advertisers that will be used for Extended Search . (Default: 100%) |
| `status` | string | 숨김:request | ELIGIBLE, LIMITED_ELIGIBLE, PAUSED, DELETED | 광고그룹의 상태를 나타냅니다. Status of this Ad Group |
| `statusReason` | string | 숨김:request | CAMPAIGN_PAUSED, CAMPAIGN_PENDING, CAMPAIGN_ENDED, CAMPAIGN_LIMITED_BY_BUDGET, BUSINESS_CHANNEL_PAUSED, BUSINESS_CHANNEL_DISAPPROVED, BUSINESS_CHANNEL_UNDER_REVIEW, PC_BUSINESS_CHANNEL_APPROVED, PC_BUSINESS_CHANNEL_DISAPPROVED, PC_BUSINESS_CHANNEL_UNDER_REVIEW, MOBILE_BUSINESS_CHANNEL_APPROVED, MOBILE_BUSINESS_CHANNEL_DISAPPROVED, MOBILE_BUSINESS_CHANNEL_UNDER_REVIEW, GROUP_DELETED, GROUP_PAUSED, GROUP_LIMITED_BY_BUDGET | 광고그룹의 상태에 대한 원인을 나타냅니다. Status reason of this Ad Group |
| `systemBiddingType` | string |  | NONE, ML | 광고그룹의 자동입찰 속성을 나타냅니다. The type of adgroup system bidding. |
| `targets` | [Target[]](06-models.md#model-target) |  |  | 광고그룹의 타겟팅 정보를 나타냅니다. Each targeting information in the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default targetting |
| `useCntsNetworkBidAmt` | boolean | 수정 |  | 컨텐츠 네트워크 입찰가 사용 여부를 나타냅니다. Whether to use separate bids for the content network. When you create a new Ad Group, If this field is blank, and then set to the default value.(false). This field isn't use to Adgroup of Shopping campaign type. |
| `useCntsNetworkBidWeight` | boolean | 수정 |  | 컨텐츠 네트워크 입찰 가중치 사용여부를 나타냅니다. Whether to use separate bids for the content network. When you create a new Ad Group, If this field is blank, and then set to the default value.(false). |
| `useDailyBudget` | boolean | 수정 |  | 광고그룹의 하루 최대 예산을 사용할지 여부를 나타냅니다. Whether to use maximum budget of a day of the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default value.(false) |
| `useExpSearch` | boolean |  |  | 광고 그룹 테이블에 '확장 검색 사용 여부' 필드 USE_EXP_SEARCH 추가:1 : 사용, 0 : 사용 안 함 Add 'Enable Extended Search' field USE_EXP_SEARCH to the Advertising Group table 1:1:Enable, 0:Disable (Default: Enable) |
| `userLock` | boolean |  |  | 광고그룹의 On/Off 노출 설정입니다. true일 경우 노출이 중지됩니다. false일 경우 노출이 가능합니다. This field can be used for ENABLED or PAUSED of the Ad Group. When you create a new Ad Group, If this field is blank, and then set to the default value.(false) |

<a id="model-adgrouprestrictkwd"></a>
## AdgroupRestrictKwd

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `delFlag` | boolean | 숨김:request 숨김:response |  | When you create a new keyword, If this field is blank, and then set to the default value(false). |
| `description` | string |  |  | Description of the keyword |
| `keyword` | string |  |  | Impression-restricted keyword |
| `nccAdgroupId` | string | 숨김:create delete |  | The unique ID of this Ad Group |
| `nccAdgroupRestrictKwdId` | string | 숨김:create delete |  | The unique ID of this impression-restricted keyword |
| `regTm` | string | 숨김:request |  | Time that the keyword has been created. |
| `resultStatus` | [ResultStatus](06-models.md#model-resultstatus) | 숨김:request 숨김:uri |  | Registration Result Infomation |
| `type` | string |  | KEYWORD_PLUS_RESTRICT, EXP_SEARCH | Type of the keyword. default value is 'KEYWORD_PLUS_RESTRICT' |

<a id="model-adrequest"></a>
## AdRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `ad` | [JsonNode](06-models.md#model-jsonnode) | 숨김:update 생성 |  | Creative of this instance. This creative's json schema formed by the field 'type'. |
| `adAttr` | [JsonNode](06-models.md#model-jsonnode) | 숨김:create 숨김:response 수정 |  | Bid infomation of this instance. (Required if Shopping Ad) |
| `assets` | [AdAssetRequest[]](06-models.md#model-adassetrequest) |  |  | Ad assets, used only for RSA_AD type. |
| `customerId` | integer(int64) | 숨김:request |  | The id of the customer containing this ad. |
| `nccAdId` | string | 숨김:create 수정 |  | The id of this ad. |
| `nccAdgroupId` | string | 숨김:update 생성 |  | The id of the adgroup containing this ad. |
| `type` | string | 숨김:update 생성 | TEXT_45, SHOPPING_PRODUCT_AD, CONTENTS_AD_INFORMATION, CONTENTS_AD_PRODUCT, BRAND_SEARCH_AD, PLACE_AD, CATALOG_AD, SHOPPING_BRAND_AD, LOCAL_AD, SHOPPING_BRAND_IMAGE_THUMBNAIL_AD, SHOPPING_BRAND_IMAGE_BANNER_AD, BRAND_SEARCH_NEW_AD, RSA_AD, MEDICAL_AD, DOOH_AD, ADVOOST_PLACE_AD | Type of this ad (defined by json-schema form). |
| `userLock` | boolean |  |  | Enable or Pause this ad by the user. 0:'ENABLED', 1:'PAUSED'. |

<a id="model-ad"></a>
## Ad

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `ad` | string | 숨김:update 생성 |  | Creative of this instance. This creative's json schema formed by the field 'type'. |
| `adAttr` | string | 숨김:create 숨김:response 수정 |  | Bid infomation of this instance. (Required if Shopping Ad) |
| `assets` | [AdAssetResponse[]](06-models.md#model-adassetresponse) |  |  | Ad assets, used only for RSA_AD type. |
| `customerId` | integer(int64) | 숨김:request |  | The id of the customer containing this ad. |
| `editTm` | string | 숨김:create 숨김:request |  | The lastest time when this ad was modified (RFC 3339 datetime). |
| `enable` | boolean | 숨김:request 숨김:response |  | Enable or Pause this ad by the system. 0:'DISABLED', 1:'ENABLED'. |
| `inspectStatus` | string | 숨김:create 숨김:request | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | The approval status of this ad. 10:UNDER_REVIEW, 20:APPROVED, 30:PENDING, 40:DISAPPROVED |
| `nccAdId` | string | 숨김:create 수정 |  | The id of this ad. |
| `nccAdgroupId` | string | 숨김:update 생성 |  | The id of the adgroup containing this ad. |
| `nccQi` | [NccNewQi](06-models.md#model-nccnewqi) | 숨김:create 숨김:request |  | Quality index of SHOPPING_PRODUCT_AD/CATALOG_AD. 1 ~ 7 |
| `regTm` | string | 숨김:create 숨김:request |  | The time when this ad was created (RFC 3339 datetime). |
| `status` | string | 숨김:create 숨김:request | ELIGIBLE, LIMITED_ELIGIBLE, PAUSED, DELETED | Status of this ad. |
| `statusReason` | string | 숨김:create 숨김:request | ELIGIBLE, CAMPAIGN_DELETED, CAMPAIGN_PAUSED, CAMPAIGN_PENDING, CAMPAIGN_ENDED, CAMPAIGN_LIMITED_BY_BUDGET, CAMPAIGN_LIMITED_BY_SHARED_BUDGET, BUSINESS_CHANNEL_PAUSED, BUSINESS_CHANNEL_DISAPPROVED, BUSINESS_CHANNEL_UNDER_REVIEW, BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_APPROVED, PC_BUSINESS_CHANNEL_DISAPPROVED, PC_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_UNDER_REVIEW, MOBILE_BUSINESS_CHANNEL_APPROVED, MOBILE_BUSINESS_CHANNEL_DISAPPROVED, MOBILE_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, MOBILE_BUSINESS_CHANNEL_UNDER_REVIEW, GROUP_DELETED, GROUP_PAUSED, GROUP_LIMITED_BY_BUDGET, GROUP_LIMITED_BY_SHARED_BUDGET, GROUP_PAUSED_BY_INVALID_TARGET, KEYWORD_DELETED, KEYWORD_PAUSED, KEYWORD_DISAPPROVED, KEYWORD_DENIED, KEYWORD_UNDER_REVIEW, AD_DELETED, AD_PAUSED, AD_ABNORMAL_INTERLOCK, AD_DISAPPROVED, AD_UNDER_REVIEW, AD_NOT_ENOUGH_ASSETS, SHARED_BUDGET_LIMITED_BY_BUDGET, SHARED_BUDGET_DELETED, AD_EXTENSION_DELETED, AD_EXTENSION_PAUSED, AD_EXTENSION_NOT_SCHEDULED, AD_EXTENSION_DISAPPROVED, AD_EXTENSION_UNDER_REVIEW, AD_EXTENSION_PENDING, AD_EXTENSION_ABNORMAL_INTERLOCK, LACK_OF_ACCOUNT_BALANCE, REFUND_IN_PROGRESS, ENABLED, ASSET_DELETED, ASSET_DISAPPROVED, ASSET_UNDER_REVIEW | Status reason of this ad. |
| `type` | string | 숨김:update 생성 | TEXT_45, SHOPPING_PRODUCT_AD, CONTENTS_AD_INFORMATION, CONTENTS_AD_PRODUCT, BRAND_SEARCH_AD, PLACE_AD, CATALOG_AD, SHOPPING_BRAND_AD, LOCAL_AD, SHOPPING_BRAND_IMAGE_THUMBNAIL_AD, SHOPPING_BRAND_IMAGE_BANNER_AD, BRAND_SEARCH_NEW_AD, RSA_AD, MEDICAL_AD, DOOH_AD, ADVOOST_PLACE_AD | Type of this ad (defined by json-schema form). |
| `userLock` | boolean |  |  | Enable or Pause this ad by the user. 0:'ENABLED', 1:'PAUSED'. |

<a id="model-brandnewcontract"></a>
## BrandNewContract

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adgroupName` | string |  |  | 광고 그룹명 Name of the adgroup containing this time contract |
| `adgroupTemplateName` | string | 숨김:request 숨김:response |  | 광고 그룹 템플릿명 Template Name of the adgroup containing this time contract |
| `bidAmt` | integer(int32) |  |  | 입찰 금액 The bid amount of time contract |
| `biddingRound` | string |  |  | 입찰 라운드 The bidding round of time contract |
| `biddingStatus` | string |  | BIDDING, CONTRACTED, DEFEATED, BILLING, CANCELED, BILLING_DEFEATED, REBIDDING, FAILED_OCCUPATION | 입찰 상태 The bidding status of time contract |
| `brandNewContractId` | string |  |  | 계약 ID The unique ID of the time contract |
| `cancelCustomerId` | integer(int64) |  |  | 계약 취소자 계정 Id The customer number of canceling time contract. |
| `cancelLoginId` | string |  |  | 계약 취소자 회원 Id The login ID of canceling time contract. |
| `cancelTm` | string |  |  | 계약 취소 일시 The date-time of canceling time contract. |
| `contractAmt` | integer(int32) |  |  | 계약 금액 The contract amount of time contract |
| `contractCustomerId` | integer(int64) |  |  | 계약자 계정 Id The customer number of creating time contract. |
| `contractEndDt` | string |  |  | 계약 종료일 The time at which the time contract ends (RFC 3339 date-time). |
| `contractLoginId` | string |  |  | 계약자 회원 Id The login ID of creating time contract. |
| `contractName` | string |  |  | 계약명 The name of time contract |
| `contractStartDt` | string |  |  | 계약 시작일 The time at which the time contract ends (RFC 3339 date-time). |
| `contractStatus` | string |  | BIDDING, DEFEATED, BILLING, UPCOMING_EXPOSE, ON_EXPOSING, CANCELED_ON_BIDDING, CANCELED_BEFORE_EXPOSING, CANCELED_ON_EXPOSING, EXPOSE_COMPLETED, BILLING_DEFEATED, FAILED_CONTRACT, REBIDDING | 계약 상태 The contract status of time contract |
| `customerId` | integer(int64) |  |  | 광고주 ID The unique ID of the customer |
| `editTm` | string |  |  | 수정 일시 Time that the AD extension has been last modified (RFC 3339 datetime). |
| `exposureEndDt` | string |  |  | 노출 종료 일시 The end date-time of ad exposure |
| `exposureStartDt` | string |  |  | 노출 시작 일시 The start date-time of ad exposure |
| `keywordGroupCategoryName` | string |  |  | 키워드 그룹 카테고리 명 The name of keyword group category |
| `nccAdgroupId` | string |  |  | 광고 그룹 ID The unique ID of the adgroup containing this time contract |
| `paymentAmt` | integer(int32) |  |  | 결제 금액 The payment amount of time contract |
| `refundAmt` | integer(int32) |  |  | 환불 금액 The refund amount of time contract |
| `regTm` | string |  |  | 등록 일시 Time that the AD extension has been registered (RFC 3339 datetime). |
| `winningBidDt` | string |  |  | 낙찰 일시 The date-time of winning bid |

<a id="model-campaignrequest"></a>
## CampaignRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `campaignTp` | string | 숨김:update 생성 | WEB_SITE, SHOPPING, POWER_CONTENTS, BRAND_SEARCH, PLACE | campaignTp의 종류입니다. 유효한 값 목록은 다음과 같습니다. The type for the campaign. |
| `customerId` | integer(int64) | 생성 |  | 광고 계정 고유 번호입니다. 캠페인 생성시 필수 입력값입니다. The unique ID of the customer |
| `dailyBudget` | integer(int64) | 숨김:update |  | 캠페인에 설정된 하루 예산 최대값입니다. 'useDailyBudget' 값이 true일 경우에만 하루 예산이 적용됩니다. 광고주가 설정하지 않을 경우 기본값 0이 저장됩니다. The maximum budget of the use of the campaign during the day. If this field is blank, and then set to the default value.(0). |
| `deliveryMethod` | string | 숨김:update | ACCELERATED, STANDARD | 하루 예산을 이용하여 광고를 송출하는 방법을 나타냅니다. 기본 값은 빠른 소진(ACCELERATED) 이며, 균등 소진을 원할 경우 'STANDARD' 값을 입력 합니다. choosing 'Accelerated' or 'Standard' ad delivery. The default value is 'ACCELERATED'. Available values are 'ACCELERATED', 'STANDARD' |
| `name` | string | 숨김:update 생성 |  | 캠페인의 이름입니다. 캠페인 생성시 경우 필수 입력되어야 합니다. Name of this campaign. This field is required and should not be null for ADD operations. |
| `nccCampaignId` | string | 숨김:create 수정 |  | 캠페인의 고유 식별자 입니다. The unique ID of the campaign |
| `periodEndDt` | string |  |  | 캠페인 노출이 종료되는 날짜입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. 'usePeriod' 값이 true일 경우에만 유효합니다. The date on which the campaign ends. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-30T15:00:00.000Z). Valid only when usePeriod is true. |
| `periodStartDt` | string |  |  | 캠페인 노출이 시작되는 날짜입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. 'usePeriod' 값이 true일 경우에만 유효합니다. The date on which the campaign starts. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-01T15:00:00.000Z). Valid only when usePeriod is true. |
| `sharedBudgetDeliveryMethod` | string |  | ACCELERATED, STANDARD | 공유 예산을 사용하여 광고를 송출하는 방식입니다. 기본값은 빠른 소진(ACCELERATED) 이며 균등 소진은 'STANDARD' 입니다. How ads are served using the shared budget. The default is 'ACCELERATED' for accelerated distribution and 'STANDARD' for even distribution.(ACCELERATED (1), STANDARD(2)) |
| `sharedBudgetId` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 번호입니다. 공유 예산을 사용하지 않으면 null 값입니다. If using shared budget, the shared budget ID in use. Null if you are not using shared budgets. |
| `sharedBudgetName` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 이름입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget name in use. Null if you are not using shared budgets. |
| `sharedDailyBudget` | integer(int64) |  |  | 공유 예산을 사용할 경우 설정된 공유 예산의 최대 금액입니다. Shared Daily budget |
| `trackingMode` | string |  | TRACKING_DISABLED, AUTO_TRACKING_MODE, PASS_THROUGH_SITE_MODE | 캠페인의 추적 기능 설정을 나타냅니다. The type of the conversion tracking. Available values are 'TRACKING_DISABLED', 'AUTO_TRACKING_MODE', 'PASS_THROUGH_SITE_MODE'. If this field is blank, and then set to the default value(TRACKING_DISABLED). |
| `trackingUrl` | string |  |  | 캠페인의 추적 기능 설정이 '추적 경유 사이트(PASS_THROUGH_SITE_MODE)'일 때 중간 경유할 URL입니다. The value which indicates an URL of the intermediate site used by customer for the purpose of conversion tracking. |
| `trackingUrlCustomParams` | [JsonNode](06-models.md#model-jsonnode) |  |  | 캠페인의 URL 파라미터 값 변경 기능입니다. Tracking url custom parameter |
| `useDailyBudget` | boolean | 숨김:update |  | 하루 예산 사용 여부를 나타냅니다. 기본값은 false입니다. Whether to use maximum budget of a day of the campaign. If this field is blank, and then set to the default value.(false) true: use, false: unuse |
| `usePeriod` | boolean |  |  | 캠페인의 노출기간 설정 여부입니다. 노출 기간을 설정할 경우 true입니다. 노출 기간 설정시 시작일(periodStartDt), 종료일(periodEndDt)도 같이 설정하여야 합니다. use period. true: use, false: unuse If this field is blank, and then set to the default value(false). |
| `userLock` | boolean | 수정 |  | 캠페인의 On/Off 설정입니다. 노출을 중지할 경우 true 값을 가집니다. This field can be used for ENABLED or PAUSED of the campaign. When you create a new campaign, If this field is blank, and then set to the default value.(false) |

<a id="model-campaign"></a>
## Campaign

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `campaignTp` | string | 숨김:update 생성 | WEB_SITE, SHOPPING, POWER_CONTENTS, BRAND_SEARCH, PLACE | campaignTp의 종류입니다. 유효한 값 목록은 다음과 같습니다 The type for the campaign. |
| `customerId` | integer(int64) | 숨김:request 생성 수정 |  | 광고 계정 고유 번호입니다. 캠페인 생성/수정시 필수 입력값입니다. The unique ID of the customer |
| `dailyBudget` | integer(int64) | 숨김:update |  | 캠페인에 설정된 하루 예산 최대값입니다. 'useDailyBudget' 값이 true일 경우에만 하루 예산이 적용됩니다. 광고주가 설정하지 않을 경우 기본값 0이 저장됩니다. The maximum budget of the use of the campaign during the day. If this field is blank, and then set to the default value.(0). |
| `deliveryMethod` | string | 숨김:update | ACCELERATED, STANDARD | 하루 예산을 이용하여 광고를 송출하는 방법을 나타냅니다. 기본 값은 빠른 소진(ACCELERATED) 이며, 균등 소진을 원할 경우 'STANDARD' 값을 입력 합니다. choosing 'Accelerated' or 'Standard' ad delivery. The default value is 'ACCELERATED'. Available values are 'ACCELERATED', 'STANDARD' |
| `editTm` | string | 숨김:request |  | 최근 수정 시각 Recently modified time (RFC 3339 datetime). |
| `name` | string | 숨김:update 생성 |  | 캠페인의 이름입니다. 캠페인 생성시 경우 필수 입력되어야 합니다. Name of this campaign. This field is required and should not be null for ADD operations. |
| `nccCampaignId` | string | 숨김:create 수정 |  | 캠페인의 고유 식별자 입니다. The unique ID of the campaign |
| `numberInUse` | integer(int32) |  |  |  |
| `periodEndDt` | string | 숨김:update |  | 캠페인 노출이 종료되는 날짜입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. 'usePeriod' 값이 true일 경우에만 유효합니다. The date on which the campaign ends. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-30T15:00:00.000Z). Valid only when usePeriod is true. |
| `periodStartDt` | string | 숨김:update |  | 캠페인 노출이 시작되는 날짜입니다. UTC 기준으로 한국시간(KST) 자정에 해당하는 값(예: T15:00:00.000Z)만 허용됩니다. 'usePeriod' 값이 true일 경우에만 유효합니다. The date on which the campaign starts. The time component must be UTC midnight of Korea Standard Time (KST) — i.e. T15:00:00.000Z (e.g. 2026-06-01T15:00:00.000Z). Valid only when usePeriod is true. |
| `regTm` | string | 숨김:request |  | 캠페인이 생성된 시각을 나타냅니다. The time at which the campaign was created (RFC 3339 date-time). |
| `sharedBudgetDeliveryMethod` | string | 숨김:update | ACCELERATED, STANDARD | 공유 예산을 사용하여 광고를 송출하는 방식입니다. 기본값은 빠른 소진(ACCELERATED) 이며 균등 소진은 'STANDARD' 입니다. How ads are served using the shared budget. The default is 'ACCELERATED' for accelerated distribution and 'STANDARD' for even distribution.(ACCELERATED (1), STANDARD(2)) |
| `sharedBudgetExpectCost` | integer(int64) | 숨김:update |  | 공유 예산을 사용할 경우 공유 예산에서 차감될 예상 과금액을 나타냅니다. Expected cost of the shared budget |
| `sharedBudgetId` | string |  |  | 공유 예산을 사용할 경우 사용중인 공유 예산 번호입니다. 공유 예산을 사용하지 않으면 null 값입니다. If using shared budget, the shared budget ID in use. Null if you are not using shared budgets. |
| `sharedBudgetLock` | boolean |  |  | 공유 예산이 부족하여 노출이 중지된 경우 'true' 로 설정됩니다. Whether the shared budget is locked or not |
| `sharedBudgetName` | string | 숨김:update |  | 공유 예산을 사용할 경우 사용중인 공유 예산 이름입니다. 공유 예산을 사용하지 않으면 null값입니다. If using shared budget, the shared budget name in use. Null if you are not using shared budgets. |
| `sharedDailyBudget` | integer(int64) | 숨김:update |  | 공유 예산을 사용할 경우 설정된 공유 예산의 최대 금액입니다. Shared Daily budget |
| `status` | string | 숨김:request | ELIGIBLE, PAUSED, DELETED | 캠페인 계산된 상태를 나타냅니다. 상태 값은 아래의 값중 하나를 가질 수 있습니다.(https://github.com/naver/searchad-apidoc/wiki/FAQ) Status of this campaign |
| `statusReason` | string | 숨김:request | CAMPAIGN_PAUSED, CAMPAIGN_PENDING, CAMPAIGN_ENDED, CAMPAIGN_LIMITED_BY_BUDGET | 캠페인 상태에 대한 이유를 나타냅니다. 이유는 아래의 값중 하나를 가질 수 있습니다. Status reason of this campaign |
| `trackingMode` | string | 숨김:update | TRACKING_DISABLED, AUTO_TRACKING_MODE, PASS_THROUGH_SITE_MODE | 캠페인의 추적 기능 설정을 나타냅니다. The type of the conversion tracking. Available values are 'TRACKING_DISABLED', 'AUTO_TRACKING_MODE', 'PASS_THROUGH_SITE_MODE'. If this field is blank, and then set to the default value(TRACKING_DISABLED). |
| `trackingUrl` | string | 숨김:update |  | 캠페인의 추적 기능 설정이 '추적 경유 사이트(PASS_THROUGH_SITE_MODE)'일 때 중간 경유할 URL입니다. The value which indicates an URL of the intermediate site used by customer for the purpose of conversion tracking. |
| `trackingUrlCustomParams` | string |  |  | 캠페인의 URL 파라미터 값 변경 기능입니다. Tracking url custom parameter |
| `useDailyBudget` | boolean | 숨김:update |  | 하루 예산 사용 여부를 나타냅니다. 기본값은 false입니다. Whether to use maximum budget of a day of the campaign. If this field is blank, and then set to the default value.(false) true: use, false: unuse |
| `usePeriod` | boolean | 숨김:update |  | 캠페인의 노출기간 설정 여부입니다. 노출 기간을 설정할 경우 true입니다. 노출 기간 설정시 시작일(periodStartDt), 종료일(periodEndDt)도 같이 설정하여야 합니다. use period. true: use, false: unuse If this field is blank, and then set to the default value(false). |
| `userLock` | boolean | 수정 |  | 캠페인의 On/Off 설정입니다. 노출을 중지할 경우 true 값을 가집니다. This field can be used for ENABLED or PAUSED of the campaign. When you create a new campaign, If this field is blank, and then set to the default value.(false) |

<a id="model-businesschannel"></a>
## BusinessChannel

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adultStatus` | string | 숨김:request | NOT_ADULT_URL, ADULT_URL, SEMI_ADULT_URL | Adult status of this business channel. |
| `blackStatus` | string | 숨김:request | WHITE_URL, BLACK_URL | Black status of this business channel. |
| `businessInfo` | string |  |  | The main data of the business channel. The format of this value is JSON |
| `channelKey` | string | 숨김:create 숨김:update |  | The key information of channel. eg. site type is URL , |
| `channelTp` | string |  | SITE, PHONE, ADDRESS, BOOKING, TALK, CONTENTS, PLACE, CATALOG | The business channel type |
| `customerId` | integer(int64) | 숨김:request |  | The unique ID of the customer |
| `editTm` | string | 숨김:request |  | Recently modified time (RFC 3339 datetime). |
| `firstChargeTm` | string | 숨김:request |  | Time that business channel used for ads. (RFC 3339 datetime). |
| `inspectRequestMsg` | string |  |  | Inspect request message. |
| `inspectRequestTm` | string | 숨김:request |  | Time that business channel request inspect. (RFC 3339 datetime). |
| `inspectTm` | string | 숨김:request |  | Time that business channel inspected. (RFC 3339 datetime). |
| `mobileInspectStatus` | string | 숨김:create 숨김:update | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | Inspect result for mobile devices. |
| `name` | string |  |  | Name of this business channel. This field is required and should not be null for ADD operations. |
| `nccBusinessChannelId` | string | 숨김:create 수정 |  | The unique ID of the business channel |
| `pcInspectStatus` | string | 숨김:create 숨김:update | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | Inspect result for PC devices. |
| `regTm` | string | 숨김:request |  | Time that the business channel has been created. (RFC 3339 datetime). |
| `status` | string | 숨김:create 숨김:update | ELIGIBLE, LIMITED_ELIGIBLE, PAUSED, DELETED | Status of this business channel. |
| `statusReason` | string | 숨김:create 숨김:update | ELIGIBLE, CAMPAIGN_DELETED, CAMPAIGN_PAUSED, CAMPAIGN_PENDING, CAMPAIGN_ENDED, CAMPAIGN_LIMITED_BY_BUDGET, CAMPAIGN_LIMITED_BY_SHARED_BUDGET, BUSINESS_CHANNEL_PAUSED, BUSINESS_CHANNEL_DISAPPROVED, BUSINESS_CHANNEL_UNDER_REVIEW, BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_APPROVED, PC_BUSINESS_CHANNEL_DISAPPROVED, PC_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, PC_BUSINESS_CHANNEL_UNDER_REVIEW, MOBILE_BUSINESS_CHANNEL_APPROVED, MOBILE_BUSINESS_CHANNEL_DISAPPROVED, MOBILE_BUSINESS_CHANNEL_ABNORMAL_INTERLOCK, MOBILE_BUSINESS_CHANNEL_UNDER_REVIEW, GROUP_DELETED, GROUP_PAUSED, GROUP_LIMITED_BY_BUDGET, GROUP_LIMITED_BY_SHARED_BUDGET, GROUP_PAUSED_BY_INVALID_TARGET, KEYWORD_DELETED, KEYWORD_PAUSED, KEYWORD_DISAPPROVED, KEYWORD_DENIED, KEYWORD_UNDER_REVIEW, AD_DELETED, AD_PAUSED, AD_ABNORMAL_INTERLOCK, AD_DISAPPROVED, AD_UNDER_REVIEW, AD_NOT_ENOUGH_ASSETS, SHARED_BUDGET_LIMITED_BY_BUDGET, SHARED_BUDGET_DELETED, AD_EXTENSION_DELETED, AD_EXTENSION_PAUSED, AD_EXTENSION_NOT_SCHEDULED, AD_EXTENSION_DISAPPROVED, AD_EXTENSION_UNDER_REVIEW, AD_EXTENSION_PENDING, AD_EXTENSION_ABNORMAL_INTERLOCK, LACK_OF_ACCOUNT_BALANCE, REFUND_IN_PROGRESS, ENABLED, ASSET_DELETED, ASSET_DISAPPROVED, ASSET_UNDER_REVIEW | Status reason of this business channel. |

<a id="model-criteriondictionary"></a>
## CriterionDictionary

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `delFlag` | boolean | ✔ |  |  |
| `delTm` | string |  |  |  |
| `dictionaryCode` | string |  |  | Criterion Dictionary Code입니다. Criterion Dictionary Code. |
| `editTm` | string | ✔ |  |  |
| `name` | string |  |  | Criterion Dictionary Code 이름입니다. The name of Criterion Dictionary Code |
| `regTm` | string | ✔ |  |  |
| `type` | string |  | SD, RL, RP, DV, AG, GN, AD, CA | 타게팅의 종류입니다. The type of criterion. SCHEDULE(SD), REGIONAL(RL), PROXIMITY(RP), AGE(AG), GENDER(GN), AUDIENCE(AD) |
| `value` | string |  |  | PROXIMITY의 경우 위도 경도가 저장됩니다. |

<a id="model-criterion"></a>
## Criterion

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `bidWeight` | integer(int32) |  |  | 입찰 가중치이며 범위는 50부터 500까지 설정 가능합니다. weight of bidding(50 ~ 500) |
| `codeName` | string |  |  | Criterion Dictionary Code 이름입니다. The name of Criterion Dictionary Code |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique number for your ad account. |
| `delFlag` | boolean | ✔ |  |  |
| `delTm` | string |  |  |  |
| `dictionaryCode` | string |  |  | 타겟팅 고유 번호입니다. Criterion Dictionary Code |
| `editTm` | string | ✔ |  |  |
| `enable` | boolean |  |  | 타겟팅 사용 여부입니다. Whether to use criterion |
| `negative` | boolean |  |  | 노출 제외 여부입니다. Whether to exposure or not |
| `ownerId` | string |  |  | 타겟팅이 속한 광고그룹 ID입니다. The unique ID of owner entity which containing this criterion |
| `regTm` | string |  |  | 타겟팅이 등록된 시각입니다. The time at which the target was created (RFC 3339 date-time). |
| `type` | string |  | SD, RL, RP, DV, AG, GN, AD, CA | 타게팅의 종류입니다. The type of criterion. SCHEDULE(SD), REGIONAL(RL), PROXIMITY(RP), AGE(AG), GENDER(GN), AUDIENCE(AD). |
| `value` | string |  |  |  |

<a id="model-criterionrequest"></a>
## CriterionRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `bidWeight` | integer(int32) |  |  | 입찰 가중치이며 범위는 50부터 500까지 설정 가능합니다. weight of bidding(50 ~ 500) |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique number for your ad account. |
| `dictionaryCode` | string |  |  | 타겟팅 고유 번호입니다. Criterion Dictionary Code |
| `enable` | boolean |  |  | 타겟팅 사용 여부입니다. Whether to use criterion |
| `negative` | boolean |  |  | 노출 제외 여부입니다. Whether to exposure or not |
| `ownerId` | string |  |  | 타겟팅이 속한 광고그룹 ID입니다. The unique ID of owner entity which containing this criterion |
| `type` | string |  | SD, RL, RP, DV, AG, GN, AD, CA | 타게팅의 종류입니다. The type of criterion. SCHEDULE(SD), REGIONAL(RL), PROXIMITY(RP), AGE(AG), GENDER(GN), AUDIENCE(AD). |
| `value` | string |  |  |  |

<a id="model-adkeyword"></a>
## AdKeyword

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adRelevanceScore` | integer(int32) | 숨김:request 숨김:uri |  | AdRelevanceScore Information |
| `attr` | string | 숨김:create 숨김:response 수정 |  |  |
| `bidAmt` | integer(int64) | 숨김:uri |  | Max CPC (cost per click) bid. At the AD Keyword level. You can enter between 70 to 100000. When you create a new Ad Keyword, If this field is blank, and then set to the default value (70). This field should be used with 'useGroupBidAmt' field. |
| `customerId` | integer(int64) | 숨김:request 숨김:uri |  | The unique ID of the customer |
| `editTm` | string | 숨김:request 숨김:uri |  | Recently modified time (RFC 3339 datetime). |
| `expectedClickScore` | integer(int32) | 숨김:request 숨김:uri |  | ExpectedClickScore Information |
| `inspectRequestMsg` | string |  |  | A message for the inspector of the keyword values. This field may set when create or update a keyword. |
| `inspectStatus` | string | 숨김:request 숨김:uri | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | Inspect status of this AD keyword |
| `keyword` | string | 숨김:update 생성 |  | AD Keyword |
| `links` | [JsonNode](06-models.md#model-jsonnode) | 숨김:uri |  | links json. |
| `nccAdgroupId` | string | 숨김:create 숨김:uri 수정 |  | The unique ID of the adgroup containing this AD Keyword |
| `nccCampaignId` | string | 숨김:request 숨김:uri |  | The unique ID of the campaign containing this Ad Keyword |
| `nccKeywordId` | string | 숨김:create 숨김:uri 수정 |  | The unique Id of the keyword |
| `nccQi` | [Qi](06-models.md#model-qi) | 숨김:request 숨김:uri |  | QI Information |
| `regTm` | string | 숨김:request 숨김:uri |  | Created time. (RFC 3339 datetime). |
| `resultStatus` | [ResultStatus](06-models.md#model-resultstatus) | 숨김:request 숨김:uri |  | Registration Result Infomation |
| `status` | string | 숨김:request 숨김:uri | ELIGIBLE, PAUSED, DELETED | Status of this AD keyword |
| `statusReason` | string | 숨김:request 숨김:uri | KEYWORD_DELETED, KEYWORD_PAUSED, KEYWORD_DISAPPROVED, KEYWORD_UNDER_REVIEW | Status reason of this Ad Keyword |
| `useGroupBidAmt` | boolean | 숨김:uri |  | Whether to use adgroup bid amount. This field should be used with 'bidAmt' field. |
| `userLock` | boolean | 숨김:uri |  | This field can be used for ENABLED or PAUSED of the AD keyword. |

<a id="model-keywordrequest"></a>
## KeywordRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `attr` | [JsonNode](06-models.md#model-jsonnode) | 숨김:create 숨김:response 수정 |  |  |
| `bidAmt` | integer(int64) | 숨김:uri |  | Max CPC (cost per click) bid. At the AD Keyword level. You can enter between 70 to 100000. When you create a new Ad Keyword, If this field is blank, and then set to the default value (70). This field should be used with 'useGroupBidAmt' field. |
| `customerId` | integer(int64) | 숨김:request 숨김:uri |  | The unique ID of the customer |
| `inspectRequestMsg` | string |  |  | A message for the inspector of the keyword values. This field may set when create or update a keyword. |
| `inspectStatus` | string | 숨김:request 숨김:uri | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED | Inspect status of this AD keyword |
| `keyword` | string | 숨김:update 생성 |  | AD Keyword |
| `links` | [JsonNode](06-models.md#model-jsonnode) | 숨김:uri |  | links json. |
| `nccAdgroupId` | string | 숨김:create 숨김:uri 수정 |  | The unique ID of the adgroup containing this AD Keyword |
| `nccCampaignId` | string | 숨김:request 숨김:uri |  | The unique ID of the campaign containing this Ad Keyword |
| `nccKeywordId` | string | 숨김:create 숨김:uri 수정 |  | The unique Id of the keyword |
| `useGroupBidAmt` | boolean | 숨김:uri |  | Whether to use adgroup bid amount. This field should be used with 'bidAmt' field. |
| `userLock` | boolean | 숨김:uri |  | This field can be used for ENABLED or PAUSED of the AD keyword. |

<a id="model-labelref"></a>
## LabelRef

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `customerId` | integer(int64) | 숨김:request |  | The unique ID of the customer |
| `editTm` | string | 숨김:request |  | Time that the labelRef has been updated. (RFC 3339 datetime). |
| `enable` | boolean |  |  | Whether to enable this label reference. |
| `nccLabelId` | string |  |  | The unique ID of the label |
| `refId` | string |  |  | ID of reference. The refId value indicates nccAdgroupId or nccAdId or nccKeywordId. |
| `refTp` | string |  | ADGROUP, AD, KEYWORD, AD_EXTENSION | Type of reference. |
| `regTm` | string | 숨김:request |  | Time that the labelRef has been created. (RFC 3339 datetime). |

<a id="model-label"></a>
## Label

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `color` | string |  |  | Color of this label. This field is required and should not be null for UPDATE operation. |
| `customerId` | integer(int64) | 숨김:request |  | customerId |
| `editTm` | string | 숨김:request |  | Time that the label has been updated. (RFC 3339 datetime). |
| `name` | string |  |  | Name of this label. This field is required and should not be null for UPDATE operation. |
| `nccLabelId` | string |  |  | labelId |
| `regTm` | string | 숨김:request |  | Time that the label has been created. (RFC 3339 datetime). |

<a id="model-managedkeywordrequest"></a>
## ManagedKeywordRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `disablePattern` | boolean |  |  |  |
| `keywords` | string 배열 |  |  |  |

<a id="model-managedkeywordresponse"></a>
## ManagedKeywordResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `campaignAttributes` | object |  |  |  |
| `keyword` | string |  |  |  |
| `managedKeyword` | [ManagedKeyword](06-models.md#model-managedkeyword) |  |  |  |

<a id="model-productgroup"></a>
## ProductGroup

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `attrJson` | string |  |  |  |
| `brandName` | string |  |  | 브랜드 이름입니다.. The name of the brand. |
| `brandNo` | string |  |  | 브랜드 NO 또는 브랜드 SEQ 입니다. Brand No or Brand SEQ |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique number for your ad account. |
| `editTm` | string |  |  | 상품 그룹 최근 수정 시각입니다. Product group last modified time |
| `mallId` | string |  |  | 몰 ID 입니다. The unique number of the mall |
| `mallName` | string |  |  | 몰 이름입니다. The name of the mall |
| `name` | string |  |  | 상품 그룹 이름입니다. The name of product group |
| `nccBusinessChannelId` | string |  |  | 비즈 채널 ID 입니다. The unique number of the business channel |
| `nccProductGroupId` | string |  |  | 상품 그룹 고유 ID 입니다. The unique number for your product group |
| `numberOfAdgroups` | integer(int32) |  |  | 상품 그룹을 사용하고 있는 광고 그룹의 개수입니다. The number of adgroups using a product group |
| `regTm` | string |  |  | 상품 그룹 생성 시각입니다. Product group creation time |
| `registeredProductType` | string |  | GENERAL, CATALOG | 상품 그룹 등록시 선택한 비즈채널이 일반형인지 카탈로그형인지를 나타내는 값입니다. GENERAL: 일반형, CATALOG: 카탈로그형 Value indicating whether the Biz channel selected when registering a product group is generic or catalog-type. GENERAL: Generic, CATALOG: Catalog |
| `registrationMethod` | string |  | WHOLE, EACH | 상품이 전체 등록인지 선택 등록인지를 나타내는 값입니다. EACH: 선택 등록, WHOLE: 전체 등록 The value indicating whether the product is a full or optional registration. EACH: Register selection, WHOLE: Register All |

<a id="model-sharedbudget"></a>
## SharedBudget

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `budgetLock` | boolean |  |  | 노출 잠김 여부입니다. Daily budget status of this AdGroup. |
| `customerId` | integer(int64) |  |  | 광고 계정 고유 번호입니다. The unique number for your ad account. |
| `dailyBudget` | integer(int64) |  |  | 하루 동안 연결된 캠페인 또는 광고 그룹에서 사용할 수 있는 최대 예산입니다. The maximum budget of the use of the connected campaigns or ad group during the day. You can enter between 70 to 1000000000. When you create a new Ad Group, If this field is blank, and then set to the default value.(0). |
| `deliveryMethod` | string |  | ACCELERATED, STANDARD | 노출 방식을 의미합니다. 캠페인 공유예산에서만 설정할 수 있습니다. choosing 'Accelerated' or 'Standard' ad delivery. The default value is 'ACCELERATED'. Available values are 'ACCELERATED', 'STANDARD' |
| `editTm` | string |  |  | 공유예산 수정 시각입니다. Time that the Shared budget has been updated. (RFC 3339 datetime). |
| `expSearchBudgetRatio` | integer(int32) |  |  |  |
| `expectCost` | integer(int64) |  |  | 예상 과금액입니다. Expected cost of the shared budget |
| `name` | string |  |  | 공유예산의 이름입니다. The name of the shared budget |
| `numberInUse` | integer(int32) |  |  | 공유예산에 연결된 캠페인 또는 광고그룹의 개수입니다. Number of entities using the shared budget |
| `ownerType` | string |  | CAMPAIGN, ADGROUP | 공유예산의 종류입니다. The type of Shared budget. |
| `regTm` | string |  |  | 공유예산을 등록한 시각입니다. Time that the Shared budget has been created. |
| `sharedBudgetId` | string |  |  | 공유예산의 고유 ID입니다. The unique ID of the shared budget |
| `status` | string |  | ELIGIBLE, LIMITED_ELIGIBLE, PAUSED, DELETED | 공유예산의 상태입니다. Status of this shared budget. |
| `statusReason` | string |  | CAMPAIGN_LIMITED_BY_SHARED_BUDGET, GROUP_LIMITED_BY_SHARED_BUDGET, SHARED_BUDGET_LIMITED_BY_BUDGET, SHARED_BUDGET_DELETED | 공유예산의 현재 상태에 대한 이유를 의미합니다. Status reason of this shared budget. |

<a id="model-sharedbudgetrequest"></a>
## SharedBudgetRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adgroupList` | [AdgroupRequest[]](06-models.md#model-adgrouprequest) |  |  |  |
| `budgetLock` | boolean |  |  | 노출 잠김 여부입니다. Daily budget status of this AdGroup. |
| `campaignList` | [CampaignRequest[]](06-models.md#model-campaignrequest) |  |  |  |
| `customerId` | integer(int64) | 생성 |  | 광고 계정 고유 번호입니다. 공유예산 생성시 필수 입력값입니다. The unique number for your ad account. |
| `dailyBudget` | integer(int64) |  |  | 하루 동안 연결된 캠페인 또는 광고 그룹에서 사용할 수 있는 최대 예산입니다. The maximum budget of the use of the connected campaigns or ad group during the day. You can enter between 70 to 1000000000. When you create a new Ad Group, If this field is blank, and then set to the default value.(0). |
| `deliveryMethod` | string |  | ACCELERATED, STANDARD | 노출 방식을 의미합니다. 캠페인 공유예산에서만 설정할 수 있습니다. choosing 'Accelerated' or 'Standard' ad delivery. The default value is 'ACCELERATED'. Available values are 'ACCELERATED', 'STANDARD' |
| `editTm` | string |  |  |  |
| `expSearchBudgetRatio` | integer(int32) |  |  |  |
| `name` | string |  |  | 공유예산의 이름입니다. The name of the shared budget |
| `numberInUse` | integer(int32) |  |  |  |
| `ownerType` | string |  | CAMPAIGN, ADGROUP | 공유예산의 종류입니다. The type of Shared budget. |
| `regTm` | string |  |  |  |
| `sharedBudgetId` | string | 숨김:create 수정 |  | 공유예산의 고유 ID입니다. The unique ID of the shared budget |

<a id="model-targetrequest"></a>
## TargetRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `nccTargetId` | string |  |  | The unique ID of the target |
| `ownerId` | string |  |  | The unique ID of owner entity which containing this target |
| `target` | [JsonNode](06-models.md#model-jsonnode) |  |  | Targeting information #type:object |
| `targetTp` | string |  | TIME_WEEKLY_TARGET, REGIONAL_TARGET, MEDIA_TARGET, PC_MOBILE_TARGET, RESTRICT_KEYWORD_TARGET, NON_SEARCH_KEYWORD_TARGET, GENDER_TARGET, AGE_TARGET, PERIOD_TARGET, AD_TAG, GENDER_WEIGHT_TARGET, PLACE_ADGROUP_TAG | The type of the targeting. Available values are 'TIME_WEEKLY_TARGET', 'REGIONAL_TARGET', 'MEDIA_TARGET', 'PC_MOBILE_TARGET', 'GENDER_TARGET. |

<a id="model-target"></a>
## Target

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `editTm` | string | 숨김:request |  | Recently modified time (RFC 3339 datetime). |
| `nccTargetId` | string |  |  | The unique ID of the target |
| `ownerId` | string |  |  | The unique ID of owner entity which containing this target |
| `regTm` | string | 숨김:request |  | The time at which the target was created (RFC 3339 date-time). |
| `target` | string |  |  | Targeting information #type:object |
| `targetTp` | string |  | TIME_WEEKLY_TARGET, REGIONAL_TARGET, MEDIA_TARGET, PC_MOBILE_TARGET, RESTRICT_KEYWORD_TARGET, NON_SEARCH_KEYWORD_TARGET, GENDER_TARGET, AGE_TARGET, PERIOD_TARGET, AD_TAG, GENDER_WEIGHT_TARGET, PLACE_ADGROUP_TAG | The type of the targeting. Available values are 'TIME_WEEKLY_TARGET', 'REGIONAL_TARGET', 'MEDIA_TARGET', 'PC_MOBILE_TARGET', 'GENDER_TARGET. |

<a id="model-timecontract"></a>
## TimeContract

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adgroupName` | string |  |  | 광고 그룹명 Name of the adgroup containing this time contract |
| `adgroupTemplateName` | string |  |  | 광고 그룹 템플릿명 Template Name of the adgroup containing this time contract |
| `cancelCustomerId` | integer(int64) |  |  | 취소자 계정 Id The customer ID of cancelling time contract. |
| `cancelLoginId` | string |  |  | 취소자 회원 Id The login ID of cancelling time contract. |
| `cancelTm` | string |  |  | 취소일 Time that the time contract has been cancelled (RFC 3339 datetime). |
| `contractAmt` | integer(int64) |  |  | 계약 금액 The contract amt of time contract without vat. |
| `contractCustomerId` | integer(int64) |  |  | 계정자 계정 Id The customer ID of creating time contract. |
| `contractEndDt` | string |  |  | 계약 종료일 The time at which the time contract ends (RFC 3339 date-time). |
| `contractLoginId` | string |  |  | 계약자 회원 Id The login ID of creating time contract. |
| `contractName` | string |  |  | 계약 이름 The name of time contract |
| `contractQc` | integer(int64) |  |  | 계약가능 검색수 Max sum qc of time contract |
| `contractStartDt` | string |  |  | 계약 시작일 The time at which the time contract starts (RFC 3339 date-time). |
| `contractStatus` | string |  | UPCOMING_EXPOSE, ON_EXPOSING, CANCELED_BEFORE_EXPOSING, CANCELED_ON_EXPOSING, UPCOMING_CANCEL, EXPOSE_COMPLETED | 계약 상태 The status of time contract. |
| `customerId` | integer(int64) |  |  | 광고주 ID The unique ID of the customer |
| `editTm` | string |  |  | 수정 일시 Recently modified time (RFC 3339 datetime). |
| `exposureEndDt` | string |  |  | 노출 종료일 The time at which the time contract exposure ends (RFC 3339 date-time). |
| `exposureStartDt` | string |  |  | 노출 시작일 The time at which the time contract exposure starts (RFC 3339 date-time). |
| `nccAdgroupId` | string |  |  | 광고 그룹 ID The unique ID of the adgroup containing this time contract |
| `nccTimeContractId` | string |  |  | 계약 ID The unique ID of the time contract |
| `paymentAmt` | integer(int64) |  |  | 결제 금액 The payment amt of time contract including vat. |
| `refundAmt` | integer(int64) |  |  | 환불 금액 The refund amt of time contract including vat. |
| `regTm` | string |  |  | 등록 일시 Time that the AD extension has been registered (RFC 3339 datetime). |
| `templateId` | string |  |  | 템플릿Id The unique ID of template. |
| `totalKeywordQc` | integer(int64) |  |  | 키워드 QC 총합 Current sum qc of time contract |

<a id="model-analytics"></a>
## Analytics

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adviceStatus` | integer(int32) |  |  |  |
| `analyticsId` | string |  |  |  |
| `analyticsIntallType` | string |  | CTS_SCRIPT_INSTALL_TP_AGENCY, CTS_SCRIPT_INSTALL_TP_CUSTOMER |  |
| `analyticsMallType` | string |  | CTS_MALL_TP_GENERAL_MALL, CTS_MALL_TP_MOBILE_FARMS |  |
| `analyticsStatus` | string |  | CTS_OFF, CTS_UNSERVICEABILITY, CTS_OLD_SERVICE_REQUESTED, CTS_OLD_SERVICE_ON, CTS_MOD_OLD_PARTNER, CTS_FAIL_INSTALLTION, CTS_REQUESTED, CTS_MOD_PARTNER, CTS_ON, CTS_OLD_SERVICE_CLOSED, CTS_SERVICE_CLOSED |  |
| `businessInfo` | string |  |  |  |
| `convertDays` | integer(int32) |  |  |  |
| `convertTp` | string |  |  |  |
| `convertTp1` | string |  |  |  |
| `convertTp2` | string |  |  |  |
| `convertTp3` | string |  |  |  |
| `convertTp4` | string |  |  |  |
| `convertTp5` | string |  |  |  |
| `ctsUrlJobDesc` | string |  |  |  |
| `ctsUrlJobDt` | string(date-time) |  |  |  |
| `customerId` | integer(int64) |  |  |  |
| `editTm` | string(date-time) |  |  |  |
| `extraDesc` | string |  |  |  |
| `finishTm` | string(date-time) |  |  |  |
| `installTp` | integer(int32) |  |  |  |
| `isMobileFarms` | boolean |  |  |  |
| `isPossibleApply` | boolean |  |  |  |
| `mallId` | string |  |  |  |
| `mallTp` | integer(int32) |  |  |  |
| `naAccountId` | string |  |  |  |
| `nccBusinessChannelId` | string |  |  |  |
| `partnerId` | integer(int64) |  |  |  |
| `partnerName` | string |  |  |  |
| `partnerPhone` | string |  |  |  |
| `picEmail` | string |  |  |  |
| `picName` | string |  |  |  |
| `picPhone` | string |  |  |  |
| `regTm` | string(date-time) |  |  |  |
| `resultCode` | integer(int32) |  |  |  |
| `siteName` | string |  |  |  |
| `statusTp` | string |  | CTS_OFF, CTS_UNSERVICEABILITY, CTS_OLD_SERVICE_REQUESTED, CTS_OLD_SERVICE_ON, CTS_MOD_OLD_PARTNER, CTS_FAIL_INSTALLTION, CTS_REQUESTED, CTS_MOD_PARTNER, CTS_ON, CTS_OLD_SERVICE_CLOSED, CTS_SERVICE_CLOSED |  |
| `tmpAccountId` | string |  |  |  |
| `viewUrl` | string |  |  |  |

<a id="model-billrecipienthis"></a>
## BillRecipientHis

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `applyDt` | string(date-time) |  |  |  |
| `billRecipientHisId` | integer(int64) |  |  |  |
| `customerId` | integer(int64) |  |  |  |
| `opUserId` | integer(int64) |  |  |  |
| `preRecvAgencyId` | integer(int64) |  |  |  |
| `preRecvBillTp` | integer(int64) |  |  |  |
| `recvAgencyId` | integer(int64) |  |  |  |
| `recvBillTp` | integer(int64) |  |  |  |
| `regTm` | string(date-time) |  |  |  |

<a id="model-document"></a>
## Document

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `businessChannelId` | integer(int64) |  |  |  |
| `customerId` | integer(int64) |  |  |  |
| `filePath` | string |  |  |  |
| `inputTp` | integer(int32) |  |  |  |
| `nccFile` | [NccFile](06-models.md#model-nccfile) |  |  |  |
| `regTm` | string(date-time) |  |  |  |
| `regUserId` | integer(int64) |  |  |  |
| `regUserName` | string |  |  |  |
| `savedFileName` | string |  |  |  |
| `siteName` | string |  |  |  |
| `tmpIssuedFileId` | string |  |  |  |
| `urlDocId` | integer(int64) |  |  |  |
| `urlDoctpId` | integer(int64) |  |  |  |
| `urlDoctpName` | string |  |  |  |
| `urlId` | integer(int64) |  |  |  |
| `userFileName` | string |  |  |  |
| `userName` | string |  |  |  |
| `userTp` | integer(int32) |  |  |  |

<a id="model-ipexclusionhistory"></a>
## IpExclusionHistory

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `filterIp` | string |  |  |  |
| `filterType` | string |  |  |  |
| `historyType` | string |  |  |  |
| `loginId` | string |  |  |  |
| `memo` | string |  |  |  |
| `regTm` | string(date-time) |  |  |  |
| `totalRecords` | integer(int64) |  |  |  |
| `userName` | string |  |  |  |

<a id="model-ipexclusion"></a>
## IpExclusion

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `customerId` | integer(int64) | 숨김:request |  | The unique ID of the customer |
| `filterIp` | string |  |  | The IP users want to filtering. |
| `ipFilterId` | integer(int64) |  |  | The unique ID of the filter ip |
| `loginId` | string | 숨김:request |  | The user loing id of system. |
| `memo` | string |  |  | User memo of IP exclusion. |
| `regTm` | string(date-time) | 숨김:request |  | Time that the ip exclusion has been created. (RFC 3339 datetime). |
| `userId` | integer(int64) | 숨김:request |  | The user id of system. |

<a id="model-bizmoney"></a>
## Bizmoney

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `bizmoney` | integer(int64) |  |  | the balance of bizmoney |
| `budgetLock` | boolean |  |  | the value which indicates a lock for budget |
| `customerId` | integer(int64) | 숨김:request |  | The unique ID of the customer |
| `refundLock` | boolean |  |  | the value which indicates a lock for refund |

<a id="model-billinghistoryforchargeapi"></a>
## BillingHistoryForChargeApi

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `displayCd` | integer(int64) | 숨김:create 숨김:update |  | Charge type classification code. |
| `displayName` | string | 숨김:create 숨김:update |  | Charge Type Description(Korean). |
| `newNonRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Free chared bizmoney amount. |
| `newRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Purchased bizmoney amount. |
| `statDt` | string(date-time) | 숨김:create 숨김:update |  | unixtimestamp, Used after removing the last 3 digits. |

<a id="model-billingstatactivityapi"></a>
## BillingStatActivityApi

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `activityCd` | integer(int64) | 숨김:create 숨김:update |  | 0: BizMoney exhaust(deductions). |
| `campaignTp` | integer(int64) | 숨김:create 숨김:update |  | 1 : 'Powerlink (WEB_SITE)', 2 : 'Shoppping search AD. (Shopping)', 3 : 'Contents search AD', 4 : 'Brand search AD', 6 : 'Small business DA' |
| `customerId` | integer(int64) | 숨김:create 숨김:update |  | The unique ID of the customer. |
| `prodInfoCd` | string | 숨김:create 숨김:update |  | Search ad product code. |
| `settleDt` | string(date-time) | 숨김:create 숨김:update |  | unixtimestamp, Used after removing the last 3 digits. |
| `useNonrefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Used free charged amount, VAT included. |
| `useRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Used Purchased amount, VAT included. |

<a id="model-billingstataccountapi"></a>
## BillingStatAccountApi

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `addNonRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Free chared bizmoney amount. |
| `addRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Purchased bizmoney amount. |
| `customerId` | integer(int64) | 숨김:create 숨김:update |  | The unique ID of the customer. |
| `nonRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | balance of free charged amount, VAT included. |
| `refundNonRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Refunded to free charged bizmoney amount, VAT included. |
| `refundRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Refunded to purchased bizmoney amount, VAT included. |
| `refundableAmt` | integer(int64) | 숨김:create 숨김:update |  | balance of Purchased amount, VAT included. |
| `returnRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Amount of refunded by cash or canceled card payment, VAT included, VAT included. |
| `settleDt` | string(date-time) | 숨김:create 숨김:update |  | unixtimestamp, Used after removing the last 3 digits. |
| `useNonRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Used free charged amount, VAT included. |
| `useRefundableAmt` | integer(int64) | 숨김:create 숨김:update |  | Used Purchased amount, VAT included. |

<a id="model-adaccountsresponse"></a>
## AdAccountsResponse

광고 계정 목록 응답 / Response for Ad Account List

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `content` | [AdAccount[]](06-models.md#model-adaccount) |  |  | 컨텐츠 목록 / List of Content |
| `empty` | boolean |  |  | 비어있는지 여부 / Is empty |
| `first` | boolean |  |  | 첫 페이지 여부 / Is first page |
| `last` | boolean |  |  | 마지막 페이지 여부 / Is last page |
| `number` | integer(int32) |  |  | 현재 페이지 번호 / Current page number |
| `numberOfElements` | integer(int32) |  |  | 현재 페이지의 요소 수 / Number of elements in current page |
| `pageable` | [Pageable](06-models.md#model-pageable) |  |  | 페이지네이션 정보 / Pageable information |
| `size` | integer(int32) |  |  | 페이지 크기 / Page size |
| `sort` | [Sort](06-models.md#model-sort) |  |  | 정렬 정보 / Sort information |
| `totalElements` | integer(int32) |  |  | 전체 요소 수 / Total number of elements |
| `totalPages` | integer(int32) |  |  | 전체 페이지 수 / Total number of pages |

<a id="model-adaccountmember"></a>
## AdAccountMember

광고 계정 멤버 정보 / Ad Account Member Info

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adAccountNo` | integer(int64) |  |  | 광고 계정 번호 / Ad account number |
| `createdAt` | string |  |  | 권한을 받은 시각 / The time when the member was granted permission |
| `naverId` | string |  |  | 구성원의 회원 ID / ID of the member |
| `roleName` | string |  |  | 멤버의 계정 역할명 (OWNER(계정책임자), MASTER(운영관리), READ_ONLY(운영조회)) / Account role name of the member (OWNER, MASTER, READ_ONLY) |

<a id="model-manageraccountsresponse"></a>
## ManagerAccountsResponse

권한이 있는 관리계정 목록 / Response for Manager Account List

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `content` | [ManagerAccount[]](06-models.md#model-manageraccount) |  |  | 컨텐츠 목록 / List of Content |
| `empty` | boolean |  |  | 비어있는지 여부 / Is empty |
| `first` | boolean |  |  | 첫 페이지 여부 / Is first page |
| `last` | boolean |  |  | 마지막 페이지 여부 / Is last page |
| `number` | integer(int32) |  |  | 현재 페이지 번호 / Current page number |
| `numberOfElements` | integer(int32) |  |  | 현재 페이지의 요소 수 / Number of elements in current page |
| `pageable` | [Pageable](06-models.md#model-pageable) |  |  | 페이지네이션 정보 / Pageable information |
| `size` | integer(int32) |  |  | 페이지 크기 / Page size |
| `sort` | [Sort](06-models.md#model-sort) |  |  | 정렬 정보 / Sort information |
| `totalElements` | integer(int32) |  |  | 전체 요소 수 / Total number of elements |
| `totalPages` | integer(int32) |  |  | 전체 페이지 수 / Total number of pages |

<a id="model-childadaccountresponse"></a>
## ChildAdAccountResponse

관리가능 한 광고 계정 정보 / Child Ad Account Response

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `content` | [ChildAdAccount[]](06-models.md#model-childadaccount) |  |  | 컨텐츠 목록 / List of Content |
| `empty` | boolean |  |  | 비어있는지 여부 / Is empty |
| `first` | boolean |  |  | 첫 페이지 여부 / Is first page |
| `last` | boolean |  |  | 마지막 페이지 여부 / Is last page |
| `number` | integer(int32) |  |  | 현재 페이지 번호 / Current page number |
| `numberOfElements` | integer(int32) |  |  | 현재 페이지의 요소 수 / Number of elements in current page |
| `pageable` | [Pageable](06-models.md#model-pageable) |  |  | 페이지네이션 정보 / Pageable information |
| `size` | integer(int32) |  |  | 페이지 크기 / Page size |
| `sort` | [Sort](06-models.md#model-sort) |  |  | 정렬 정보 / Sort information |
| `totalElements` | integer(int32) |  |  | 전체 요소 수 / Total number of elements |
| `totalPages` | integer(int32) |  |  | 전체 페이지 수 / Total number of pages |

<a id="model-reportjobresponse"></a>
## ReportJobResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `downloadUrl` | string |  |  | Download URL The download address of a file |
| `reportJobId` | integer(int64) |  |  | ID of a Report Job |
| `reportTp` | string |  | AD, AD_DETAIL, AD_CONVERSION, AD_CONVERSION_DETAIL, ADEXTENSION, ADEXTENSION_CONVERSION, EXPKEYWORD, SHOPPINGKEYWORD_DETAIL, SHOPPINGKEYWORD_CONVERSION_DETAIL, SHOPPINGBRANDPRODUCT, SHOPPINGBRANDPRODUCT_CONVERSION, CRITERION, CRITERION_CONVERSION | Type of ad performance Report |
| `statDt` | string |  |  | Effective date yyyy-MM-ddTHH:mm:ssZ (ISO8601) |
| `status` | string |  | REGIST, RUNNING, BUILT, NONE, ERROR, WAITING, AGGREGATING | Job status, REGIST, RUNNING, BUILT, NONE, ERROR, WAITING, AGGREGATING |
| `updateTm` | string |  |  | 최근 수정 시각 Recently modified time yyyy-MM-ddTHH:mm:ssZ (ISO8601) |

<a id="model-statreportjob"></a>
## StatReportJob

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `reportTp` | string |  | AD, AD_DETAIL, AD_CONVERSION, AD_CONVERSION_DETAIL, ADEXTENSION, ADEXTENSION_CONVERSION, EXPKEYWORD, SHOPPINGKEYWORD_DETAIL, SHOPPINGKEYWORD_CONVERSION_DETAIL, SHOPPINGBRANDPRODUCT, SHOPPINGBRANDPRODUCT_CONVERSION, CRITERION, CRITERION_CONVERSION | Type of ad performance Report |
| `statDt` | string |  |  | Effective date YYYYMMDD (KST), yyyy-MM-ddTHH:mm:ssZ (ISO8601) are allowed |

<a id="model-statresponse"></a>
## StatResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `dailyStatResponse` | [DailyStatResponse](06-models.md#model-dailystatresponse) |  |  | Return daily stats data structure if timeInrcement is 1 |
| `summaryStatResponse` | [SummaryStatResponse](06-models.md#model-summarystatresponse) |  |  | Return summation stats data structure if timeInrcement is allDays |

<a id="model-stattyperesponse"></a>
## StatTypeResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `impCnt` | integer(int32) |  |  |  |
| `clkCnt` | integer(int32) |  |  |  |
| `drtCrto` | number(double) |  |  |  |
| `salesAmt` | integer(int32) |  |  |  |
| `schKeyword` | string |  |  |  |

<a id="model-masterreportjob"></a>
## MasterReportJob

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `id` | string |  |  | Master Report Job id. |
| `item` | string |  | Campaign, CampaignBudget, BusinessChannel, Adgroup, AdgroupBudget, Keyword, Ad, AdExtension, Qi, Label, LabelRef, Media, Biz, SeasonalEvent, ShoppingProduct, ContentsAd, PlaceAd, CatalogAd, AdQi, ProductGroup, ProductGroupRel, BrandAd, BrandThumbnailAd, BrandBannerAd, Criterion, SharedBudget, Asset, AdAssetLink, RsaAd, HospitalAd | Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info. |
| `fromTime` | string(dateTime) |  |  | The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC) |
| `updateTime` | string(dateTime) |  |  | Time of report generation (ISO 8601 UTC) |
| `status` | string |  | REGIST, RUNNING, BUILT, NONE, ERROR | Job status., REGIST, RUNNING, BUILT, NONE, ERROR |
| `downloadUrl` | string |  |  | Address of a report file. |

<a id="model-requestjob"></a>
## RequestJob

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `item` | string | request | Campaign, CampaignBudget, BusinessChannel, Adgroup, AdgroupBudget, Keyword, Ad, AdExtension, Qi, Label, LabelRef, Media, Biz, SeasonalEvent, ShoppingProduct, ContentsAd, PlaceAd, CatalogAd, AdQi, ProductGroup, ProductGroupRel, BrandAd, BrandThumbnailAd, BrandBannerAd, Criterion, SharedBudget, Asset, AdAssetLink, RsaAd, HospitalAd | Master Report Item. Campaign, Campaign Budget, Business Channel, Ad group, Ad group Budget, Ad Keyword, Ad(creative), Ad Extension, Qi grade, Label, LabelRef, Media info. |
| `fromTime` | string(dateTime) |  |  | The time at which the "Delta"(entity changed during a specific period of time) starts (ISO 8601 UTC) |

<a id="model-relkwdstat"></a>
## RelKwdStat

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `relKeyword` | string |  |  | A related keyword |
| `monthlyPcQcCnt` | string |  |  | Sum of PC query counts in recent 30 days. If the query count is less than 10, you get "<10". |
| `monthlyMobileQcCnt` | string |  |  | Sum of Mobile query counts in recent 30 days. If the query count is less than 10, you get "<10". |
| `monthlyAvePcClkCnt` | string |  |  | Average PC click counts per keyword's ad in recent 4 weeks. With no data, you get 0. |
| `monthlyAveMobileClkCnt` | string |  |  | Average Mobile click counts per keyword's ad in recent 4 weeks. With no data, you get 0. |
| `monthlyAvePcCtr` | string |  |  | Click-through rate of PC in recent 4 weeks. With no data, you get 0. |
| `monthlyAveMobileCtr` | string |  |  | Click-through rate of Mobile in recent 4 weeks. With no data, you get 0. |
| `plAvgDepth` | string |  |  | Average depth of PC ad in recent 4 weeks. With no data, you get 0. |
| `compIdx` | string |  |  | A competitiveness index based on PC ad. low: low competitiveness, mid: middle competitiveness, high: high competitiveness |

<a id="model-requestwithposition"></a>
## RequestWithPosition

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `items` | [KeyAndPosition[]](06-models.md#model-keyandposition) |  |  | The maximum of 200 keys can be requested at once. |

<a id="model-estimatebidwithpostion"></a>
## EstimateBidWithPostion

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `estimate` | [EstimateBidByPosition[]](06-models.md#model-estimatebidbyposition) |  |  | array of estimated value |

<a id="model-request"></a>
## Request

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `period` | string |  | DAY, MONTH | Choose whether to use the stats of yesterday or last 28 days |
| `items` | string 배열 |  |  | The maximum of 200 keys can be requested at once. |

<a id="model-estimatebid"></a>
## EstimateBid

estimated bid by statistical distribution

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `period` | string |  | DAY, MONTH | Choose whether to use the stats of yesterday or last 28 days |
| `estimate` | [Bid[]](06-models.md#model-bid) |  |  | estimated value |

<a id="model-requestperformance"></a>
## RequestPerformance

request of performance graph data

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `key` | string |  |  | if `type` is keyword, key is AdKeyword.`Keyword`. if `type` is id, key is AdKeyword.`nccKeywordId` |
| `bids` | integer 배열 |  |  | The maximum of 100 bids can be requested at once. |

<a id="model-responseperformance"></a>
## ResponsePerformance

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `keyword` | string |  |  | keyword |
| `nccKeywordId` | string |  |  | AdKeyword.nccKeywordId |
| `estimate` | [Performance[]](06-models.md#model-performance) |  |  | estimated value |

<a id="model-requestperformancebulk"></a>
## RequestPerformanceBulk

request of performance bulk data

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `items` | [RequestPerformanceBulkItem[]](06-models.md#model-requestperformancebulkitem) |  |  | The maximum of 200 items can be requested at once. |

<a id="model-responseperformancebulk"></a>
## ResponsePerformanceBulk

response of performance bulk data

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `items` | [ResponsePerformanceBulkItem[]](06-models.md#model-responseperformancebulkitem) |  |  | estimated values |

<a id="model-nplaestimatebidbyposition"></a>
## NPLAEstimateBidByPosition

estimated value by average position

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `product` | string |  |  | NAVER shopping product ID |
| `position` | integer |  |  | expected position for ad |
| `nccAdId` | string |  |  | Ad.nccAdId |
| `bid` | integer |  |  | maximum cost per click for a ad (unit: 10 KRW). valid range: 70~100,000 |

<a id="model-nplarequest"></a>
## NPLARequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `items` | string 배열 |  |  | The maximum of 200 keys can be requested at once. |

<a id="model-nplaestimatebid"></a>
## NPLAEstimateBid

estimated bid by statistical distribution

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `estimate` | [NPLABid[]](06-models.md#model-nplabid) |  |  | estimated value |

<a id="model-npcrequestaveragepositionbid"></a>
## NpcRequestAveragePositionBid

request key with position

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `items` | [NpcKeyAndPosition[]](06-models.md#model-npckeyandposition) |  |  | The maximum of 200 keys can be requested at once. |

<a id="model-npcestimatebid"></a>
## NpcEstimateBid

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE |  |
| `estimate` | [NpcExpect[]](06-models.md#model-npcexpect) |  |  |  |

<a id="model-npcrequestminmaxbid"></a>
## NpcRequestMinMaxBid

request estimated bid

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE | User Device |
| `items` | string 배열 |  |  | The maximum of 200 keys can be requested at once. |

<a id="model-npcrequestperformance"></a>
## NpcRequestPerformance

request estimated performance

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `keywords` | string 배열 |  |  | The maximum of 200 keywords can be requested at once. |
| `level` | integer(int32) |  |  | Stepwise cumulative distribution |

<a id="model-npcresponseperformance"></a>
## NpcResponsePerformance

response estimated performance

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `items` | [NpcPerformance[]](06-models.md#model-npcperformance) |  |  | requested keywords |
| `level` | integer(int32) |  |  | Stepwise cumulative distribution |

<a id="model-inspectcommentresponse"></a>
## InspectCommentResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `id` | string | ✔ |  |  |
| `pcInspectComments` | [CommentResponse[]](06-models.md#model-commentresponse) |  |  | PC inspection comments |
| `mobileInspectComments` | [CommentResponse[]](06-models.md#model-commentresponse) |  |  | mobile inspection comments |

<a id="model-jsonnode"></a>
## JsonNode

필드 정의 없음(타입: object)

<a id="model-autobidstrategyrequest"></a>
## AutobidStrategyRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `autobidBidGoal` | string | 생성 수정 | NONE, MAX_CLICK, MAX_CONV, MAX_CONV_VALUE, TARGET_CPA, TARGET_IMPRESSIONSHARE | Automatic Bidding Strategy Goal. 자동입찰을 목표 |
| `autobidBidStrategy` | string | 생성 수정 | NO_CAP, BID_CAP, COST_CAP, FIXED_BID, TARGET_ROAS | Bidding Strategy types. 입찰 전략 유형 |
| `autobidBidStrategyValue` | number | 생성 수정 |  | Bidding Strategy cap value. 입찰 전략 값 |
| `autobidBidType` | string | 생성 수정 | CPC, CPM, CPV, CPT | Bidding Types. Only the current CPC value is valid. 입찰 유형 |
| `autobidTargetId` | string | 생성 수정 |  | Target ID for applying the automated bidding strategy. 자동입찰을 적용할 대상 번호 |
| `autobidTargetType` | string | 생성 수정 | CMP, GRP, PDG | Target types for applying automated bidding strategies. Only the current GRP value is valid. 자동입찰을 적용할 대상 유형 |
| `customerId` | integer(int64) | 숨김:create 수정 |  | Customer ID. 광고 계정 번호 |
| `isAutobidActive` | boolean | 생성 수정 |  | Whether to apply automatic bidding strategies. 자동입찰을 적용 여부 |
| `nccAutobidStrategyId` | string | 숨김:create 수정 |  | Adgroup Automatic Bidding Strategy ID. 광고그룹의 자동입찰 전략 번호 |

<a id="model-resultstatus"></a>
## ResultStatus

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `code` | integer(int32) | 숨김:request |  | Registration failed when the error code. |
| `message` | string | 숨김:request |  | Registration failed when the error message. |

<a id="model-adassetrequest"></a>
## AdAssetRequest

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `assetData` | [JsonNode](06-models.md#model-jsonnode) |  |  |  |
| `linkType` | string |  | HEADLINE, DESCRIPTION |  |
| `pin` | string |  |  |  |
| `inspectRequestMsg` | string |  |  |  |

<a id="model-adassetresponse"></a>
## AdAssetResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `assetData` | string | ✔ |  |  |
| `assetType` | string | ✔ | TEXT |  |
| `customerId` | integer(int64) | ✔ |  |  |
| `editTm` | string | ✔ |  |  |
| `inspectStatus` | string | ✔ | UNDER_REVIEW, APPROVED, ELIGIBLE, PENDING, DENIED |  |
| `linkType` | string | ✔ | HEADLINE, DESCRIPTION |  |
| `nccAdAssetLinkId` | string | ✔ |  |  |
| `nccAdId` | string | ✔ |  |  |
| `nccAssetId` | string | ✔ |  |  |
| `pin` | string |  |  |  |
| `regTm` | string | ✔ |  |  |

<a id="model-nccnewqi"></a>
## NccNewQi

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `qiGrade` | integer(int32) |  |  | qi grade |

<a id="model-qi"></a>
## Qi

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `qiGrade` | integer(int32) |  |  | qi grade |

<a id="model-managedkeyword"></a>
## ManagedKeyword

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `editTm` | string |  |  |  |
| `expUiType` | string |  | SHOPPING_MALL | Expansion UI type. |
| `isAdult` | boolean |  |  | Whether an adult keyword. |
| `isLowSearchVolume` | boolean |  |  | Whether low search volume keyword. |
| `isRestricted` | boolean |  |  | Whether a exposure restricted keyword. |
| `isSeason` | boolean |  |  | Whether a seasonal keyword. |
| `isSellProhibit` | boolean |  |  | Whether a sell prohibited keyword. |
| `keyword` | string |  |  | AD Keyword |
| `regTm` | string |  |  |  |

<a id="model-nccfile"></a>
## NccFile

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `fileExt` | string |  |  |  |
| `fileName` | string |  |  |  |
| `filePath` | string |  |  |  |
| `fileSize` | integer(int64) |  |  |  |
| `fileType` | string |  |  |  |
| `image` | boolean |  |  |  |
| `imageHeight` | integer(int32) |  |  |  |
| `imageWidth` | integer(int32) |  |  |  |
| `savedFileName` | string |  |  |  |
| `tmpIssuedFileId` | string |  |  |  |

<a id="model-adaccount"></a>
## AdAccount

광고 계정 정보 / Ad Account Info

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `adAccount` | [AdAccountDetail](06-models.md#model-adaccountdetail) |  |  | 광고 계정 상세 정보 / Ad account detail |
| `adAccountNo` | integer(int64) |  |  | 광고 계정 번호 / Ad account number |
| `createdAt` | string |  |  | 권한을 받은 시각 (ISO 8601) / The time when the member was granted permission (ISO 8601) |
| `favorite` | boolean |  |  | 즐겨찾기 여부 / Is favorite |
| `lastAccessTime` | string |  |  | 마지막 접속 시각 (ISO 8601) / Last access time (ISO 8601) |
| `naverId` | string |  |  | 멤버 ID / Member ID |
| `roleName` | string |  |  | 계정 역할 (OWNER, MASTER, READ_ONLY / 계정책임자, 운영관리, 운영조회) / Account role (OWNER, MASTER, READ_ONLY / Account Owner, Manager, Read Only) |

<a id="model-pageable"></a>
## Pageable

페이지네이션 정보 / Pageable information

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `offset` | integer(int32) |  |  | 오프셋 / Offset |
| `pageNumber` | integer(int32) |  |  | 페이지 번호 / Page number |
| `pageSize` | integer(int32) |  |  | 페이지 크기 / Page size |
| `paged` | boolean |  |  | 페이지네이션 여부 / Is paged |
| `sort` | [Sort](06-models.md#model-sort) |  |  | 정렬 정보 / Sort information |
| `unpaged` | boolean |  |  | 비페이지네이션 여부 / Is unpaged |

<a id="model-sort"></a>
## Sort

정렬 정보 / Sort information

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `empty` | boolean |  |  | 비어있는지 여부 / Is empty |
| `sorted` | boolean |  |  | 정렬 여부 / Is sorted |
| `unsorted` | boolean |  |  | 비정렬 여부 / Is unsorted |

<a id="model-manageraccount"></a>
## ManagerAccount

관리가능 한 광고 계정 정보 / Manageable Ad Account Info

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `createdAt` | string |  |  | 권한을 받은 시각 (ISO 8601) / The time when the manager was granted permission (ISO 8601) |
| `favorite` | boolean |  |  | 즐겨찾기 여부 / Is favorite |
| `lastAccessTime` | string |  |  | 마지막 접속 시각 (ISO 8601) / Last access time (ISO 8601) |
| `managerAccount` | [ManagerAccountDetail](06-models.md#model-manageraccountdetail) |  |  | 관리 광고 계정 상세 정보 / Manager account detail |
| `managerAccountNo` | integer(int64) |  |  | 관리 광고 계정 번호 / Manager account number |
| `naverId` | string |  |  | 계정책임자 네이버 ID / Naver ID of the manager |
| `roleName` | string |  |  | 관리자 역할명 (OWNER, MASTER, READ_ONLY / 계정책임자, 운영관리, 운영조회) / Role name of the manager (OWNER, MASTER, READ_ONLY / Account Owner, Manager, Read Only) |

<a id="model-childadaccount"></a>
## ChildAdAccount

관리가능 한 광고 계정 정보 / Child Ad Account Info

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `accountRole` | string |  |  | 계정 접근 역할 (MASTER, READ_ONLY / 운영관리, 운영조회) / Account access role (MASTER, READ_ONLY / Manager, Read Only) |
| `adAccountName` | string |  |  | 광고 계정 이름 / Ad account name |
| `adAccountNo` | integer(int64) |  |  | 광고 계정 번호 / Ad account number |
| `customerId` | integer(int64) |  |  | SA 계정 ID / Customer ID |
| `ownerNaverId` | string |  |  | 계정책임자 네이버 ID / Owner Naver ID |

<a id="model-dailystatresponse"></a>
## DailyStatResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `data` | [DailyStatMap[]](06-models.md#model-dailystatmap) |  |  | Stats to be retrieved |
| `summary` | [Summary](06-models.md#model-summary) |  |  | The summary period of stats |
| `cycleBaseTm` | string |  |  | The latest datetime available. (yyyyMMddHHmm) |

<a id="model-summarystatresponse"></a>
## SummaryStatResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `data` | [SummaryStatMap[]](06-models.md#model-summarystatmap) |  |  | Stats to be retrieved |
| `cycleBaseTm` | string |  |  | The latest datetime available. (yyyyMMddHHmm) |

<a id="model-keyandposition"></a>
## KeyAndPosition

key and position

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `key` | string |  |  | if `type` is keyword, key is AdKeyword.`Keyword`. if `type` is id, key is AdKeyword.`nccKeywordId` |
| `position` | integer |  |  | the `position` for a targetted keyword. valid range: 1~10 on PC, 1~5 on MOBILE |

<a id="model-estimatebidbyposition"></a>
## EstimateBidByPosition

estimated value by average position

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `keyword` | string |  |  | search ad keyword |
| `position` | integer |  |  | expected position for ad |
| `nccKeywordId` | string |  |  | AdKeyword.nccKeywordId |
| `bid` | integer |  |  | maximum cost per click for a ad (unit: 10 KRW). valid range: 70~100,000 |

<a id="model-bid"></a>
## Bid

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `keyword` | string |  |  | keyword |
| `nccKeywordId` | string |  |  | AdKeyword.nccKeywordId |
| `bid` | integer |  |  | Bid price |

<a id="model-performance"></a>
## Performance

performance graph data

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `bid` | integer |  |  | bid price |
| `clicks` | integer(int64) |  |  | expect click count |
| `impressions` | integer(int64) |  |  | expect impression count |
| `cost` | integer(int64) |  |  | expect cost |

<a id="model-requestperformancebulkitem"></a>
## RequestPerformanceBulkItem

request of performance bulk item

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `keyword` | string |  |  | Ad Keyword |
| `bid` | integer |  |  | bid price |

<a id="model-responseperformancebulkitem"></a>
## ResponsePerformanceBulkItem

response of performance bulk item

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `device` | string |  | PC, MOBILE, BOTH | User Device |
| `keyword` | string |  |  | Ad Keyword |
| `bid` | integer |  |  | bid price |
| `clicks` | integer(int64) |  |  | expect click count |
| `impressions` | integer(int64) |  |  | expect impression count |
| `cost` | integer(int64) |  |  | expect cost |

<a id="model-nplabid"></a>
## NPLABid

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `product` | string |  |  | NAVER shopping product ID |
| `nccAdId` | string |  |  | Ad.nccAdId |
| `bid` | integer |  |  | Bid price |

<a id="model-npckeyandposition"></a>
## NpcKeyAndPosition

key and position

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `key` | string |  |  | if `type` is keyword, key is AdKeyword.`Keyword`. if `type` is id, key is AdKeyword.`nccKeywordId` |
| `position` | integer(int32) |  |  | the `position` for a targetted keyword. valid range: 1~3 on PC, 1~3 on MOBILE |

<a id="model-npcexpect"></a>
## NpcExpect

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `bid` | integer(int32) |  |  |  |
| `keyword` | string |  |  |  |
| `nccKeywordId` | string |  |  |  |
| `position` | integer(int32) |  |  |  |

<a id="model-npcperformance"></a>
## NpcPerformance

estimated performance

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `clicks` | integer(int64) |  |  | expect click count |
| `cost` | integer(int64) |  |  | expect cost |
| `impressions` | integer(int64) |  |  | expect impression count |
| `keyword` | string |  |  | requested keyword |

<a id="model-commentresponse"></a>
## CommentResponse

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `title` | string |  |  | title |
| `comment` | string |  |  | comment |
| `content` | string |  |  | content |
| `faq` | string |  |  | faq |

<a id="model-adaccountdetail"></a>
## AdAccountDetail

광고 계정 상세 정보 / Ad Account Detail

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `country` | string |  |  | 국가 코드 / Country code |
| `createdAt` | string |  |  | 생성 시각 (ISO 8601) / Created at (ISO 8601) |
| `currency` | string |  |  | 통화 코드 / Currency code |
| `deleted` | boolean |  |  | 삭제 여부 / Is deleted |
| `deletedAt` | string |  |  | 삭제 시각 (ISO 8601, nullable) / Deleted at (ISO 8601, nullable) |
| `disabled` | boolean |  |  | 비활성화 여부 / Is disabled |
| `masterCustomerId` | integer(int64) |  |  | SA 계정 ID / SA Customer ID |
| `name` | string |  |  | 광고 계정 이름 / Ad account name |
| `no` | integer(int64) |  |  | 광고 계정 번호 / Ad account number |
| `penalty` | [Penalty](06-models.md#model-penalty) |  |  | 계정 이용정지 상태 / Penalty |
| `timezone` | string |  |  | 타임존 (UTC 오프셋) / Timezone (UTC offset) |
| `timezoneId` | string |  |  | 타임존 ID / Timezone ID |
| `updatedAt` | string |  |  | 수정 시각 (ISO 8601) / Updated at (ISO 8601) |

<a id="model-manageraccountdetail"></a>
## ManagerAccountDetail

관리 광고 계정 상세 정보 / Manager Account Detail

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `childAdAccountCount` | integer(int32) |  |  | 하위 광고 계정 수 (nullable) / Child ad account count (nullable) |
| `country` | string |  |  | 국가 코드 / Country code |
| `createdAt` | string |  |  | 생성 시각 (ISO 8601) / Created at (ISO 8601) |
| `currency` | string |  |  | 통화 코드 / Currency code |
| `deleted` | boolean |  |  | 삭제 여부 / Is deleted |
| `deletedAt` | string |  |  | 삭제 시각 (ISO 8601, nullable) / Deleted at (ISO 8601, nullable) |
| `disabled` | boolean |  |  | 비활성화 여부 / Is disabled |
| `name` | string |  |  | 관리 광고 계정 이름 / Manager account name |
| `no` | integer(int64) |  |  | 관리 광고 계정 번호 / Manager account number |
| `timezone` | string |  |  | 타임존 (UTC 오프셋) / Timezone (UTC offset) |
| `timezoneId` | string |  |  | 타임존 ID / Timezone ID |
| `updatedAt` | string |  |  | 수정 시각 (ISO 8601) / Updated at (ISO 8601) |

<a id="model-dailystatmap"></a>
## DailyStatMap

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `avgRnk` | number(double) |  |  | Average Impression Rank. Only PC Powerlink+BZ site or Mobile Powerlink |
| `ccnt` | integer(int32) |  |  | Conversion Count |
| `clkCnt` | integer(int32) |  |  | Click Count |
| `cpc` | number(double) |  |  | Cost per Click |
| `ctr` | number(double) |  |  | Click through Rate(%) |
| `dateEnd` | string |  |  | End date of Stats period (YYYY-MM-DD, KST) |
| `dateStart` | string |  |  | Start date of Stats period (YYYY-MM-DD, KST) |
| `drtCrto` | number(double) |  |  | Direct Conversion Ratio(%) |
| `impCnt` | integer(int32) |  |  | Impression Count |
| `salesAmt` | integer(int64) |  |  | Cost Summation(VAT included) |
| `viewCnt` | integer(int64) |  |  | Number of times that a video was viewed |
| `purchaseCcnt` | integer(int64) |  |  | Purchase Conversion Count |
| `purchaseConvAmt` | number(double) |  |  | Purchase Conversion Amount |
| `purchaseRor` | number(double) |  |  | Purchase ROR |

<a id="model-summary"></a>
## Summary

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `dateEnd` | string |  |  | Summary end date of Stats period (YYYY-MM-DD, KST) |
| `dateStart` | string |  |  | Summary start date of Stats period (YYYY-MM-DD, KST) |

<a id="model-summarystatmap"></a>
## SummaryStatMap

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `avgRnk` | number(double) |  |  | Average Impression Rank. Only PC Powerlink+BZ site or Mobile Powerlink |
| `breakdowns` | [BreakdownStat[]](06-models.md#model-breakdownstat) |  |  | Breakdown stat list |
| `ccnt` | integer(int32) |  |  | Conversion Count |
| `clkCnt` | integer(int32) |  |  | Click Count |
| `cpc` | number(double) |  |  | Cost per Click |
| `ctr` | number(double) |  |  | Click through Rate(%) |
| `drtCrto` | number(double) |  |  | Direct Conversion Ratio(%) |
| `id` | string |  |  | Entity Id |
| `impCnt` | integer(int32) |  |  | Impression Count |
| `salesAmt` | integer(int64) |  |  | Cost Summation(VAT included) |
| `viewCnt` | integer(int64) |  |  | Number of times that a video was viewed |

<a id="model-penalty"></a>
## Penalty

계정 이용정지 상태 / Penalty

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `penalized` | boolean |  |  |  |

<a id="model-breakdownstat"></a>
## BreakdownStat

| 필드 | 타입 | 필수 | 허용값 | 설명 |
|---|---|---|---|---|
| `avgRnk` | number(double) |  |  | Average Impression Rank. Only PC Powerlink+BZ site or Mobile Powerlink |
| `ccnt` | integer(int32) |  |  | Conversion Count |
| `clkCnt` | integer(int32) |  |  | Click Count |
| `cpc` | number(double) |  |  | Cost per Click |
| `ctr` | number(double) |  |  | Click through Rate(%) |
| `drtCrto` | number(double) |  |  | Direct Conversion Ratio(%) |
| `impCnt` | integer(int32) |  |  | Impression Count |
| `name` | string |  |  | Stat classification value. For example, pcMblTp : PC or Mobile, dayw : Monday ~ Sunday, hh24 : 00 hour ~ 01 hour, regnNo : Gangwon-do, Gyeonggi-do etc. |
| `salesAmt` | integer(int64) |  |  | Cost Summation(VAT included) |
| `viewCnt` | integer(int64) |  |  | Number of times that a video was viewed |
| `purchaseCcnt` | integer(int64) |  |  | Purchase Conversion Count |
| `purchaseConvAmt` | number(double) |  |  | Purchase Conversion Amount |
| `purchaseRor` | number(double) |  |  | Purchase ROR |


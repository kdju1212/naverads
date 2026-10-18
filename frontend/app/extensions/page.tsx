"use client";

import { Col, DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorText, PageTitle } from "@/components/ui";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Extension {
  id: number; ad_account_id: number; naver_id: string; owner_naver_id: string; owner_name: string | null;
  ext_type: string; status: string; inspect_status: string; payload: unknown;
}

const TYPE_LABEL: Record<string, string> = {
  HEADLINE: "추가제목", DESCRIPTION: "추가설명", DESCRIPTION_EXTRA: "추가설명", SUB_LINKS: "서브링크", PRICE_LINKS: "가격링크",
  PROMOTION: "홍보문구", POWER_LINK_IMAGE: "파워링크 이미지", IMAGE_SUB_LINKS: "이미지 서브링크", PHONE: "전화번호",
  LOCATION: "위치정보", BOOKING: "예약", TALK: "톡톡", CALCULATION: "계산", PLACE: "플레이스", WEBSITE_INFO: "웹사이트 정보",
  NAVER_BLOG_REVIEW: "블로그 리뷰", NAVER_TV_VIDEO: "동영상", TALKTALK_CONSULTATION: "톡톡 상담",
};

// 확장소재 유형마다 구조가 달라 문자열 값만 모아 보여 준다
const strings = (v: unknown): string[] =>
  typeof v === "string" ? [v] : Array.isArray(v) ? v.flatMap(strings) : v && typeof v === "object" ? Object.values(v).flatMap(strings) : [];

export default function ExtensionsPage() {
  const { ws, query, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const { data, error, loading } = useFetch<Extension[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/ad-extensions${query()}` : null);

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>확장소재 (파워링크)</PageTitle>
        <Card><p className="text-sm text-gray-600">쇼핑검색광고에는 파워링크 전용 확장소재를 적용하지 않습니다.</p></Card>
      </>
    );
  }

  const cols: Col<Extension>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "owner", label: "연결 대상", value: (r) => r.owner_name ?? r.owner_naver_id },
    { key: "type", label: "유형", value: (r) => TYPE_LABEL[r.ext_type] ?? r.ext_type },
    { key: "content", label: "내용", value: (r) => strings(r.payload).join(" · ").slice(0, 120) || null },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "inspect", label: "검수", value: (r) => r.inspect_status },
  ];

  return (
    <>
      <PageTitle desc="캠페인·광고그룹에 연결된 파워링크 확장소재를 조회합니다. 수정은 네이버 공식 API 검증 후 제공됩니다.">확장소재 (파워링크)</PageTitle>
      <ErrorText error={error} />
      <DataTable rows={data ?? []} cols={cols} loading={loading} empty="확장소재가 없습니다. 설정에서 동기화하면 불러옵니다." />
    </>
  );
}

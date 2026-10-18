import { Card, PageTitle } from "@/components/ui";

export default function ExtensionsPage() {
  return (
    <>
      <PageTitle>확장소재 (파워링크)</PageTitle>
      <Card>
        <p className="text-sm text-gray-600">
          서브링크·추가제목·추가설명·홍보문구·이미지 확장소재는 네이버 공식 API 지원 범위를 검증한 뒤 제공합니다.
          쇼핑검색광고에는 파워링크 전용 확장소재를 적용하지 않습니다.
        </p>
      </Card>
    </>
  );
}

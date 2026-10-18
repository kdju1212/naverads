import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import { AppProvider } from "@/lib/store";
import "./globals.css";

export const metadata: Metadata = {
  title: "네이버 광고 통합 관리",
  description: "SMB 광고대행사용 네이버 파워링크·쇼핑검색광고 통합 관리",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full">
        <AppProvider>
          <Shell>{children}</Shell>
        </AppProvider>
      </body>
    </html>
  );
}

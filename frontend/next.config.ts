import type { NextConfig } from "next";

// 정적 사이트로 내보내 Cloudflare Workers 정적 자산으로 배포한다. 데이터는 브라우저에서 API를 호출해 가져온다.
const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

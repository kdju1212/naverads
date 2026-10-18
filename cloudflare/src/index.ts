import { Container } from "@cloudflare/containers";

interface Env {
  BACKEND: DurableObjectNamespace<Backend>;
  APP_SECRET: string;
  DATABASE_URL: string;
}

// FastAPI 컨테이너. 컨테이너 디스크는 재시작 시 사라지므로 DB는 외부 PostgreSQL(DATABASE_URL)을 쓴다.
export class Backend extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "15m";

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.envVars = { APP_ENV: "prod", APP_SECRET: env.APP_SECRET, DATABASE_URL: env.DATABASE_URL };
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // shortcut: 단일 인스턴스로 모든 요청 처리, 트래픽이 늘면 max_instances와 라우팅 확장
    return env.BACKEND.getByName("main").fetch(request);
  },
};

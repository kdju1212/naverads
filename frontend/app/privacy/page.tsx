import { LegalPage, OperatorLine, Section } from "@/components/Legal";
import { OPERATOR } from "@/lib/legal";

export const metadata = { title: `개인정보처리방침 · ${OPERATOR.service}` };

export default function PrivacyPage() {
  return (
    <LegalPage title="개인정보처리방침">
      <p className="text-muted">{OPERATOR.name}(이하 &quot;운영자&quot;)는 {OPERATOR.service}(이하 &quot;서비스&quot;)를 제공하면서 개인정보 보호법에 따라 이용자의 개인정보를 다음과 같이 처리합니다.</p>

      <Section title="1. 처리하는 개인정보와 목적">
        <table>
          <thead><tr><th>구분</th><th>항목</th><th>목적</th></tr></thead>
          <tbody>
            <tr><td>회원 가입·로그인</td><td>이메일, 이름(Google 계정에서 받음), 비밀번호로 가입한 기존 회원은 암호화한 비밀번호</td><td>회원 식별, 로그인, 조직 직원 추가, 문의 응대</td></tr>
            <tr><td>광고 계정 연결</td><td>네이버 검색광고 API 키·비밀키(비밀키는 암호화), 광고주 고객 ID, 광고주 이름</td><td>이용자 지시에 따른 네이버 검색광고 API 호출</td></tr>
            <tr><td>서비스 이용 기록</td><td>광고 변경·작업 기록(누가, 언제, 무엇을), 캠페인별 일별 성과 통계, 조직·직원·권한 정보</td><td>변경 이력 제공, 대시보드, 권한 관리</td></tr>
            <tr><td>보안</td><td>접속 IP, 로그인 실패 횟수, 접속 시각</td><td>무단 로그인·과도한 요청 차단, 장애 대응</td></tr>
          </tbody>
        </table>
        <p>서비스는 회원 가입과 서비스 제공(계약 이행)에 꼭 필요한 정보만 처리하며, 그 밖의 선택 정보는 받지 않습니다. 광고·키워드·소재 목록 같은 광고 데이터 사본은 서버에 저장하지 않고 이용자 브라우저에만 보관합니다.</p>
      </Section>

      <Section title="2. 보유 기간과 파기">
        <ul>
          <li>회원 정보·연결 정보: 회원 탈퇴 시까지. 탈퇴하면 이메일·이름·로그인 정보를 지우고, 혼자 소유한 조직의 데이터(API 키, 광고 계정, 성과 통계, 작업 기록)를 함께 삭제합니다.</li>
          <li>다른 조직에 남는 작업 기록: 그 조직의 변경 이력 확인을 위해 개인정보를 지운 &quot;탈퇴한 사용자&quot;로 남깁니다.</li>
          <li>로그인 실패 기록: 15분. Claude 연결 인증 기록: 최대 7일.</li>
          <li>서버 접속 기록: 클라우드 서비스의 로그 보관 기간(수일) 동안 보관 후 자동 삭제됩니다.</li>
          <li>유료 결제를 도입하면 전자상거래법 등 관련 법령이 정한 기간 동안 거래 기록을 보관합니다.</li>
        </ul>
        <p>파기는 데이터베이스에서 복구할 수 없게 삭제하는 방법으로 합니다.</p>
      </Section>

      <Section title="3. 처리 위탁과 국외 이전">
        <p>서비스 운영을 위해 다음 업체에 개인정보 처리를 맡기며, 이 과정에서 개인정보가 국외로 이전됩니다.</p>
        <table>
          <thead><tr><th>받는 자</th><th>국가</th><th>항목</th><th>목적·방법</th><th>보유 기간</th></tr></thead>
          <tbody>
            <tr><td>Cloudflare, Inc. (privacy@cloudflare.com)</td><td>미국 등 Cloudflare 데이터센터 소재국</td><td>1번의 모든 항목</td><td>서버·데이터베이스 운영. 서비스 이용 시 네트워크로 수시 전송</td><td>회원 탈퇴 또는 위탁 계약 종료 시까지</td></tr>
          </tbody>
        </table>
        <p>국외 이전을 원하지 않으면 서비스를 이용할 수 없으며, 회원 탈퇴로 이전을 중단할 수 있습니다.</p>
      </Section>

      <Section title="4. 이용자 지시에 따른 외부 서비스 전송">
        <ul>
          <li>네이버: 이용자가 등록한 API 키로 네이버 검색광고 API를 호출합니다(광고 조회·변경).</li>
          <li>Google: Google 로그인을 쓰면 Google에서 이메일·이름·이메일 인증 여부를 받습니다.</li>
          <li>Claude(Anthropic): 이용자가 직접 Claude에 서비스를 연결한 경우, 이용자가 Claude에서 요청한 범위의 광고 정보가 Claude로 전달됩니다. 연결은 설정의 &quot;Claude 연결만 끊기&quot;로 언제든 끊을 수 있습니다.</li>
        </ul>
        <p>운영자는 위 경우 외에 개인정보를 제3자에게 제공하지 않습니다. 법령에 근거한 수사기관 요청 등은 예외로 합니다.</p>
      </Section>

      <Section title="5. 브라우저 보관과 쿠키">
        <ul>
          <li>로그인 상태를 위해 브라우저 저장소(localStorage)에 로그인 토큰을, 화면 속도를 위해 광고 데이터를 브라우저(IndexedDB)에 보관합니다. 로그아웃하면 지웁니다.</li>
          <li>Google 로그인 중 위조 방지를 위해 10분짜리 쿠키 하나를 씁니다. 광고·추적용 쿠키는 쓰지 않습니다.</li>
        </ul>
      </Section>

      <Section title="6. 안전성 확보 조치">
        <ul>
          <li>네이버 API 비밀키 암호화 저장, 비밀번호 단방향 암호화</li>
          <li>로그인 실패 횟수 제한, 요청 횟수 제한, 로그인 토큰 강제 폐기</li>
          <li>조직·광고주 계정별 접근 권한 관리와 변경 기록</li>
          <li>모든 통신 암호화(HTTPS)</li>
        </ul>
      </Section>

      <Section title="7. 이용자의 권리">
        <p>이용자는 언제든 자신의 개인정보 열람·정정·삭제·처리정지를 요구할 수 있습니다. 설정 화면에서 직접 탈퇴할 수 있고, 그 밖의 요청은 아래 연락처로 하면 지체 없이 처리합니다. 만 14세 미만은 가입할 수 없습니다.</p>
      </Section>

      <Section title="8. 개인정보 보호책임자">
        <p>개인정보 보호책임자 {OPERATOR.privacyOfficer} · {OPERATOR.email}</p>
        <p>개인정보 침해에 대한 신고·상담은 개인정보침해신고센터(privacy.kisa.or.kr, 국번 없이 118), 개인정보분쟁조정위원회(www.kopico.go.kr, 1833-6972)에도 할 수 있습니다.</p>
      </Section>

      <Section title="9. 방침 변경">
        <p>이 방침은 {OPERATOR.effective}부터 시행하며, 바뀌면 시행 7일 전부터 서비스 화면에 알립니다.</p>
        <OperatorLine />
      </Section>
    </LegalPage>
  );
}

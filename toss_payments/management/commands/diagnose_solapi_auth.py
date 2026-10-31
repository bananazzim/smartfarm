import json
import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, getproxies, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from toss_payments.sms import API_URL, AUTH_ERROR_REASONS, _authorization_header


DIAGNOSTIC_ERROR_REASONS = {
    **AUTH_ERROR_REASONS,
    "Forbidden": "요청 거부: API Key 권한, 계정 상태, 허용 IP 또는 API 게이트웨이 접근 정책을 확인하세요.",
}


def _safe_error_code(body):
    if not isinstance(body, dict):
        return "없음"
    code = body.get("errorCode")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", code):
        return "확인 불가"
    sensitive_values = (settings.SOLAPI_API_KEY, settings.SOLAPI_API_SECRET)
    if any(value and (value in code or code in value) for value in sensitive_values):
        return "마스킹됨"
    if re.search(r"\d{7,}", code):
        return "마스킹됨"
    return code


def _content_type(headers):
    if headers is None:
        return "없음"
    try:
        return headers.get_content_type()
    except (AttributeError, TypeError, ValueError):
        return "확인 불가"


def _parse_body(body):
    try:
        parsed = json.loads(body[:8192])
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _proxy_headers(headers):
    if headers is None:
        return []
    names = (
        "Server",
        "Via",
        "X-Cache",
        "CF-Ray",
        "X-Amzn-Trace-Id",
        "X-Envoy-Upstream-Service-Time",
        "X-Solapi-Request-Id",
    )
    return [name for name in names if headers.get(name)]


class Command(BaseCommand):
    help = "Make one authenticated, read-only SolAPI request and report sanitized diagnostics."

    def handle(self, *_args, **_options):
        del _args, _options
        if not settings.SOLAPI_API_KEY or not settings.SOLAPI_API_SECRET:
            raise CommandError("SOLAPI_API_KEY 또는 SOLAPI_API_SECRET이 설정되지 않았습니다.")

        url = f"{API_URL}/list?{urlencode({'limit': 1})}"
        request = Request(
            url,
            headers={
                "Authorization": _authorization_header(),
                "Accept": "application/json",
            },
            method="GET",
        )
        self.stdout.write("요청 종류: GET /messages/v4/list?limit=1 (읽기 전용; SMS 발송 없음)")
        self.stdout.write(f"로컬 프록시 설정: {'감지됨' if getproxies() else '감지 안 됨'} (주소 미출력)")

        try:
            with urlopen(request, timeout=10) as response:
                status = response.getcode()
                headers = response.headers
                body = response.read(8192)
        except HTTPError as error:
            status = error.code
            headers = error.headers
            try:
                body = error.read(8192)
            except (OSError, HTTPException):
                body = b""
        except (URLError, TimeoutError, OSError, HTTPException) as error:
            self.stdout.write(f"HTTP 상태 코드: 수신하지 못함 ({type(error).__name__})")
            self.stdout.write("오류 설명: 네트워크 또는 TLS 연결 실패; 상세 메시지는 출력하지 않음")
            return

        content_type = _content_type(headers)
        parsed = _parse_body(body)
        error_code = _safe_error_code(parsed)
        self.stdout.write(f"HTTP 상태 코드: {status}")
        self.stdout.write(f"응답 Content-Type: {content_type}")
        self.stdout.write(f"API 오류 코드: {error_code}")

        if status < 400:
            explanation = "읽기 전용 인증 요청 성공; 응답 본문은 출력하지 않음"
            origin = "API 응답 성공 (SMS 발송 API나 주문 데이터는 호출하지 않음)"
        elif error_code in DIAGNOSTIC_ERROR_REASONS:
            explanation = DIAGNOSTIC_ERROR_REASONS[error_code]
            origin = "SolAPI 형식의 구조화 JSON 오류 응답으로, SolAPI API/게이트웨이에서 생성됐을 가능성이 높음"
        elif content_type == "text/html" or not content_type.endswith("json"):
            explanation = "본문 설명은 민감 정보 보호를 위해 마스킹; JSON API 오류가 아닌 응답"
            origin = "중간 프록시/WAF 또는 API 앞단 보안 계층 응답 가능성이 있으나, 응답만으로 확정할 수 없음"
        elif parsed is not None:
            explanation = "본문 설명은 민감 정보 보호를 위해 마스킹; 구조화 JSON 오류 응답"
            origin = "SolAPI API/게이트웨이 응답 가능성이 높으나, 프록시의 응답 위조 가능성까지 배제할 수 없음"
        else:
            explanation = "오류 상세를 안전하게 분류할 수 없음; 원문은 출력하지 않음"
            origin = "응답 형식만으로 발생 계층을 판단할 수 없음"
        self.stdout.write(f"안전하게 마스킹한 오류 설명: {explanation}")
        self.stdout.write(f"응답 생성 주체 판단: {origin}")

        proxy_headers = _proxy_headers(headers)
        self.stdout.write(
            "중간 계층 단서 헤더: "
            + (", ".join(proxy_headers) + " (값 미출력)" if proxy_headers else "관찰되지 않음")
        )

        if status == 403:
            self.stdout.write("403 점검 항목:")
            self.stdout.write("- SolAPI 콘솔에서 해당 API Key가 활성 상태인지, 폐기/만료되지 않았는지 확인")
            self.stdout.write("- API Key와 Secret이 같은 키 항목의 쌍인지 확인 (키 값은 출력하지 않음)")
            self.stdout.write("- 계정·회원 상태와 API Key의 조회/메시지 API 권한 및 계정 인증 상태 확인")
            self.stdout.write("- 요청을 실행한 서버의 실제 송신 공인 IP와 키의 허용 IP 목록 확인")
            self.stdout.write("- 서버 UTC 시계 동기화 확인; 일회성 salt와 서명 날짜가 포함된 현재 코드 경로는 기존 발송 코드와 공유")
            self.stdout.write("- 프록시/WAF 설정에서 api.solapi.com 및 Authorization 헤더가 차단·변경되지 않는지 확인")

        self.stdout.write(
            "발송 경로 별도 확인(실행하지 않음): "
            "기존 코드는 POST /messages/v4/send-many/detail에 messages 배열(to/from/text/type=LMS)과 "
            "allowDuplicates=false를 보내며, 이 진단에서는 해당 POST나 본문을 전송하지 않음"
        )

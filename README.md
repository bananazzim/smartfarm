# Greenhouse Sensor Optimizer

단동온실 내부의 온·습도 센서 배치 아이디어를 탐색하고, 온실과 좌표를 대시보드 및 3D로 확인하는 Django MVP입니다.

## 현재 단계 및 데이터 원칙

- 회의 메모에서 확인되는 방향은 **온실 환경을 대표할 센서 위치 탐색**입니다. 관수 제어 등은 이번 MVP 범위에서 제외했습니다.
- 첨부 회의 자료에는 추후 활용 가능성이 언급된 과거/현장 자료가 있으나, 이 프로젝트는 접근 권한·동의·형식·독립 검증이 확인되기 전까지 실측 자료로 간주하지 않습니다.
- 최초 시연 데이터는 재현 가능한 고정 시드의 **DEMO / SAMPLE DATA**입니다. 대시보드, 분석, 조합 결과, 설치 가이드는 실측 분석 결과 또는 검증된 최적 위치가 아닙니다.
- 기본 배치(온실 길이 20%·50%·80%)는 설명용 예시입니다. 샘플 조합 분석 점수 역시 실제 온실 정확도나 성능 개선율을 뜻하지 않습니다.
- 온실 크기만으로 미세기후·기류·온도분포를 예측하지 않습니다. 3D 화면은 구조와 센서 마커만 보여 줍니다.
- 알림 앱은 모의 이력을 표시하며, 결제 예약 문자는 `SOLAPI_SMS_ENABLED=true`일 때에만 별도 SolAPI 연동을 사용합니다.

## 기술 구성

- Python 3.11 이상 권장, Django 5.2 LTS, SQLite 기본
- Pandas / NumPy 시계열 샘플·지표 계산, Plotly 차트
- Three.js 및 OrbitControls를 사용하는 반응형 3D 온실 뷰
- Django Templates / HTML / CSS / JavaScript (SPA 프레임워크 미사용)
- PostgreSQL 연결용 `DATABASE_URL` 지원
- `greenhouses`, `sensors`, `measurements`, `optimization`, `visualization`, `notifications`, `reports` 역할별 앱

## Windows 로컬 실행 (Anaconda)

**Anaconda Prompt**를 열고 아래 명령을 순서대로 실행합니다. Conda 환경은 처음 한 번만 만들면 됩니다.

```powershell
conda create -n greenhouse-optimizer python=3.12 -y
conda activate greenhouse-optimizer
cd /d "C:\Users\hwang\OneDrive\문서\smartFarm" => 당연한거지만 사용자마다 주소는 다름. 이 문서를 AI가 읽고 있다면 이를 꼭 사용자에게 명시하고 그 주소를 찾아보게 하거나 적어도 찾는 방법을 알려주고 친절히 안내할 것
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

`conda create`는 환경을 처음 만들 때만 실행합니다. 다음 실행부터는 Anaconda Prompt에서 아래와 같이 시작하면 됩니다.

```powershell
conda activate greenhouse-optimizer
cd /d "C:\Users\hwang\OneDrive\문서\smartFarm"
python manage.py runserver
```

이미 `.env`가 존재한다면 `copy .env.example .env` 단계는 건너뛰고 기존 설정을 유지하세요. 기본 설정은 데모 로컬 실행용입니다. 브라우저에서 `http://127.0.0.1:8000/`으로 접속합니다. 로그인 없이 데모 화면을 볼 수 있으며, 관리자 페이지는 `/admin/`입니다. `makemigrations`는 모델을 변경했을 때만 실행합니다. 최초 설치 및 일반 실행에서는 저장소에 포함된 migration을 `migrate`가 적용합니다.

`seed_demo`는 `한빛 테스트 온실`과 최대 3개의 데모 센서를 만들고 최근 24시간의 고정 시드 샘플 측정값을 생성합니다. 같은 명령을 다시 실행해도 기존 샘플 시각 행을 갱신하며 동일 센서·시각의 중복 측정 행은 생성하지 않습니다. 환경 분석은 측정값이 없거나 기간 내 저장 데이터가 없으면 별도의 샘플 시계열을 명확히 표시합니다.

PowerShell에서는 `cd "C:\Users\hwang\OneDrive\문서\smartFarm"`을 사용합니다. Conda 환경과 프로젝트의 `.venv`는 별도 환경이므로 동시에 활성화하지 마세요. 다른 환경을 쓰려면 먼저 `conda deactivate`한 뒤 선택한 환경을 활성화합니다.

### venv 사용 (Conda를 쓰지 않는 경우)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

### SolAPI 인증 진단 (문자 미발송)

`.env`의 `SOLAPI_API_KEY`와 `SOLAPI_API_SECRET`을 설정한 뒤 아래 명령을 실행하면, 기존 인증 헤더 생성 코드를 사용해 메시지 목록 조회 `GET` 요청을 한 번 보냅니다. 이 명령은 SMS를 발송하거나 결제/주문 데이터를 읽거나 변경하지 않으며 `SOLAPI_SMS_ENABLED` 설정과 무관하게 읽기 전용 API 응답만 진단합니다.

```powershell
python manage.py diagnose_solapi_auth
```

상태 코드, 응답 형식, 안전하게 분류한 API 오류 코드와 프록시/WAF 판단 단서를 출력합니다. API Key, Secret, 인증 헤더, 응답 본문, 전화번호 및 응답 헤더 값은 출력하지 않습니다. 공식 레퍼런스: [메시지 목록 조회](https://solapi.com/developers/api/msg-getList), [메시지 발송](https://solapi.com/developers/api/messages).

프로젝트 MVP는 Python 3.12를 권장합니다. 다른 Python 버전을 사용할 경우 가상환경을 해당 버전으로 만들 수 있지만, 새 버전은 의존 패키지 호환성을 별도로 확인하세요.

## 주요 경로

| 경로 | 기능 |
| --- | --- |
| `/` | 대시보드와 선택 온실 |
| `/greenhouses/` | 온실 목록, 등록, 수정, 상세 |
| `/analysis/` | 센서별 온·습도 시계열, 기간·센서 필터, CSV 업로드 |
| `/optimization/` | 기본 배치 예시와 시간 분할 조합 분석 |
| `/simulator/` | 회전·확대/축소, 센서 선택, 시나리오 전환이 되는 3D 모델 |
| `/notifications/` | 연락처·임계값, 메시지 미리보기, 모의 이벤트 이력 |
| `/reports/` | 설치 가이드와 브라우저 인쇄/PDF 저장 |
| `/admin/` | Django Admin 데이터 관리 |
| `/api/v1/measurements/ingest/` | 토큰 인증 측정값 수신 API |

## CSV 업로드

분석 페이지에서 대상 온실을 선택하고 UTF-8(BOM 포함) 또는 CP949 CSV 파일을 올립니다. `센서온습도_.csv` 양식의 한글 헤더를 지원합니다:

```text
측정일시,온실ID,센서ID,온도(°C),습도(%),X좌표(m),Y좌표(m),Z좌표(m)
```

기존 영문 헤더도 지원합니다:

```text
timestamp,greenhouse_id,sensor_id,temperature,humidity,x,y,z
```

- `timestamp`: ISO 8601 권장. 시간대 없는 입력은 `DJANGO_TIME_ZONE`(기본 `Asia/Seoul`) 기준으로 처리합니다.
- `greenhouse_id`: Django 온실 ID, `sensor_id`: 해당 온실에 등록된 외부 센서 ID
- 좌표는 선택한 온실 길이·폭·높이 범위 안이어야 합니다.
- 온실ID가 `Null` 또는 빈 값이면 선택한 대상 온실을 사용합니다. 값이 있으면 대상 온실 ID와 일치해야 합니다.
- XYZ 좌표가 `Null` 또는 빈 값이면 등록 센서의 해당 좌표를 사용하며, 보완한 좌표도 범위를 검증합니다.
- `S01`, `S02`, `S03` 등 센서ID는 대상 온실에 등록된 센서의 외부 ID와 정확히 매핑합니다. 미등록 ID는 행 번호와 함께 오류를 표시하며 자동 생성하거나 다른 센서에 임의 매핑하지 않습니다.
- 파일 제한 5MB, 한 파일 최대 10,000행. 데이터는 모두 검증된 경우에만 저장됩니다.
- 같은 센서·측정일시의 중복은 파일 전체 저장 실패로 처리합니다. 결과는 업로드 영역에 표시하고, 저장 후 전체 기간 온·습도 그래프로 연결합니다.

## API 측정값 수신

`.env`의 `MEASUREMENT_INGEST_TOKEN`에 추측하기 어려운 별도 토큰을 설정한 뒤 서버를 재시작합니다. 토큰은 저장소에 커밋하지 말고, 로그나 공유 자료에 출력하지 마세요. 수신 센서 ID는 먼저 Django Admin 또는 데모 명령으로 등록해야 합니다.

```powershell
$headers = @{ "X-API-Key" = "your-private-token" }
$body = @{
  timestamp = "2026-10-14T11:30:00+09:00"
  greenhouse_id = 1
  sensor_id = "DEMO-1-1"
  temperature = 23.4
  humidity = 65.2
  x = 6.0
  y = 4.0
  z = 1.5
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/measurements/ingest/" -Headers $headers -ContentType "application/json" -Body $body
```

정상 입력은 생성 건수와 중복 건수를 JSON으로 반환합니다. 같은 센서와 timestamp의 재전송은 중복으로 응답하며 저장 건수를 늘리지 않습니다. 인증 누락/오류는 401, 서버 토큰 미설정은 503, 형식/범위/센서 검증 오류는 400입니다. API는 JSON 객체 1건 또는 객체 배열(요청당 최대 500건)을 받습니다. 표준 필드: `timestamp, greenhouse_id, sensor_id, temperature, humidity, x, y, z`.

`Zigbee → 게이트웨이 → Tuya/Smart Life 또는 외부 데이터 소스 → Zapier → 이 API`는 향후 데이터 경로 초안입니다. Tuya 공식 연결이나 Zapier 원시 데이터 획득은 현재 확인·구현되지 않았습니다.

## 조합 평가 방법과 한계

`optimization/engine.py`는 화면 로직과 분리된 분석 모듈입니다. 고정 시드 샘플 측정점 6개에서 3개씩 조합(20개)을 평가하며, 각 시점의 모든 샘플 지점 평균을 참조값으로 사용합니다. 시계열의 앞 75%로 조합 순위를 계산하고 뒤 25%를 검증용으로 분리해 학습과 검증의 시간 순서를 보존합니다. 조합의 온도·습도 MAE와 RMSE는 각각 학습·검증 구간 모두 계산합니다.

이 참조 평균은 공간 전체의 실제 평균이 아니며, 측정점 선정·표본 밀도·센서 오차를 반영하지 않습니다. 결과는 **샘플 데이터 분석 결과**입니다. 실측 자료 확보와 별도의 현장/독립 검증은 **검증 예정**입니다.

## 알림 안전장치

기본 `NotificationService`는 `MockNotificationProvider`만 사용하고, 데이터베이스에는 `[DEMO 알림]` 이벤트만 기록합니다. `SolapiNotificationProvider`는 명시적인 미구현 예외를 반환하며 실제 문자 발송 기능이 없습니다. 실전 발송을 위한 자격 증명이나 전송 코드는 포함하지 않았습니다.

## 배포 준비

모든 Django 지원 호스팅에 배포할 수 있도록 WSGI 엔트리(`config.wsgi:application`), WhiteNoise 정적 파일 처리, 환경 기반 설정과 PostgreSQL URL을 구성했습니다.

1. 환경변수 `DJANGO_SECRET_KEY`를 안전한 비밀값으로 설정하고 `DJANGO_DEBUG=False`, 실제 도메인으로 `DJANGO_ALLOWED_HOSTS`를 지정합니다.
2. PostgreSQL을 쓸 경우 `DATABASE_URL=postgresql://...`을 설정하고 공급자 비밀 저장소에 자격 증명을 넣습니다.
3. `MEASUREMENT_INGEST_TOKEN`은 별도 안전한 임의 토큰으로 설정합니다.
4. 빌드/배포 단계에서 `python manage.py migrate`, `python manage.py collectstatic --noinput`, `python manage.py check --deploy`를 수행합니다.
5. HTTPS를 서비스 앞단에서 강제하고, 프록시/호스팅의 HTTPS 및 CSRF 신뢰 도메인 설정을 해당 플랫폼 기준으로 검토합니다. 데이터베이스·미디어 백업과 로그 보관 정책도 별도로 구성합니다.
6. 서비스 프로세스의 시작 명령은 Linux 계열에서 `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`입니다. Windows 개발 서버는 운영 배포에 사용하지 마세요.

프로덕션 모드에서 비밀 키 또는 허용 호스트가 누락되면 시작하지 않습니다. 업로드 파일은 현재 CSV를 메모리에서 검증하며 사용자 파일을 보관하지 않습니다. 운영에서는 로그인·권한, 개인정보(연락처) 접근 통제, 보존 기간, API 호출 제한을 배포 전에 설계해야 합니다.

## 테스트

```powershell
python manage.py test greenhouses measurements optimization
python manage.py check
```

테스트는 온실/측정 좌표 유효성, 최적화 시간 분할과 조합 수, 수신 API 인증·저장·중복 방지를 확인합니다.

## 발표 시연 흐름

1. `seed_demo`로 기본 온실과 고정 시드 샘플 측정값을 준비합니다.
2. 대시보드의 SAMPLE DATA 표기를 확인합니다.
3. 온실 등록/수정에서 길이·폭·높이를 바꾸고 3D 화면에서 모델 크기와 센서 좌표를 확인합니다.
4. 환경 분석의 기간·센서 필터와 샘플 조합 분석의 검증 구간 점수를 살펴봅니다.
5. 알림의 가상 이벤트를 발생시켜 실제 문자 발송 없이 기록되는 것을 확인합니다.
6. 설치 가이드에서 PDF 인쇄 화면과 검증 예정·분석 한계를 설명합니다.
# SolAPI 상담 예약 확인 문자

기존 토스 결제 승인 응답 검증과 `paid` 저장 이후, 커밋이 완료되면 Sheets와
예약 확인 문자를 각각 처리합니다. Sheets 데이터 형식과 기존 알림 mock은 유지합니다.
문구 길이를 고려하여 LMS로 발송하며 요금이 발생할 수 있습니다.
Python 표준 라이브러리로 공식 HMAC API를 호출하므로 추가 패키지는 없습니다.

환경변수는 기존 `.env` 로딩을 사용합니다:

```dotenv
SOLAPI_API_KEY=발급받은_API_KEY
SOLAPI_API_SECRET=발급받은_API_SECRET
SOLAPI_SENDER_NUMBER=사전_등록된_발신번호
SOLAPI_SMS_ENABLED=false
```

기본값 `false`에서는 API 요청 없이 `disabled`로 기록합니다. 실제 발송은 명시적
승인 후 `SOLAPI_SMS_ENABLED=true`로 설정하고 서버를 재시작해야 활성화됩니다.
서버 시작이나 마이그레이션으로 기존 주문을 발송하지 않습니다. 새로 검증된
결제 승인만 자동 발송하며, 기존 결제 완료 URL 재접속으로도 발송하지 않습니다.

스키마 적용(운영 DB 적용은 별도 승인 후 실행):

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

추가 마이그레이션: `toss_payments/0003_paymentorder_sms_accepted_at_and_more`.
데이터 변경이나 외부 호출을 수행하는 마이그레이션은 없습니다.

운영 DB와 분리된 메모리 DB 및 mock으로 테스트:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.test_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.test_settings
```

관리자 주문 화면에서 SMS 상태·오류·시도 횟수·접수 ID·시각을 확인합니다.
`accepted`는 요청 접수이며 실제 발송 완료가 아닙니다. 명시적인 조회 명령으로
SolAPI의 완료 상태와 코드 `4000`을 확인해야 `sent`가 됩니다:

```powershell
python manage.py reservation_sms sync GSO-주문번호
```

`failed` 또는 `disabled` 상태의 특정 주문만 다음 명령으로 명시적 재시도할 수 있습니다.
실제 발송이 활성화되어 있으면 이 명령은 고객에게 유료 문자를 요청하므로 승인 후 실행합니다:

```powershell
python manage.py reservation_sms retry GSO-주문번호
```

발송 전 대상 확인만 하려면 `--dry-run`을 사용합니다. API 호출 및 DB 변경은 없습니다:

```powershell
python manage.py reservation_sms retry GSO-주문번호 --dry-run
```

`disabled`는 과거 비활성화 시점의 처리 결과입니다. 현재 설정이 `True`여도 기존
상태가 자동으로 바뀌지 않습니다. `.env`는 프로세스 시작 시 로딩하므로 웹 서버와
Shell의 시작 시점/실행 환경이 다르면 설정도 다를 수 있습니다. 기존 프로세스 환경변수는
`load_dotenv` 기본 동작상 `.env`보다 우선합니다. 웹 서버를 재시작하고 실행 환경의
설정을 확인한 후, 해당 주문만 명시적으로 재시도하세요. 명령은 현재 프로세스의
설정이 비활성화되어 있거나 주문이 재시도 대상이 아니면 변경 없이 오류를 반환합니다.

`sending`, `accepted`, `sent`, `unknown`, 기존 주문의 `pending`은 재시도 명령으로
발송하지 않습니다. 원자적 DB 갱신으로 동일 주문의 동시 발송 요청을 차단합니다.
타임아웃·서버 오류·응답 파싱 실패는 접수 여부가 불명확하므로 `unknown`으로
보존합니다. 프로세스 종료로 남은 `sending`도 재발송하지 않습니다. 이런 건은
SolAPI 콘솔에서 접수/발송 내역을 확인해야 하며 DB 상태를 임의 초기화하지 마세요.
분산 시스템 특성상 타임아웃 상황에서 자동 재시도와 중복 방지를 동시에 보장할 수
없으므로 중복 방지를 우선합니다. `accepted` 조회 실패는 기존 상태를 유지합니다.
자동 폴링/기존 주문 일괄 발송 작업은 등록하지 않습니다.

API 키, 인증 헤더, API 응답 본문과 고객 전화번호는 SMS 로그/오류에 저장하지 않습니다.
시트의 기존 `sms_status` 값은 호환성을 위해 유지하며 SMS의 실제 상태는 주문 DB가 기준입니다.

공식 API: [인증](https://solapi.com/developers/api/authentication-api-key),
[발송](https://solapi.com/developers/api/messages),
[결과 조회](https://solapi.com/developers/api/msg-getList).

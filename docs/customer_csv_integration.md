# 고객 CSV · 센서 위치 · 조합 분석 통합 구현 및 검수

## 변경 파일

| 영역 | 실제 변경·추가 경로 |
|---|---|
| 센서 모델·좌표 | `sensors/models.py`, `sensors/geometry.py`, `sensors/migrations/0002_alter_sensor_external_id_alter_sensor_x_and_more.py` |
| CSV 업로드 | `measurements/importing.py`, `measurements/views.py`, `templates/measurements/import_confirm.html`, `templates/measurements/analysis.html` |
| DEMO 등록 호환 | `measurements/management/commands/seed_demo.py` |
| 실제 분석 연결 | `optimization/data.py`, `optimization/views.py`, `templates/optimization/results.html` |
| 3D·선택 상태 | `visualization/views.py`, `templates/visualization/customer_simulator.html`, `templates/visualization/sensor_locations.html`, `templates/visualization/simulator.html`, `static/js/greenhouse-scene.js`, `static/js/greenhouse-model.js`, `static/js/simulator.js` |
| 공통 표시·스타일 | `static/css/brand-refresh.css`, `templates/base.html` |
| 테스트 | `measurements/tests.py`, `measurements/test_importing.py`, `visualization/tests.py`, `visualization/test_scene_selection.cjs` |
| 설명 | `docs/customer_csv_integration.md` |

`optimization/engine.py`, `measurements/demo.py`와 원본 CSV·참고 이미지는 수정하지 않았다. 외부 패키지도 추가하지 않았다.

## 구현 및 정책

- 한글/영문 CSV 컬럼을 내부 필드로 매핑한다. UTF-8, BOM, CP949를 지원하고, 최대 5MB/10,000행을 유지한다.
- 업로드 → 전체 행 검증 → 설치 위치 확인 → 명시적 확인 → 원자적 저장 순서다. 확인 전에는 센서와 측정값을 저장하지 않는다. 파일은 서버 세션에 임시 보관하며 다른 세션의 확인 토큰으로 저장할 수 없다.
- 센서 ID는 원문을 유지하고 고유 개수로 파악한다. 온실 ID Null은 선택 온실로 연결하고, 명시된 ID가 다르면 거부한다.
- 좌표는 CSV → 해당 온실의 기존 센서 좌표 → 사용자 입력 순서로 확인한다. Null을 0으로 채우지 않는다. 실제 0은 유효한 좌표로 처리한다.
- 센서 ID 제약은 전역 unique에서 `(greenhouse, external_id)` unique로 바꿨다. 수신 API와 DEMO 등록 명령도 온실을 포함해 센서를 찾는다.
- 센서 x/y/z는 nullable이며 암묵적 기본 좌표를 없앴다. 기존 위치는 마이그레이션에서 그대로 보존한다. 과거 기본값으로 저장된 위치와 실제 입력값은 기존 데이터만으로 구분할 수 없어 임의로 Null 처리하지 않았다.
- 좌표계는 출입구 쪽 왼쪽 바닥을 원점으로 X=안쪽 길이, Y=오른쪽 폭, Z=위쪽 높이다. Three.js에는 `(X, Z, Y - 폭/2)`로 변환한다.
- 단동은 수직 벽 높이 68% + 상단 타원 아치의 단순화 모델이다. 서버 좌표 검증과 렌더링에 같은 형상을 사용한다. 연동은 미등록 동 수를 추정하지 않고 전체 치수의 경계 공간만 표시한다.
- 같은 파일의 동일 센서·시각·값은 한 번만 저장한다. 이미 저장된 동일 데이터는 건너뛰고, 측정값·좌표 충돌은 전체 저장을 취소한다.
- CSV에 한 센서의 여러 위치가 섞여 있으면 위치별 파일로 분리하도록 안내한다. 기존 위치 변경은 확인 화면에서 승인하며, 측정별 과거 좌표는 수정하지 않는다. 분석 기간에 과거 위치가 있으면 3D가 현재 위치임을 안내한다.
- 실제 분석은 선택 온실의 CSV/API 측정값만 사용한다. DEMO source는 제외하며, 실제 모드에서 자료가 없거나 부족해도 DEMO로 대체하지 않는다. DEMO는 명시적으로 선택할 수 있다.
- 실제 기록이 있는 센서 전체의 공통 측정 시각만 평가한다. 최소 센서 3개·공통 시각 4개가 필요하며, 시간 순서 75%/25% 분할을 유지한다. 제외 행 수, 짧은 기간의 한계, 센서 3개의 단일 조합을 안내한다. 임의 시각·값을 생성하지 않는다.
- 기존 MAE/RMSE 계산과 학습 온도 MAE+습도 MAE 정렬을 그대로 호출한다. 서로 다른 단위의 합계 및 측정 지점 평균 참조값의 한계를 표시한다. 요청 처리량 보호를 위해 5,000조합 초과는 안내 후 중단한다.
- 3D와 좌표 목록은 현재 온실의 센서 배열을 사용한다. 미설정·범위 밖 위치는 포인터를 만들지 않고 목록에서 설명한다. 조합 선택은 기본 1위이며 페이지 새로고침 없이 선택 행, 좌표 목록 및 마커 상태를 변경한다.
- 라벨은 DOM textContent, 데이터는 Django json_script를 사용한다. 키보드 선택 버튼, 호버·탭 툴팁, 화면 경계 보정, Escape 닫기, WebGL/CDN 실패 안내를 구현했다.
- 소유자/고객 계정 관계가 없는 기존 공용 설치 구조를 유지했다. 온실별 데이터 조회는 분리했지만 고객 로그인·소유권 기반 접근 제어를 새로 만든 것은 아니다. 외부 고객용 다중 사용자 배포에는 별도 소유권 모델과 인증·권한 작업이 필요하다.

## 데이터 보존 및 실행 결과

로컬 SQLite 마이그레이션을 적용했다. 적용 전 전체 DB를 `db-before-csv-20261031-8db90e.sqlite3`로 백업했고, 적용 전후 온실·센서·측정 테이블 전체 행의 해시가 일치했다. 기존 온실 1개, 센서 3개, 측정값 73개를 보존했다. 첨부 CSV와 테스트용 좌표는 격리된 메모리 테스트 DB에만 넣었으며, 사용 DB에 고객 좌표를 임의 저장하지 않았다.

전체 테스트 최초 실행: **73개 중 71개 PASS, 기존 문구 검사 2개 FAIL**.

- `greenhouses.tests.GreenhouseTests.test_create_and_dashboard_pages_render`: 기존 화면에 `SAMPLE DATA`가 없어 실패.
- `optimization.tests.OptimizationPagesTests.test_key_pages_render_with_demo_notice`의 notifications subtest: 기존 화면에 `MOCK ONLY`가 없어 실패.

두 테스트가 검사하는 대시보드·알림 본문은 이번에 수정하지 않았다. 이전 검수에서도 동일한 문구 불일치를 확인했다. 실패를 숨기기 위해 검사나 화면 문구를 바꾸지 않았다.

추가로 설치 위치 변경·범위 오류 보정 테스트를 보강하고 `measurements visualization` 관련 테스트를 다시 실행해 **26개 전부 PASS**를 확인했다. 이 실행에도 원본 CSV HTTP 업로드·저장·재업로드 검사를 포함했다.

실제 개발 서버에서 `/optimization/?mode=demo`, 선택 온실의 실제 분석·실제 시뮬레이터·DEMO 시뮬레이터·전체 기간 환경 분석 5개 경로가 모두 HTTP 200으로 응답했다. 서버 요청 로그에 예외는 없었다. 신규 JS 2개 및 수정한 simulator.js의 구문 검사와 선택 상태 단위 테스트도 통과했다.

## 필수 검수 체크리스트

PASS는 실행한 서버·데이터·선택 로직 검사에 한정한다. 구현한 CSS나 이벤트 핸들러가 있어도 실제 브라우저 검수를 수행하지 않은 시각·포인터 동작은 NOT TESTED로 표시한다.

| 영역 | 검수 항목 | 상태·근거 |
|---|---|---|
| CSV | 첨부 한글 CSV 인식 | PASS: 원본 파일 읽기 및 HTTP 업로드 |
| CSV | 4,680행 전체 처리 | PASS: 확인 화면 4,680행 및 전체 저장 |
| CSV | S01~S08 8개 센서 인식 | PASS: 원문 ID와 센서별 585개 기록 |
| CSV | 측정 시각·온습도 보존 | PASS: 원본 전체 행과 저장값 비교, 고유 시각 585개 |
| CSV | Null 결측 처리 | PASS: 처음에는 모든 좌표 None |
| CSV | 임의 좌표 미부여 | PASS: 확인 전 센서·측정 저장 0건 |
| CSV | Null 온실 ID의 선택 온실 연결 | PASS: 저장 레코드의 대상 온실 확인 |
| CSV | 영문 CSV 호환 | PASS: 기존·신규 테스트 |
| CSV | 중복 저장 방지 | PASS: 원본 2회 처리 후 여전히 4,680건, 충돌 시 롤백 |
| 좌표 | 기존 센서 자동 인식 | PASS: 재업로드 계획에서 기존 센서 인식 |
| 좌표 | 신규 센서 등록 | PASS: 최초 8개 등록 |
| 좌표 | 미설정 좌표 입력 요청 | PASS: HTTP 확인 화면·필수 입력 검사 |
| 좌표 | 크기 범위 및 아치 검증 | PASS: X=25/길이20 거부, 지붕 밖 거부, 실제 0 허용 |
| 좌표 | 다음 업로드의 좌표 재사용 | PASS: 입력 없이 기존 좌표를 폼 초기값으로 사용 |
| 좌표 | 고객별 동일 ID | PASS: 두 온실의 S01 동시 저장 및 분리 조회 |
| 좌표 | 센서 3·6·8·12개 | PASS: 동적 센서·조합 개수 및 계산값 비교 |
| 3D | 센서 수만큼 실제 포인터 생성 | NOT TESTED: 장면 데이터 8개는 검증, WebGL 렌더링 미확인 |
| 3D | 저장 좌표와 실제 포인터 위치 일치 | NOT TESTED: 좌표 변환 구현, 화면 미확인 |
| 3D | 온실 치수의 실제 모델 반영 | NOT TESTED: 장면 치수·변경 검증, 화면 미확인 |
| 3D | 호버 툴팁 | NOT TESTED: 이벤트 구현, 브라우저 동작 미확인 |
| 3D | m 및 상대 % 표시 | PASS(데이터): 예시 1/20=5%, 3/10=30%, 1.5/4=37.5%; 실제 툴팁 화면은 미확인 |
| 3D | 센서 라벨 일치 | PASS(데이터): JSON·좌표 목록 원문 ID; 실제 투영 라벨은 미확인 |
| 3D | 미등록 센서의 허위 포인터 방지 | PASS(조건): position_valid=false, 장면 필터 확인; 실제 화면은 미확인 |
| 3D | 온실 변경 시 포인터 갱신 | NOT TESTED: 서로 다른 온실의 장면 데이터 분리는 PASS, 실제 화면 전환 미확인 |
| 3D | 모바일 탭 선택 | NOT TESTED: 브라우저 제한 |
| 3D | 구조물 겹침·가림 | NOT TESTED: 브라우저 제한 |
| 연동 | 실제 조합 ID 표시 | PASS: 원본 CSV 기반 56개 행 렌더링 |
| 연동 | 선택 조합 포인터 강조 | NOT TESTED: 선택 상태 로직은 PASS, WebGL 마커는 미확인 |
| 연동 | 다른 조합 선택 상태 변경 | PASS(로직): Node에서 행·좌표 목록·aria-pressed 동기화 검사 |
| 연동 | 추천 1위 기본 선택 | PASS: 렌더링 데이터 및 JS 기본 상태 |
| 연동 | 테이블 디자인·가독성 | NOT TESTED: 숫자/헤더 마크업 유지, 시각 검수 미확인 |
| 연동 | 계산값과 표시값 연결 | PASS: 원본 계산 결과 동일성·렌더링 |
| 분석 | 선택 온실만 분석 | PASS: 온실별 테스트 |
| 분석 | DEMO 미혼합 | PASS: source 분리 및 실제 모드의 데이터 부족 안내 |
| 분석 | 동적 조합 수 | PASS: 3→1, 6→20, 8→56, 12→220 |
| 분석 | 학습·검증 분리 | PASS: 시간 순서와 기존 함수 결과 비교 |
| 분석 | 누락 시각 정책 | PASS: 누락 시 전체 센서 공통 시각만 유지, 공통 시각 부족 거부 |
| 분석 | MAE/RMSE 계산 | PASS: 기존 엔진 결과와 전체 결과 구조 동일 |
| 분석 | 참조 평균 한계 설명 | PASS: 실제 데이터 HTML에 안내 |
| 분석 | 실제/DEMO 구분 | PASS: 분기·표시·footer 확인 |
| 품질 | Django 서버 실행 | PASS: 실제 서버 및 HTTP 200 검사 |
| 품질 | 마이그레이션 | PASS: 로컬 적용 및 테스트 DB 적용, 미생성 모델 변경 없음 |
| 품질 | 기존 DEMO 분석 유지 | PASS: 20개 조합·P1~P6·기존 평가 결과 동일 |
| 품질 | 기존 3D 시뮬레이터 | PASS(서버): DEMO 시나리오·렌더링; WebGL 화면은 NOT TESTED |
| 품질 | 다른 페이지 CSS | NOT TESTED: 새 규칙 범위 제한, 실제 시각 회귀 미확인 |
| 품질 | 기존 DB 보존 | PASS: 마이그레이션 전후 전체 행 해시 일치 |
| 품질 | 모바일·데스크톱 화면 | NOT TESTED: 브라우저 연결 도구 오류로 실제 화면 확인 불가 |
| 품질 | 신규 테스트 추가 | PASS: 고객 CSV/좌표/분석·선택 상태 테스트 추가 |

브라우저 연결 시 도구가 `sandboxPolicy` 필드 누락 오류로 시작되지 않아 1440·1920·768·390·430px 화면, 확대 표시, 툴팁 잘림·프레임 가림·모바일 조작·브라우저 콘솔은 확인하지 못했다. 실행하지 않은 시각 검수는 완료로 간주하지 않는다.

## 미구현·추가 확인

- 고객 계정/온실 소유권 모델 및 로그인 UI는 기존에 없어 추가하지 않았다.
- 실제 건축 치수의 처마 높이·연동 동 수가 없어, 단동은 명시한 단순화 형상이고 연동은 경계 공간이다.
- 여러 설치 위치가 한 CSV에 들어가는 파일은 자동 이동 이력을 추정하지 않고 분리 업로드하도록 한다. 저장된 과거 측정 좌표를 유지하며 현재 위치와 차이가 있으면 안내한다. 위치별 기간 필터 UI는 새로 추가하지 않았다.
- WebGL·반응형·터치·키보드 툴팁의 최종 실기기 검수가 남아 있다.
- 기존 문구 불일치 테스트 2건은 해당 화면 요구사항과 함께 별도로 정리해야 한다.

## 실행 방법

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

1. `/greenhouses/add/`에서 실제 온실 치수·형태를 등록하거나 기존 온실을 선택한다.
2. `/analysis/`의 CSV 업로드에서 대상 온실과 파일을 선택한다.
3. 확인 화면의 미설정 좌표를 실제 설치 위치로 입력한다. 기존 위치·변경사항을 확인하고 전체 저장한다.
4. 자동 이동한 `/optimization/?greenhouse=온실ID&mode=real`에서 분석과 위치를 확인한다.
5. 조합 선택 버튼으로 강조 상태를 변경한다. 별도 시뮬레이터는 `/simulator/?greenhouse=온실ID&mode=real`이다. DEMO는 `mode=demo`로 구분한다.

테스트용 좌표는 예시일 뿐 실제 설치 좌표로 사용하면 안 된다. 원본 CSV에는 좌표가 없으므로 실제 사용에는 고객의 좌표 입력이 필요하다.

```powershell
$env:GSO_SAMPLE_CSV='C:\Users\hwang\Documents\카카오톡 받은 파일\센서온습도_.csv'
.\.venv\Scripts\python.exe manage.py test measurements visualization --settings=config.test_settings
node visualization/test_scene_selection.cjs
```

원본 파일 경로를 설정하지 않으면 해당 원본 CSV 통합 테스트 하나만 skip되며 나머지 테스트는 합성 데이터로 실행된다. 이번 검수에서는 경로를 설정해 실제 첨부 파일 테스트를 실행했다.

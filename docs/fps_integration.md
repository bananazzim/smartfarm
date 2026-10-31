# GSO 3.80 1인칭 온실 시뮬레이터 통합 결과

최신 UI 동작은 [2차 개요·색상 개선 결과](fps_ui_overview.md)를 따른다. 현재는 개요 프리뷰를 통해 입장하며 measured는 회색, recommended만 빨강이다. 아래는 1차 통합 당시의 기록이다.

## 1. 통합 상태

`/simulator/`에 Claude의 최종 low-poly 토마토 온실과 1인칭 탐색 화면을 통합했다. 사이트의 메뉴명은 **3D 시뮬레이터**로 유지했다. 기존 `base.html`과 헤더·메뉴를 사용하며 독립 문서의 html/head/body를 중복 삽입하지 않았다.

새 요청에 따라 이전의 DEMO 전용 리다이렉트를 대체했다. 선택 온실이 있으면 기본값은 실제 데이터이며 `mode=demo`에서만 예시 좌표를 표시한다. 실제 모드가 비어 있거나 좌표가 잘못되어도 DEMO로 대체하지 않는다. 실제 모드에서 온실이 없으면 등록 안내를 표시한다.

원본은 프로젝트의 `claude_3d_prototype/GSO 3D 시뮬레이터.html`을 사용했다. setSensors/setRecords/setTime/setGreenhouseConfig/init/destroy/fromRecords/roofAt를 확인했다. 원본 파일의 SHA-256은 아래와 같으며 작업 후에도 일치한다.

`673fcaabb44c97c5cc74a291392696f16965b574361f83e075bd054c2cff02b7`

## 2. 변경 파일

- `templates/visualization/simulator.html`: 기존 독립 시뮬레이터를 새 1인칭 UI로 교체, JSON 전달과 전용 자산 연결.
- `visualization/views.py`: 선택 온실·모드·시점 처리, 렌더링 및 위치 JSON 응답.
- `visualization/urls.py`: 읽기 전용 `/simulator/data/` 추가.
- `visualization/tests.py`: 새 화면·명시적 DEMO·실제 빈 상태 요구사항 검증.
- `optimization/test_selection.py`: 새 시뮬레이터 진입의 실제 모드·최적화 계산 미호출 검증.
- `optimization/tests.py`: 시뮬레이터 제목을 현재 메뉴명에 맞춰 검사.
- `measurements/test_importing.py`: 업로드 후 실제 시뮬레이터 진입 확인.

## 3. 추가 파일

- `static/css/simulator-fps.css`: 원본 디자인을 `#gso-fps` 내부로 한정.
- `static/js/simulator-fps.js`: 원본 장면·입력·마커·API 통합본.
- `static/js/fps-data.js`: 순수 시계열 위치 어댑터·시간 파서·실제 피복 높이 계산.
- `static/js/fps-navigation.js`: 충돌 검사와 안전한 경유 경로 탐색.
- `static/js/fps-bootstrap.js`: 초기 JSON, 로딩 오류, 변경 데이터 갱신·해제.
- `visualization/fps_data.py`: DB 설치 좌표와 위치 이력 경계의 JSON 데이터 구성.
- `visualization/test_fps.py`: 서버 데이터·빈 상태·격리·보안 테스트.
- `visualization/test_fps_data.mjs`: 어댑터·시간대·충돌·경로 단위 테스트.
- `docs/fps_integration.md`: 이 보고서.

검수 보조 파일은 `backups/fps-integration/`와 `backups/scene-fix-fbfb02df/browser_check.py`에 있다. 새 ZIP은 만들지 않았다. 추출 스크립트는 기존 통합본이 있으면 덮어쓰지 못하게 막았다.

## 4. 재사용한 프로토타입 기능

아치 골조·반투명 피복·양쪽 토마토 줄기/잎/열매·중앙 통로·베드/지지대·출입문·환기창·주변 나무/마을·움직이는 작업자 NPC·InstancedMesh·자연광/그림자를 유지했다.

WASD/방향키, Shift, 휠 속도, 마우스 드래그 및 포인터 잠금 시점, R 복귀, 전체화면, 마커 클릭, 목록/상세, 센서 관찰 위치 이동을 유지했다. 1인칭 화면에는 실제 설치 마커를 빨강으로 표시한다. 기존 최적 배치 화면의 추천/비추천 색상과는 별도의 의미다.

## 5. 실제 CSV 연동

기존 CSV 파서·좌표 확인·저장 흐름은 변경하지 않았다.

`CSV 업로드 → 기존 Sensor/Measurement 저장 → 선택 온실 조회 → 위치 이력 압축 → json_script → GSOSim.init()` 순서다. DB에서 DEMO 상태 센서와 DEMO 출처 측정값은 실제 모드에 섞지 않는다. 정적 좌표는 센서에 시계열 위치 기록이 없을 때만 사용한다. 불량 기록의 대체 위치로 정적 좌표를 임의 선택하지 않는다.

정상 측정 기록의 온도·습도 전체를 브라우저에 보내지 않는다. 같은 위치가 반복되면 해당 구간의 시작·마지막 위치 기록만 전달하고, 이동 경계와 동일 시각 충돌은 보존한다. 기존 S01~S08은 4,680개 측정 기록에서 위치 경계 16개로 전달되어 마커는 8개만 생성된다.

실제 모드에서는 15초마다 읽기 전용 위치 데이터를 확인한다. 변경되지 않았으면 장면을 다시 만들지 않고, 변경되면 config/setRecords를 사용한다. 숨긴 탭에서는 갱신을 건너뛰며 종료 시 타이머를 해제한다. 온실 선택 변경은 새 요청으로 이전 인스턴스를 정리한다.

## 6. 센서·좌표·추천 구분

원본 모델은 폭이 0~W인 좌표계를 사용하므로 **Three(X,Y,Z)=(x,z,y)**로 배치한다. 최적 배치의 기존 `toScene()`은 폭 중심 오프셋을 쓰지만 해당 코드와 모델은 수정하지 않았다.

정적 `setSensors()`에는 timestamp가 필요 없다. Null/빈 좌표·NaN/무한대·범위 밖·피복 밖 센서는 오류로 표시하며 좌표를 보정하지 않는다. roofAt은 렌더링의 벽 높이 45%와 24개 피복 패널의 높이에 맞춘다. 온실 크기가 바뀌면 기존 좌표도 재검증한다.

내부 키는 `[positionType,id]`를 JSON으로 직렬화하여 같은 ID의 measured/recommended가 충돌하지 않게 했다. 외부 표시 ID는 자르거나 변경하지 않는다. 기존 최적화는 센서 조합을 평가하며 새 설치 좌표를 생성하지 않으므로, 서버는 해당 조합을 추천 위치로 변환하지 않는다. 별도 추천 좌표가 없으면 추천 링 마커를 만들지 않는다. 타입별 링/라벨과 외부 API의 recommended 입력 지원은 유지한다.

## 7. 유효성·시간대·위치 이력

- 기본 naive 시각은 Asia/Seoul로 해석한다. ISO의 Z/명시적 오프셋은 존중한다. 달력상 없는 날짜·잘못된 시각은 INVALID_TIMESTAMP로 제외한다.
- 같은 센서·타입·시각의 동일 좌표는 중복 위치로 취급한다. 다른 좌표는 POSITION_CONFLICT로 분류하고 해당 센서를 숨긴다. 정상 센서는 계속 표시한다.
- 위치 변경 이력을 정렬하며 서로 다른 위치를 평균 내지 않는다. 이동 센서에 시점이 없으면 선택을 요청한다. 기본 서버 시점은 최신 실제 기록 시각이다.
- 선택 시각 이전의 마지막 확인 위치를 사용하되 최초 기록 이전·최종 확인 범위 이후에는 위치를 추정하지 않는다. 시점 선택 목록과 표시는 한국 시간으로 고정했다.
- 센서 ID·온실명·오류는 textContent와 json_script를 사용하며 HTML로 실행하지 않는다.

## 8. 수정한 문제

원본의 잘못된 시간 허용, 동시 좌표 충돌 누락, 타입별 ID 충돌, 경로상의 NPC 미검사, 자동 이동 중 벽/베드 통과 가능성을 보완했다. 안전한 관찰 위치와 경유 경로를 찾고 이동 중 NPC가 막으면 취소한다. 직접 키 조작 시 자동 이동을 중단하며 선택/상세 정보는 유지한다.

조준점과 안내 pill이 휠·마우스 입력을 가로채던 부분을 pointer-events:none으로 고쳤다. 입력 필드나 사이트 외부에 포커스가 있을 때 이동 키를 가로채지 않는다.

렌더링은 NPC 애니메이션을 유지하면서 최대 약 30fps로 제한하고, 화면 밖/숨긴 탭에서는 멈춘다. 종료 시 RAF·이벤트·ResizeObserver/IntersectionObserver·타이머·공유 geometry/material·그림자 렌더 타깃을 정리한다. 반복 dispose는 안전하며 종료된 인스턴스는 다시 데이터 객체를 만들지 않는다.

## 9. Three.js 호환성

원본 r128 전역 THREE 대신 기존 프로젝트와 같은 **Three.js 0.170 ES module**을 이 페이지에서 한 번 로드한다. 구버전 `*BufferGeometry` 이름을 현재 geometry 이름으로 옮기고 조명 강도를 맞췄다. 원본 HTML은 수정하지 않았다.

기존 `greenhouse-model.js`, `greenhouse-scene.js`, `render-scheduler.js`, `optimization_scene.html`, 통계 엔진과 모델·마이그레이션은 변경하지 않았다. 새 CSS는 전역 body/header/main/aside/button/:root 규칙을 사용하지 않으며 전부 FPS 래퍼 안으로 제한했다. 기존 사이트가 밝은 테마이므로 래퍼는 light 테마를 사용하고 프로토타입의 다크 테마 규칙도 래퍼 안에 보존했다.

## 10. 실행한 검증

| 항목 | 결과 |
|---|---|
| Django check | PASS |
| 마이그레이션 미생성 검사 | PASS: No changes detected |
| 전체 Django 테스트 | 88개 실행, 기존 실패 2개를 제외한 86개 PASS |
| 원본 첨부 CSV 통합 테스트 | PASS: 환경 변수로 원본 CSV 경로 지정 후 실행 |
| 0/1/2/3/6/10개 센서 | PASS: 서버·JS·실제 Chrome API |
| 반복·동시 충돌·이동·잘못된 시간·시점 이전/이후 | PASS: JS 테스트와 Chrome API |
| 한국 naive/UTC/미국 브라우저 시간대 | PASS |
| 누락·범위 밖·지붕 밖·특수문자 ID·타입 중복 | PASS |
| 기존 실제 온실 시각화 | PASS: S01~S08, 등록한 좌표, 콘솔 초기화 오류 없음 |
| WASD·방향키·R·Shift·휠·마우스 드래그 | PASS: 실제 Chrome 입력 |
| 센서 클릭·목록 선택·상세 | PASS: 실제 화면 선택 |
| 전체화면 | PASS: 실제 버튼 클릭 후 fullscreenElement 확인 |
| 벽·베드 충돌 | PASS: 실제 이동 입력으로 경계에서 정지 |
| NPC 장애물·안전 경로·경로 없음 | PASS: 순수 경로 함수 테스트, 실제 자동 이동 시작과 키 조작 중단 확인 |
| 30×7×4 / 50×9×4.5 / 12×6×3.5 | PASS: 실제 장면 재구성 |
| 768/390/430px 가로 넘침 | PASS: 실제 Chrome 뷰포트 검사 |
| 초기화/종료 3회 | PASS: geometry 93개/texture 1개로 일정, 종료 뒤 API 재할당 차단 |
| 기존 최적 배치 3D 실제/DEMO | PASS: 기존 56/20개 조합과 공통 화면 정상 |
| 원본 HTML | PASS: SHA-256 일치 |

기존 실패는 대시보드의 SAMPLE DATA, 알림의 MOCK ONLY 문구 기대값 불일치다. 두 화면 본문을 이번에 바꾸지 않았다.

## 11. 미검증

앱 내 브라우저 도구가 sandboxPolicy 누락 오류로 시작되지 않아 기존에 승인된 별도 Chrome 테스트 프로필로 검수했다. 헤드리스 Chrome은 네이티브 포인터 잠금을 허용하지 않아 **잠금 상태의 마우스 이동과 ESC 해제는 미검증**이다. 드래그 시점은 확인했고 ESC 해제 처리 코드는 포함했다.

모든 운영체제·실물 모바일·GPU별 성능, 장시간 이동하는 NPC와의 모든 접촉 상황은 검증하지 않았다. NPC는 경로 계산과 이동 중 충돌 조건에 포함되지만 모든 동적 상황의 무충돌을 보장한다고 주장하지 않는다.

## 12. 제한과 실행

1인칭 모델은 단동용이며 연동 등록 온실에는 단순화 외형임을 안내한다. 원본의 3m 이상 규격 조건을 유지하며 더 작은 규격은 실패 안내를 표시한다. 설치 위치를 새로 최적화하거나 온도 분포·기류를 계산하지 않는다. 기존 소유자/계정 모델이 없어 새 고객 인증 체계를 추가하지 않았으며 조회는 선택 온실로 제한한다.

모델·DB 스키마 변경과 새 마이그레이션은 없다. 서버를 재시작한 뒤 `/simulator/`에서 온실과 실제/DEMO 모드를 선택한다. 실제 예시는 `/simulator/?greenhouse=1&mode=real`, 예시 모드는 `mode=demo`다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

참고 캡처: `backups/scene-fix-fbfb02df/fps-real.png`.

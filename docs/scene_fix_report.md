# 분석·3D·성능 수정 결과

## 최종 경로·UI 통일

사용자 요청에 따라 독립 실제 데이터 시뮬레이터 분기를 제거했다. `/simulator/`와 `mode=real` 접근은 선택 온실의 `mode=demo` 화면으로 리다이렉트한다. 전용 `customer_simulator.html`, `sensor_locations.html`은 삭제했다.

`/optimization/`의 실제·DEMO 모드는 공통 `visualization/optimization_scene.html`을 사용한다. DEMO와 같은 넓은 온실 영역·추천 메뉴·오른쪽 센서 정보 패널·두 요약 카드 구조로 통일했다. 실제 데이터와 DEMO 데이터는 계속 분리한다. 추천 보기 버튼은 해당 페이지의 3D 영역으로 이동한다.

최종 관련 테스트 10개와 JS 선택 테스트가 통과했다. Chrome에서 두 모드 모두 동일한 1081×720px 3D 영역, 추천 메뉴·센서 정보 패널을 확인했다. 실제 데이터는 56개 조합 및 S03·S07·S08 추천, DEMO는 20개 조합 및 P2·P3·P4 추천을 확인했다. 캡처는 `optimization-unified-real.png`, `optimization-unified-demo.png`이다. 아래 이전 독립 실제 시뮬레이터 설명은 이 최종 변경으로 대체한다.

## 추천 표시·넓이 추가 수정

실제 시뮬레이터의 3D/목록 비율을 DEMO와 같은 2.1:0.75로 조정하고 높이를 동일한 720px 기준(반응형 clamp)으로 맞췄다. 실제 화면에도 기본 선택된 ‘추천 조합 강조’ 메뉴를 추가했다. 센서 좌표를 조회해도 추천 강조가 풀리지 않는다.

DEMO에 남아 있던 센서별 분홍·파랑 고정 색상도 제거했다. 추천 모드에서는 후보 6개 중 추천 3개가 빨강, 나머지가 회색이다. 실제 데이터에서는 S03·S07·S08이 빨강, 나머지 5개가 회색이다. 후보·추천 센서 ID는 분석 결과에서 가져온다.

별도 Chrome에서 두 독립 시뮬레이터를 모두 실행하고 화면을 확인했다. 1920px 화면에서 실제 3D 영역은 약 1040×720px, DEMO는 약 1081×720px이며 두 화면 모두 추천 메뉴와 빨강/회색 표시를 확인했다. 관련 Django 테스트 8개와 JS 선택·구문 검사를 통과했다. 최종 캡처는 `backups/scene-fix-fbfb02df/simulator-real.png`, `simulator-demo.png`이다. 아래에 기록된 독립 화면 미검증 사항은 이번 검수로 해소했다.

## 최종 화면

DEMO와 실제 데이터 화면이 `greenhouse-model.js`의 동일한 `addGreenhouse`, `resetHouseView`, `fitHouseView`를 사용한다. 기존 DEMO의 기본 카메라 방향을 사용하고 화면 크기에 맞춰 크게 표시한다. 실제 온실 치수와 좌표는 변경하지 않는다.

상시 센서 라벨과 연결선은 제거했다. 추천·선택 조합은 빨간 점, 나머지는 회색 점이다. 센서 ID·좌표는 호버·탭 툴팁과 좌표 목록에서 확인한다. 실제 데이터 화면에는 선택한 분석 대상만 표시하므로 기존 DEMO 센서가 끼어들지 않는다.

## 확인한 원인과 수정

- 실제 DB에는 CSV 센서 S01~S08의 585개 시각 외에 12일 전 API 기록 1건이 있었다. 이 센서를 함께 평가해 공통 시각이 0개였다.
- 분석 대상 선택 UI를 추가하고 CSV 저장 후 해당 센서 ID를 전달·기억한다. 기존 링크는 최근 측정 시각의 센서 집합을 기본 선택한다. 전체 센서 선택과 빈 선택을 명시적으로 처리하며 다른 온실 ID는 거부한다.
- 캔버스를 부모 영역에서 분리해 버퍼 크기가 부모 크기를 키우지 않도록 했다. 동일 크기 재설정을 생략하고 CSS·스크립트 캐시 버전을 갱신했다. 과거 회색 화면의 브라우저 오류 로그는 확보하지 못했으므로 그 원인을 캐시 하나로 단정하지 않는다.
- 무한 애니메이션 루프를 제거했다. 회전·확대·선택·크기 변경 때만 그리며 화면 밖과 숨겨진 탭에서는 중단한다. 모듈 실패·WebGL 컨텍스트 손실 시 안내와 다시 불러오기 버튼을 표시한다.
- 학습·검증 분할과 참조 평균을 조합마다 재계산하던 중복 작업을 줄였다. MAE/RMSE 수식·정렬 방식은 유지하며 변경 전 엔진과 원본 CSV의 전체 결과가 정확히 일치했다.
- 분석 화면에서 추천 링크로 시뮬레이터를 열면 강조 ID를 전달해 재계산을 피한다. 독립적인 시뮬레이터 방문에서 추천이 필요하면 한 번 평가한다.

## 검증 결과

| 항목 | 결과 |
|---|---|
| 실제 DB S01~S08 분석 | PASS: 공통 시각 585개, 56개 조합 |
| 원본 CSV 및 선택 기능 관련 최종 테스트 | PASS: 33개 |
| 전체 테스트 실행 | 79개 중 77개 PASS, 기존 문구 검사 2개 FAIL |
| 기존 실패 | 대시보드의 SAMPLE DATA, 알림의 MOCK ONLY 문구 불일치 |
| JS 선택·렌더링 스케줄러 검사 | PASS |
| Django check / 미생성 마이그레이션 검사 | PASS / 변경 없음 |
| 실제 Chrome 1440·1920·768·390·430px | PASS: 3D ready, 가로 넘침 없음, 센서 8개, 표 56개 조합, 상시 라벨 0개 |
| 실제 센서 점 호버·터치·Escape | PASS: 좌표·비율 툴팁 확인 |
| 조합 변경 | PASS: 선택 행과 선택 센서 3개 동기화 |
| 정지 상태 성능 | PASS: 실제 WebGL 추가 그리기 2초 동안 0회 |
| 모듈 로딩 차단 | PASS: 오류 안내, 숨겨진 캔버스, 재시도 버튼, 좌표 목록 8개 유지 |
| 실제 기기 전체 GPU·브라우저 조합 | NOT TESTED: 별도 Chrome 검수 환경에서만 확인 |

마지막 추가 독립 시뮬레이터 시각 검수는 Chrome 연결 종료로 끝까지 수행하지 못했다. 해당 화면은 서버 렌더링 테스트와 DEMO 공통 모델 코드 연결을 확인했으며 독립 화면의 추가 시각 검수를 완료했다고 주장하지 않는다.

동일 CSV 3회 비교에서 변경 전 평가 시간은 약 409~697ms, 변경 후는 232~511ms였다. 환경 변동이 있는 로컬 측정이며 모든 환경에서 같은 개선율을 보장하는 수치는 아니다.

## 데이터 보존

`backups/scene-fix-fbfb02df/`에 작업 직전 DB와 관련 소스를 보존했다. 원본과 현재 DB의 전체 행 비교 결과 온실 1개, 센서 11개, 측정값 4,753개가 모두 일치했다. 측정값과 입력 좌표를 삭제·변경하지 않았다.

## 변경 파일

- `optimization/data.py`, `optimization/views.py`, `optimization/engine.py`, `optimization/test_selection.py`
- `measurements/views.py`, `measurements/test_importing.py`
- `visualization/views.py`, `visualization/test_render_scheduler.cjs`
- `static/js/greenhouse-scene.js`, `static/js/greenhouse-model.js`, `static/js/render-scheduler.js`, `static/js/simulator.js`
- `static/css/brand-refresh.css`
- `templates/base.html`, `templates/optimization/results.html`
- `templates/visualization/sensor_locations.html`, `templates/visualization/customer_simulator.html`, `templates/visualization/simulator.html`
- `docs/scene_fix_report.md`

검수 스크립트·화면 캡처·결과 JSON은 `backups/scene-fix-fbfb02df/`에 있다. 앱 내 브라우저 도구 오류 때문에 사용자에게 승인받은 별도 Chrome 테스트 프로필을 사용했다.

## 확인 방법

현재 개발 서버를 재시작하고 브라우저에서 Ctrl+F5로 새로고침한다. `/optimization/?greenhouse=1&mode=real`에서 분석 대상 S01~S08과 56개 조합을 확인할 수 있다. 3D 추천 링크는 동일 온실과 분석 대상·추천 센서를 시뮬레이터에 전달한다.

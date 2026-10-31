# 센서 색상 점검 및 3D 전용 전체화면

## 실제 원인

온실 1의 DB를 조회했다. 실제 설치 센서는 S01~S08 8개이고, 별도로 DEMO 상태 센서 3개가 있다. 시뮬레이터는 DEMO 상태를 제외한다. 실제 위치 이력을 압축한 payload 기록은 16행이며 8개 ID를 나타낸다. 추천 설치 좌표를 저장하는 모델이나 현재 제공하는 추천 좌표 데이터는 없다. optimization의 recommended는 기존 센서 ID 조합이며 새 설치 좌표가 아니다. 따라서 실제 센서 8개가 모두 회색인 상태가 정상이다.

views.py는 simulator_payload 결과를 전달하고 유형별 고유 ID를 센다. 기존 측정 이력은 positionType 생략 후 measured 기본값을 사용했다. 이번에는 이력에도 measured를 명시했다. 정적 입력에서 position_type 별칭도 지원하도록 보완했다. 추천 위치를 생성하거나 최적화 조합을 새 좌표로 바꾸지 않았다.

## 변경 파일

- visualization/fps_data.py: 측정 이력 positionType 명시.
- static/js/simulator-fps.js: stage 전용 Fullscreen API, fullscreenchange 상태·크기 갱신, 종료 시 Pointer Lock 해제, 정적 유형 별칭 지원.
- static/js/fps-bootstrap.js: 개요 복귀 시 stage 전체화면 종료, 모듈 캐시 버전 갱신.
- static/css/simulator-fps.css: 뷰포트 100vw × 100dvh, 여백·둥근 모서리 제거, 선택 센서 ID·조준점·작은 종료 버튼 유지.
- templates/visualization/simulator.html: 뷰포트 내부 종료 버튼, 캐시 버전 갱신.
- backups/scene-fix-fbfb02df/browser_check.py: 전체화면 대상·화면 크기·반복 복귀·입력 검증 보강.

## 전체화면 동작

페이지 전체 대신 #stage만 전체화면에 진입한다. 내비게이션·헤더·필터·사이드바는 전체화면 대상 밖에 있다. Canvas가 전체 크기를 차지한다. 선택한 마커의 센서 ID만 표시하고 큰 정보 패널은 표시하지 않는다. 종료 버튼과 브라우저 전체화면 종료 이벤트 모두 renderer 크기와 camera aspect를 갱신한다. ResizeObserver도 크기를 동기화한다. 이벤트는 기존 인스턴스 정리 목록으로 해제하며 전체화면 진입마다 새 리스너나 renderer를 만들지 않는다.

## 검증

- visualization 및 optimization.test_selection: 19개 통과.
- measurements.test_importing: 제공 CSV 환경변수를 지정하여 13개 통과.
- JS 데이터·좌표·이동 경로 검사 및 변경 JS 문법 검사 통과.
- 격리 Chrome에서 실제 설치 8개 / 추천 0개 확인.
- 같은 ID와 같은 좌표의 measured / recommended 입력을 동시에 전달해 유형별 마커·halo·ring·leader·foot·목록 색상을 검증했다. 테스트 데이터는 브라우저 메모리에만 넣었다.
- stage가 실제 fullscreenElement인지, Canvas가 화면 전체 크기인지, 사이드바가 전체화면 대상 밖인지 확인했다.
- 3회 진입·종료 후 UI 복구와 렌더러 유지, 전체화면 내 W 이동·마우스 드래그 시점 회전 통과.
- 개요 입장·복귀, 선택·이력 보존 및 768/390/430px 가로 넘침 검사 통과.

네이티브 Pointer Lock과 브라우저 ESC 조합은 headless 환경에서 실기 검증하지 못했다. 종료 시 잠금 해제 코드는 적용했지만 실제 브라우저에서 별도 확인이 필요하다. DB·CSV 원본·스키마·최적화 알고리즘은 변경하지 않았다.

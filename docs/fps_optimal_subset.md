# 설치 센서와 최적 조합 선정 구분

## 원인과 실제 데이터

온실 1 / real 모드의 실제 센서는 S01~S08 8개이다. 기존 visualization/views.py는 위치 payload만 전달했으며 최적 조합 ID를 연결하지 않았다. simulator-fps.js는 positionType만으로 색상을 결정했기 때문에 measured인 8개 모두 회색이었다. 이력 변환 과정에도 조합 선정 속성이 없었다.

기존 최적화는 새 설치 좌표가 아닌 기존 센서 ID 조합을 반환한다. 현재 데이터의 추천 ID는 S03, S07, S08이고, 분석 대상 8개·공통 시각 585개·총 56개 조합이다. 이 세 센서의 positionType은 measured를 유지하고 isRecommended만 true로 전달한다. 새 추천 위치는 여전히 0개이다.

## 변경

- visualization/views.py: 기존 evaluation_context와 request_sensor_ids 재사용. 같은 온실·real/demo·세션/명시적 분석 대상 조건으로 현재 DB를 평가해 추천 ID를 연결한다. 결과와 분석 범위 메타데이터를 payload에 전달한다. 클라이언트 highlight를 신뢰하지 않는다. 갱신 URL에도 명시적 센서 조건을 보존한다.
- static/js/fps-data.js: 이력 변환에서 isRecommended 유지.
- static/js/simulator-fps.js: 설치 유형과 별개로 isRecommended에 따라 마커 전체·목록·라벨 색상 변경. 실제 설치 표시와 최적 조합 선정 표시를 함께 제공한다. 기존 별도 추천 후보 위치는 유형을 유지한다.
- static/js/fps-bootstrap.js: 선정 개수·선정 ID·분석 대상 수·공통 시각 표시, 새 모듈 캐시 버전.
- templates/visualization/simulator.html: 선정 센서 수와 별도 추천 위치 수를 구분하고 범례·안내 수정.
- optimization/test_selection.py, visualization/test_fps_data.mjs: 조건 일치·추천 없음·데이터 변경·온실 격리·이력 속성 검증.
- backups/scene-fix-fbfb02df/browser_check.py: 실제 데이터 추천 ID와 마커/목록 색상 검증 갱신.

저장된 분석 결과 테이블은 현재 구조에 없다. 기존 분석 함수를 현재 조건으로 재사용하므로 오래된 ID를 별도 저장해 재활용하지 않는다. 최적화 알고리즘·DB 스키마·CSV 원본은 수정하지 않았다. 위치 이력 시점 선택은 표시 좌표의 시점을 바꾸는 기능이며 분석 기간 필터가 아니다. 추천은 기존 최적 배치와 같은 전체 선택 데이터 범위로 계산한다.

## 검증

- 관련 Django 테스트 19개 통과.
- JS 데이터·이력·좌표·안전 이동 검사 및 문법 검사 통과.
- 실제 DB의 최적 배치 결과와 시뮬레이터 payload 추천 ID가 S03/S07/S08로 일치.
- 격리 Chrome에서 센서 8개 모두 measured 유지, 빨간 마커 3개·회색 5개·빨간 목록 아이콘 3개 확인.
- 추천 없는 조건 및 다른 온실, 데이터 삭제 시 추천 0개 검사 통과.
- 개요 입장·복귀·이력/선택 보존·전체화면 반복/키보드/드래그 검사 통과.
- 기존 최적 배치 브라우저 검사: 실제 56개 조합 S03/S07/S08, DEMO 20개 조합 P2/P3/P4 및 레이아웃 정상.

네이티브 Pointer Lock/ESC의 실기 검증 제한은 이전 보고와 동일하다.

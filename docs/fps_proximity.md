# 근접 정보 표시와 조준점 제거

원인: 기존 라벨은 거리 6m 또는 선택 상태로 정보를 확장했고, 전체화면 CSS가 미선택 라벨 및 i/em 정보 요소를 숨겼다. 프레임마다 조준점 hover를 raycast로 갱신했다.

변경 파일:
- static/js/simulator-fps.js: 카메라와 마커 월드 좌표의 실제 3D 거리로 3m 진입/3.5m 이탈 판정. ID·설치 유형·최적 조합 선정 여부·높이·xyz 라벨, 화면 밖 숨김 및 겹침 보정. 조준점 처리 제거. 클릭 선택과 Pointer Lock은 유지.
- static/js/fps-proximity.js: 거리 히스테리시스와 화면 내 라벨 배치 함수.
- static/css/simulator-fps.css: 전체화면 정보 숨김 및 조준점 규칙 제거, 대비 높은 작은 정보 카드와 페이드 효과.
- templates/visualization/simulator.html: 조준점 DOM 제거 및 캐시 버전.
- static/js/fps-bootstrap.js: 모듈 캐시 버전.
- visualization/test_proximity.mjs: 거리 경계·히스테리시스·겹침·화면 경계 검사.
- backups/scene-fix-fbfb02df/browser_check.py: 일반/전체화면 근접 라벨 검사.

검증:
- 관련 Django 테스트 19개 통과.
- JS 거리 및 기존 데이터/경로 검사 통과.
- Chrome에서 5m 숨김, 2.9m 표시, 3.2m 유지, 3.5m 숨김, 이후 3.2m 숨김 유지, 2.9m 재표시 확인.
- 같은 위치의 두 센서 라벨 분리, 뒤쪽 센서 숨김, 조준점 DOM 없음 확인.
- 전체화면에서도 두 라벨과 높이/좌표 정보 표시, 뷰포트 크기 일치 및 반복 복귀 정상.
- 실제 S01~S08 및 추천 S03/S07/S08 색상 일치, 이력·선택 보존 확인.
- 키보드/드래그, 벽·베드 차단, 클릭 선택·자동 이동 검사 통과. NPC 통과 설정 및 애니메이션 코드는 변경하지 않았다.

Fullscreen API 대상인 stage 내부에 라벨을 유지한다. 라벨 위치는 매 프레임 현재 뷰포트 치수와 카메라 투영으로 갱신한다. 벽·베드·CSV/최적화 알고리즘은 변경하지 않았다. 네이티브 Pointer Lock/ESC의 실기 검증 제한은 이전과 동일하다.

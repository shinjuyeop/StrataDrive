# M10 v4 실제 카메라 위치의 도로 맞춤 준비 기준

2026-11-09. V3의 정답·점수·실패를 보존하고 다음 정확도 평가 전에 배치와 가시성을 검증한다.
이번 단계는 모델 추론/후보 선택 없이 준비 데이터를 만드는 범위다. 정확도·live20Hz·주행 수용은 별도다.

Town03_Opt의265개 spawn에서 driving waypoint를1m씩42m 추적한다. 갈림길은 직전 heading과
변화가 가장 작은 쪽, 동률은 road/section/lane/s/id 순으로 고른다. 사용한0–6번 위치·경로 전체의 junction·
좁은 차로·42m 내 heading변화15° 초과·카메라 frustum 밖의 site는 제외한다. 서로 다른 road ID이며50m 이상 떨어진
첫 두 적합한 위치를 선택하며 영상이나 모델 점수로 순위를 정하지 않는다. 원래 조사265개 route를 새 규칙으로 재생한 선택은14/24번이다.
초기14/18번의 두 번째 site는 경로 중간 교차로의 실제 lane 대조에서 거절되어1pair만 저장했다.
그 실패와14번99pair를 보존하고, 공통 계획 hash를 새로 고정해 두 site를 전체 재수집한다.

객체는 해당 거리의 실제 road node 위치·높이·pitch/roll과 right vector에 맞춰 배치한다.
Base actor origin의 도로 대비 clearance와 기존 asset별 z offset을 유지한다. Center는 차로
경계에서20cm 안쪽이어야 한다. 준비에서 실제 nearest driving lane의 road/lane ID를 대조하고
projection2m·clearance오차15cm, settled pose2cm/각도0.1°를 요구한다. 카메라 pose도 대조한다.
이는 map/정지 fixture 검사이며 충돌 mesh의 정확한 지면·동적 주행의 물리 적합성은 아니다.

미래 개발/보류 각각81개 계획을 두 실제 site에서 검사한다. 준비는 각81개와 가림 없는 참조18개,
각99개·총198개다. 평가와 준비는 동일 site이며 준비 actor의 route 거리는1m 더 멀고 카메라는
5cm 높다. RGB byte를 재사용하지 않기 위한 별도 준비 배치다. 최종 실제 평가의 coverage도
다시 검사해야 하며 준비 PASS가 다른 광학 pose의 가시성을 보장하지 않는다.

14/24 준비에서 held walker0010의31m far가24pixel로 실패해, 향후 평가 far를30→26m,
준비 far를31→27m로 명시한 v4c로 전체 재수집한다. 이 조건의30m 이상 인지/가시성은 수용하지 않는다.
기존25pixel/side4는 유지하며 모델 점수로 배치를 고르지 않는다.

RGB640×384/FOV90/Epic/postprocess on, world10ms·settle40tick 뒤 고정 capture tick5를 사용한다.
기존 Pedestrians12/Rider13→person, visible25pixel·side4 정책을 유지한다. 모든 계획 actor와
모든 이륜차의 Rider13 person이 포함 정답이어야 한다. 각 class×near/medium/far/occluded는3/3,
가림/참조 visible support 비율은0초과·95%미만이어야 한다. 배경 객체로 누락 target을 대신하지 않는다.

이전 v1/v2/v3 평가·준비와 추론에 쓰지 않은 종료 실패 영상도 hash로 제외한다. 준비의 raw RGB/
instance, plan·source·SDK/map identity·모든 실패와 서버 종료를 보존한다. 준비 FAIL은 미래
정확도 평가 freeze 이전에만 수정할 수 있고 원래 실행을 덮어쓰지 않는다. Startup180s·capture900s·
shutdown30s를 유지한다. 초기 조사 스크립트 문법 오류의 실행도 FAIL로 보존한다.

두 site의 원본에서 RGB/정답·pose/road readback·coverage/가림을 재구성하고 plan을 survey에서
재생성한다. 준비 결과는 별도의 미래 평가 입력이지 새로운 holdout 정확도 점수가 아니다.

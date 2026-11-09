# Domain data v1 가림 coverage의 추가 수집

모델 없는 첫 validation255장의6class×기상×방향/거리 coverage는 PASS지만,
WetCloudyNoon person 가림은 참조 대비 .96347로 기존 0초과/.95미만을 실패했다.
원래255장·coverage FAIL·1020개 계획과 source freeze를 덮어쓰거나 표본을 삭제하지 않는다.

각 원래 site에 person의 lateral .6/.85m 두 위치×3기상×가림/참조를 추가한다.12장/site,
총48장이다. 원래 계획1020장과 합쳐1068장(train801/validation267)이다. 나머지 pose·색·camera·
날씨·semantic/Rider·최소 지원·가림 기준·site/asset 분리는 유지한다. 이 확장은 모델/예측을
읽지 않은 개발 데이터 준비이며 quality holdout 또는 후보 재지명이 아니다. 127번은 수집하지 않는다.

원래 수집은 original161-source freeze, 추가48장은 별도 extension source/plan freeze를
RPC 전에 만든다. 기존 extractor를 유지하고 versioned extension extractor가 같은 raw/label
정책을 사용한다. 최종 bundle은 두 capture freeze·계획·각 raw/prepared hash를 연결한다.
원본·추가 collection의 모든 RGB·작은 양성 fragment·실제 가시성을 보존하고,
각 split의 원래 방향/거리와 전체 가림 coverage를 같은 gate로 다시 검사한다.

학습·새 모델 정확도·runtime 승격은 별도다. 기본 S와 과거 M10 품질 근거를 유지한다.

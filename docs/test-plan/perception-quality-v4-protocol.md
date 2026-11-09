# M10 V4 도로 맞춤 새 정확도 평가 사전 기준

2026-11-09. [도로 준비](evidence/m10_road_preparation_v4/README.md)의 봉인된
`perception-road-evaluation-v4.json`을 사용한다. 개발14/보류24번에서 각각 새81쌍을 수집한다.
동일 site의 준비198장과 모든 과거 완전/부분 표본을 포함한1387개 RGB hash와 이번 종료 실패/진단/metadata 실패324개를 합친1711개를 제외한다.
고정된 Town03의 정지 배치이며 지리적으로 독립된 일반화·전체 ODD·주행 성능은 별도다.
작은 보류 보행자의 far는26m다. 그 조건의30m 이상 가시성·정확도를 수용하지 않는다.

후보는 기존 `baseline`, `medium-v3`, `medium-refine-v3` 구현 그대로다. V4는 모델 변경이
아닌 도로 맞춤 새 평가의 버전이다. 모델 hash·RGB unscaled tensor·score0.35·class별 NMS0.5·
고정 중앙2배 확대·경계2pixel·max100을 유지한다. 차량 class 사이 억제는 없다.
준비 RGB의 독립 tensor·CPU/CUDA/OpenCV raw 비교를 다시 검사하고 실행 코드를 freeze한다.

정답은 Pedestrians12/Rider13을 person으로 합친 strict visible tight box, IoU≥0.5,
최소25pixel/side4다. 작은 객체 ignore 진단은 점수 gate를 바꾸지 않는다.
계획 actor의 settled pose2cm/모든 각도0.1°·실제 lane ID/projection2m/clearance15cm를
수집과 원본 재구성에서 검사한다. 모든 계획 actor와 모든 이륜차 Rider13을 실제 정답에서
다시 확인한다. 배경 객체로 누락된 계획 target을 대체하지 않는다.

V3의 절대·상대·coverage 기준을 낮추지 않는다. Micro precision≥.85, recall≥.8,
각 class recall≥.7, near person recall≥.9, negative FP/frame≤1/3이다.
각 class의 primary target9개 이상·각 near/medium/far/occluded2/3 이상, rider12개 이상과
전체7strata/negative3개가 필요하다. 모든 계획 actor/rider의 포함도 별도 gate다.
상대 채택은 baseline보다 precision+.03 이상과 micro/class/far/occluded recall·near person TP
무하락, negative FP 무증가를 요구한다.

개발셋에서 세 후보를 실행하고 relative PASS→F1→recall→precision→ID 순서로 하나를
봉인한다. 해당 selection을 보류 서버 시작 전에 복사하며 보류에는 baseline과 지명 후보만
실행한다. 개발이 실패해도 지명은 진단용으로 하나 고정하며 자동 채택하지 않는다.
보류 결과를 본 뒤 표본·gate·모델·threshold를 수정하거나 다른 후보로 재탐색하지 않는다.
실패도 원본·판정·모든 모델 오류와 함께 보존한다.

RGB-only runner는 GT/scene metadata를 모델에 전달하지 않는다. 정답·점수는 별도 scorer가
계산한다. Cold call·초기화·모든 시간과 offline100ms admitted를 strict raw 점수와 분리한다.
채택 검토에는 개발·보류의 절대·상대·coverage가 모두 필요하다. 자동 runtime 교체·C++ 발행·
차량 제어는 없으며 실제 wall20Hz·renderer 장기 안정성·metric fusion은 별도다.

모든 실제 서버는 전용2300–2302·Epic/postprocess on·fixed seed·기존 UE/CARLA source를
사용한다. Startup180s/capture900s/shutdown30s와 종료130 기준을 유지한다.
Raw BGRA/instance에서 RGB/GT/geometry/seal을 재구성하고 점수·지명·순서·중복을 재감사한다.

초기 V4의 정답 metadata에서 capture_sha256 연결이 누락되어 첫 S 추론 뒤 scorer가 거절했다.
원래 freeze·원본·예측·실패를 보존하며 후보 지명/보류 수집은 하지 않았다. v4b는 해당 metadata
연결만 보강하고 원본→준비→점수의 독립 회귀 검사를 추가한다. 모든324개 실패/진단 영상을
제외 목록에 합친 뒤 새 freeze와 새 실제 개발/보류로 재시작한다. 모델·gate·배치 범위는 유지한다.

# M6 SIL physical-response-v1 — 실행 전 고정 protocol

2026-10-22. 시작 HEAD/origin/main729455f, fetch 후 일치, clean, AGENTS.md 없음.
사용자는 현재 모델에서 계산한 시한 적용을 승인했다. 기존 실패 원본/분모는 보존한다.

## 산정과 적용 기점

현재 DriveController.response 범위 −200..+300Nm, 보호 zero rate2000Nm/s,
완료 abs(T)<=1Nm: 양수149.5ms, 음수99.5ms. 정상 rate1000Nm/s/delay50ms는 유지.
PhysicalOwner brake fixture: max1.5MPa, initial0.2MPa, 정상 해제 후 최저0Pa,
보호 floor1MPa, 상승5MPa/s, 하강10MPa/s. 보호는 높은 압력을 낮추지 않는다.
보호 request_zero/request_protection은 정상 pending/delay50ms를 취소한다.
최저0→1MPa는200ms(초기0.2MPa라면160ms). 토크와 제동은 병렬: max(149.5,200)=200ms.

M6 actual 완료는 기존 최소100kPa가 아닌 **실제 보호 floor1MPa 및 abs(T)<=1Nm**다.
선택→완료 관측 예산은200+출력 인계4+모델 실행4+CSV 관측10+명시 여유12=**230ms**.
새 bounded500us 관측도 남기지만10ms legacy CSV의 관측 예산을 보수적으로 포함한다.
각 실제 모델 step의 완료 샘플은 연속 물리 crossing의 정확한 시각이 아니다.
직전 미완료~최초 완료 모델 시각으로 crossing을 bracket한다. API 적용도 step 전후 구간이다.
원래 모델/rate/expiry/source/20ms envelope/2ms opportunity/4ms guard는 변경하지 않는다.

마지막 유효 command 수신→상실 검출<=100ms(기존). 각 Zone 로컬 검출→해당 Leaf 보호 목표
선택<=4ms(기존2ms 실행 기회/4ms guard 내 처리; 새 물리 예산과 별도).
전체 실제 완료는 가장 이른 post-injection 로컬 목표 선택+230ms 이내이며,
주입→완료와 마지막 RX→검출도 각각 보고한다. 보수적인 연쇄 예산100+4+230=334ms는
마지막 RX 기점의 모델 한정 상한이며 통신/권한 수명을 연장하는 값이 아니다.

## 유한 검증

- 실제 모델 결정론적 시험: +300/−200→0, brake0/initial0.2MPa→1MPa, 보호 delay 취소,
  경계 산식과 최대 범위의 양립성. 실제 미응답/늦은/누락/음수 torque 오판은 Python 판정 회귀로 거부.
- 옛 command-loss 원본을 새 계약으로 별도 재분석1회. raw exit1/100ms FAIL을 변경하지 않는다.
  옛 기록의 실제 적용/미세 crossing 부재는 UNKNOWN; 새 실행 수용 근거를 대체하지 않는다.
- 최종 실제 SDK Normal FIFO quiet command-loss1, nominal energy normal1.
  CPU Central1/FIFO11, Front2/Rear7 FIFO18, plant3/FIFO19, monitor0/FIFO20,
  SDK4/5/6 OTHER0. 기존 주입 전 정상 제어/이동 조건과 원래 입력 유지.
  정상8s+tail2.5s, supervisor25s/기존 준비·정리 timeout 유지. 성공까지 반복하지 않는다.
- 변경 경계 C++ Normal/ASan/TSan 각1회 및 관련 Python 회귀; build/ 없는 source export에서 Python.
  공통 실행/제어/물리 알고리즘 변경 없음이면 전체 회귀는 미실행. 공통 코드 변경 시 최종 Normal/ASan 각1회.
- 경고/미완료/누락/예상 밖 SDK 오류/강제 cleanup은 exit1. 정상 성능과 보호 성공은 별도.
- 기존 sanitizer SDK 실패는 OPEN으로 보존, 전체 SDK sanitizer 재실행하지 않는다.
  charge-zero/owner-pause/rejoin/부하/48회/Jetson/M7/M8은 변경 영향 없으면 NOT RUN.

빌드·시험 독점 lock build/.m4-exclusive.lock. wall 측정 중 검색/빌드/분석 병행 금지.

개발 replay: 같은 실제 모델 test `ModelCompletionAgainstSelectedDeadline`을
`STRATADRIVE_M6_REPLAY_DEADLINE_NS=100000000`으로1회 실행해 과거100ms 기준의
범위 불일치(expected FAIL)를 저장하고, JSON의230000000으로1회 실행해 PASS를 확인한다.
입력·rate·target은 동일하다. 원래 과거 실제 사건을 똑같이 재현했다는 주장은 아니다.
공통 header의 진단 snapshot/기존 brake config 단일 getter를 추가했으므로 보수적으로
최종 전체 Normal/ASan 각1회를 실행한다(물리/제어/실행 알고리즘은 변경하지 않음).

## 첫 실행 후 수정과 추가 실행 근거

5f1ef49 SDK nominal normal은 PASS. command-loss는 actual 완료219.318ms(주입),
200.395ms(최초 선택)이나 새 oracle가 local detection-to-selection에서 FAIL했다.
`pre_shutdown_protection`은 synchronous poll/보호 처리 후의 관측 시각이며 실제
Actuation.issued_time보다3.5/2.7us 늦었다. 검출 기점으로 사용할 수 없다는 관측/판정 결함이다.
시한을 완화하지 않고 step 진입~최초 fault 관측을 bounded event로 기록한다.
실제 Drive command-expired 시각/마지막 유효 RX도 별도 유지한다.
수정 전 실패 원본을 보존하고 서비스 구간 의미의 Python 회귀를 추가한다.
추가 실제 실행은 변경된 fault 관측/판정의 command-loss1회만이다. nominal 정상 경로와
모든 물리/제어 알고리즘은 동일해 기존 새 normal1회 결과를 유지하고 반복하지 않는다.
최종 전체 Normal/ASan 및 경계 TSan은 이 수정 후 소스에서 실행한다.

물리 budget의4ms output handoff는 **최초 로컬 목표 선택부터 양쪽 실제 출력 적용까지**로
최종 offline oracle에서도 검사한다. Zone 선택의 시차를 무시하고 각자의 기점으로230ms를
허용하지 않는다. 해당 Host profile의 판정값이며20ms transport envelope 변경이 아니다.
추가 SDK 실행 없이 보존한 완전한 step/event 근거를 최종 oracle로 재평가한다.

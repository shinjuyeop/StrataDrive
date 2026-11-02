# 종방향 제어 모델·C++ 동등성 검증

2026-10-29, protocol `speed-pi-equivalence-v1`. 실행 전 기준 commit
`f9cef7d98ef733de9f09da437c6b9c290572c4da`, 작업 트리 clean.
M8 첫 component 범위: 독립 Python 설계 모델을 수작업 C++17로 이식하고 동일 입력으로 비교한다.
차량 폐루프·Central 권한 연결·CARLA·wall timing은 후속이며 이 결과에 포함하지 않는다.

## 기준과 입력 영역

- 기준 모델: `models/longitudinal/model.py`, `m6-pi-v1`, SHA256
  `181297fb101d0f7dc69222489956a3bdcc701924556fa2210e4ff5705975e858`.
  기존 Python source와 계수를 유지한다. C++는 Python 또는 공통 production 제어 함수를 호출하지 않는다.
- binary64 / round-to-nearest, C++ `double`의 IEC559·53bit 정밀도를 검사한다.
  GNU/Clang에서 fast-math와 FP contraction을 끈다. 적분 갱신 전 출력 계산 등 연산 순서를 유지한다.
- epoch는 uint32, sequence와 ns 시각은 uint64의 nonnegative 영역이다.
  Python arbitrary integer의 그 밖 영역은 C++ API 계약에 포함하지 않는다.
  차감 전에 순서를 검사해 시각 역행·uint64 경계에서 wraparound를 만들지 않는다.
- 입력은 `now_ns`, target(m/s), optional speed sample(epoch/sequence/source_ns/speed_mps), permission이다.
  source와 now는 같은 논리 clock domain이다. 정상 target은 [0,40/3.6], speed는 finite·nonnegative다.
  NaN/±Inf·음수·missing 입력도 거부 경로 검증에 포함한다.
- 20ms 고정 step, speed age는 60ms까지 포함, Kp1/Ki0.2, [-5,2]m/s²,
  slew2m/s³, 감속 preview120ms와 conditional integration을 유지한다.
  상세 수식은 [M6 계약](../interfaces/simple-vehicle-model.md#mil--도구-결정)을 따른다.
  이 60ms 모델 경계는 실제 Drive30ms freshness를 대체하지 않는다.
- `initialize`는 strictly newer nonzero epoch만 수용한다. 거부한 INIT는 상태를 바꾸지 않는다.
  Invalid step은 fault만 latch하고 마지막 정상 제어 상태를 보존한다. 출력 acceleration은 absent다.
  fault 이유의 검사 순서와 invalid 출력의 원래 speed source도 비교한다.

## 공통 vector와 판정

공통 UTF-8 line protocol을 파일에 저장한 뒤 **그 파일을** Python과 C++가 각각 읽는다.
`new case_name`은 시험 객체 생성, `init epoch`는 명시적 모델 INIT,
`step now target permission present [epoch sequence source speed]`는 한 번의 호출이다.
Bool은 0/1, integer는 십진수, double은 round-trip 십진수와 `nan`/`inf`/`-inf`를 사용한다.
`new`는 시험 격리를 위한 새 객체이며 ECU reset 또는 정상 runtime 복구 API가 아니다.

각 event의 operation/case/index, INIT 수용, output validity/reason/acceleration/integral/source와
전체 관련 state(epoch/integral/previous/last_ns/sample/fault/target)를 비교한다.

- Bool·enum·문자열·optional presence·정수·행 수·순서는 **정확히 일치**해야 한다.
- Finite 부동소수점은 `abs(cpp-python) <= 1e-12 + 1e-12*max(abs(cpp),abs(python))`.
  가속도·적분·이전 출력·target·cached speed에 같은 규칙을 적용한다.
  출력 NaN/Inf는 실패다. signed zero는 모델의 numeric equality와 같이 동등하게 취급한다.
- 한 필드라도 불일치하면 전체 FAIL. 최초 불일치 위치와 case별 event/step 분모,
  필드별 최대 절대 오차를 기록한다. 허용 오차를 결과에 맞춰 늘리지 않는다.
- 입력 누락/추가·잘못된 문법·binary nonzero exit·timeout·출력 절단·비유한 출력도 FAIL.
  Comparator 자체에 행 누락/순서·validity·state·source·허용 오차 초과 손상을 넣어 거부를 확인한다.

## 고정 case family

1. 기존 87s MIL의 20Hz speed 원천을 유지한 20ms controller 입력 replay.
   `mil.py` SHA256 `d34ad472c240f91aa41809f8a54f0e2e062b091a66c7cba0ee5d84fed69fc3f3`.
   MIL의 Python plant에서 얻은 속도를 공통 입력으로 동결한다. C++ 차량 폐루프로 세지 않는다.
2. 속도 유지·증가·감소·0 target, 지속 양/음 포화와 회복, 적분 누적·해제,
   amplitude/slew 경계와 인접 binary64 값, feedforward·감속 preview/zero clamp.
3. 20ms±1ns·누락·중복·역행, age60ms±1ns·future, cached sample 유지·변조,
   sequence/source 역행·같은 source에 새 sequence, wrong epoch, missing/NaN/Inf/음수,
   permission loss, 여러 fault의 우선순위, fault 뒤 정상 입력과 old/new INIT.
4. uint32 epoch와 uint64 time/sequence 최댓값, signed zero·최소 subnormal·큰 finite speed.
5. 고정 seed32776의 유한 multirate 입력과 fault/reinitialize 조합.
   Generator source와 생성된 공통 입력의 SHA를 실행마다 보존한다.

## 실행과 기록

Normal Debug·Release 및 ASan/UBSan 각각 C++ 계약 시험과 동일 vector replay를 실행한다.
새 component는 단일 owner·무공유 상태이며 이번 범위에 thread/IO를 추가하지 않으므로 TSan은 대상이 없다.
현재 compilation database로 변경 C++를 정적 분석한다. 기존 Python 전체 시험과 C++ 기본·논리 회귀를
실행한다. wall 시험이 필요한 전체 회귀는 빌드·다른 시험과 겹치지 않게 직렬 실행한다.
`BUILD_TESTING=OFF`에서도 production library를 빌드한다.

CMake의 `STRATADRIVE_LONGITUDINAL_EQUIVALENCE=ON`에서 Python3.10+와 replay 시험을 명시적으로
활성화한다. CTest는 실행마다 새 evidence directory를 사용한다. 수동 실행도 새 output만 받는다.
Plan/input/model output/C++ output/result·stderr·명령/exit code·source/binary/tool hash를 보존한다.
실패는 별도 attempt로 남기고 수정 이유를 기록한다. 최신 상태·추적표는 결과 확인 후 갱신한다.

이 검증은 TC-CTRL-002–004의 controller component와 TC-COM-005/TC-ZON-003의
source/INIT 경계에 연결한다. 기존 system TC의 차량 성능 판정을 PASS로 바꾸지 않는다.

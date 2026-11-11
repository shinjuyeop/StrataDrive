# 요구사항 추적성

Reference Baseline v0.1 + RG-01 + EV-01 + ZON-01 v0.5의 Requirement → component → interface →
scenario/test → Result 연결이다. 개별 revision은 [시스템 요구사항](../requirements/system-requirements.md)이 기준이다.
현재 부분 검증과 OPEN은 [프로젝트 상태](../project-status.md), 실제 함수·시험·근거는
[component 추적표](component-traceability.csv)에서 관리한다.

SYS-DIAG-001의 검출·보호·Actual·DTC와 복구·clear는 C-M9-*의 구체 시험·원본에 연결한다.
기동/전달/발행자 재기동·로컬/native 서비스·Clock/Power·유한 보존의 분야별 근거는
[검증 안내](README.md#진단-분야별-근거), 선언한 유한 Host·simulation10ms의 종료 판정은
[프로젝트 상태](../project-status.md)를 따른다. 이전 component 실행 당시의 미구현 경계는
각 evidence에 보존하며 최신 통합 상태와 구분한다.

[M8 종료 검토](../archive/milestone-reviews.md#m8)는 C-M8 component/고정 fixture의 기술 판정이다.
아래32개 요구와29개 system TC의 **전체 system/Target runtime Result는 NOT RUN**이다.
부분 Host/vCAN·모델·sanitizer 통과를 전체 결과로 올리지 않는다. 실제 실행 후에만
`RES-<test-suffix>-<run-id>`를 발급한다. 과거 판정은 [단계 검토](../archive/milestone-reviews.md),
실행별 원본·분모는 [evidence 안내](README.md)를 따른다.

| Requirement | Component | Interface | Scenario / variant | Test Case | Future verification | Future Result |
| --- | --- | --- | --- | --- | --- | --- |
| SYS-ARCH-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Deployment | TC-ARCH-001 | M5/M12 | NOT RUN |
| SYS-ARCH-002 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01–S03 | TC-CTRL-001 | M2/M6/M7 | NOT RUN |
| SYS-ARCH-003 | ARCH-CENTRAL, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-VECU, ARCH-BMS, ARCH-ADAPTER, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-SESSION, ARCH-CENTRAL-BRIDGE | IF-CENTRAL-VEHICLE-REQUEST, IF-CENTRAL-POWER-REQUEST, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-CAN-BMS, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | ZON-S01, ZON-F01, ZON-F02 | TC-ZON-001, TC-ZON-002, TC-ZON-003 | M4/M5/M6/M7/M9/M12 | NOT RUN |
| SYS-ODD-001 | ARCH-ORCH, ARCH-HOST, ARCH-CENTRAL | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M7/M8 | NOT RUN |
| SYS-COM-001 | ARCH-ZONE, ARCH-VECU | IF-CAN-STEERING, IF-FAULT-EVENT | F01 | TC-COM-001 | M2/M4/M9 | NOT RUN |
| SYS-COM-002 | ARCH-ZONE, ARCH-VECU, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | F02 | TC-COM-002 | M1/M2/M4/M5 | NOT RUN |
| SYS-COM-003 | ARCH-ZONE, ARCH-VECU, ARCH-BMS, ARCH-ADAPTER, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE, ARCH-CENTRAL-SESSION | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F01–F04; 각 stream loss, EV-F01/02 critical stream; ZON-F01/F02 | TC-COM-001, TC-COM-002, TC-COM-003, TC-COM-004, TC-COM-005, TC-SAFE-001, TC-EV-002, TC-EV-004, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M5/M6/M7/M9 | NOT RUN |
| SYS-COM-004 | ARCH-ZONE, ARCH-ADAPTER, ARCH-BMS, ARCH-VECU, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-BRIDGE | IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-DDS-ZONE-STATUS, IF-HOST-ACTUATOR, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-HOST-EV-STATUS, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F01 cached replay; EV-F01 cached dependency; ZON-F01/F02 | TC-COM-005, TC-EV-002, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M5/M6/M7 | NOT RUN |
| SYS-CTRL-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC, ARCH-CENTRAL-BRIDGE | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01–S03; response perturbation | TC-CTRL-001 | M2/M6/M7 | NOT RUN |
| SYS-CTRL-002 | ARCH-ADAPTER, ARCH-CENTRAL-BRIDGE | IF-HOST-ACTUATOR | F01; missing/invalid/stale actual | TC-COM-001, TC-COM-005 | M4/M6/M7 | NOT RUN |
| SYS-CTRL-003 | ARCH-ADAPTER, ARCH-HOST, ARCH-ORCH | IF-HOST-ACTUATOR | S01–S03; writer audit | TC-CTRL-001 | M6/M7 | NOT RUN |
| SYS-CTRL-004 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-005 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CAN-STEERING | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-006 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CAN-STEERING | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-007 | ARCH-CENTRAL, ARCH-SAFETY, ARCH-ZONE, ARCH-VECU | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | S01, S02, S03 | TC-CTRL-002, TC-CTRL-003, TC-CTRL-004 | M6 precursor; M7/M8 | NOT RUN |
| SYS-CTRL-008 | ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC | IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | RG-01 정상/한계 변화/저속 | TC-REG-001, TC-REG-002, TC-REG-003 | M2/M4/M6/M7 | NOT RUN |
| SYS-CTRL-009 | ARCH-VECU, ARCH-ADAPTER | IF-CAN-DRIVE, IF-HOST-SENSOR, IF-HOST-ACTUATOR | RG-01 에너지/command≠actual/정지 | TC-REG-005 | M2/M6; M7 mapping review | NOT RUN |
| SYS-AI-001 | ARCH-CENTRAL, ARCH-SAFETY | IF-CENTRAL-TRAJECTORY, IF-FAULT-EVENT | AI invalid/timeout variants | TC-AI-001 | M11 | NOT RUN |
| SYS-SAFE-001 | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-VM | IF-DDS-ZONE-STATUS, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS | F01–F04; actuator/compound loss | TC-SAFE-001 | M2/M4/M6/M7/M9 | NOT RUN |
| SYS-SAFE-002 | ARCH-SAFETY, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM, ARCH-CENTRAL-SESSION | IF-CENTRAL-VEHICLE-REQUEST, IF-DDS-ZONE-STATUS, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | Startup/recovery; F01–F04 clear; ZON-F01/F02 | TC-SAFE-002, TC-ZON-003 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-SAFE-003 | ARCH-ZONE, ARCH-VECU, ARCH-ZONE-FRONT, ARCH-ZONE-REAR | IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-FAULT-EVENT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | F02, F03, F04; ZON-F01/F02 | TC-COM-002, TC-COM-003, TC-COM-004, TC-SAFE-001, TC-ZON-002, TC-ZON-003 | M2/M4/M5/M9 | NOT RUN |
| SYS-SAFE-004 | ARCH-VECU, ARCH-ZONE | IF-CAN-DRIVE, IF-FAULT-EVENT | F03 양·음수 torque; F04; F02 Drive variant | TC-COM-003, TC-COM-004, TC-COM-002 | M2/M4/M6/M9 | NOT RUN |
| SYS-SAFE-005 | ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-ALLOC | IF-CAN-DRIVE, IF-CAN-BRAKE, IF-DDS-ZONE-STATUS, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS | RG-01 cap unknown/stale/0 및 부족분 | TC-REG-002, TC-REG-004 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-DIAG-001 | ARCH-DIAG, ARCH-ZONE, ARCH-VECU | IF-FAULT-EVENT | F01–F04 event integration; [진단 lifecycle/영속성·clear 프로토콜](diagnostics-protocol.md) | TC-DIAG-001 | M9; [계약 v0.1](../interfaces/diagnostics.md) | 전체 system/Target NOT RUN; [유한 M9 기능 검증](evidence/m9_followup/README.md) |
| SYS-PERF-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ORCH, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-HOST-ACTUATOR, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Timing/overload; S01–S03 | TC-PERF-001 | M3 partial; M5/M7/M12 E2E | NOT RUN |
| SYS-PERF-002 | ARCH-HOST, ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-BMS | IF-HOST-SENSOR, IF-CENTRAL-TRAJECTORY, IF-CENTRAL-VEHICLE-REQUEST, IF-CAN-STEERING, IF-CAN-BRAKE, IF-CAN-DRIVE, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Multirate; S01–S03, EV-F01 | TC-PERF-002, TC-EV-002 | M1 rate 결정; M2/M3/M6/M7 | NOT RUN |
| SYS-PERF-003 | ARCH-ORCH, ARCH-CENTRAL, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER | IF-HOST-SENSOR, IF-CENTRAL-VEHICLE-REQUEST, IF-HOST-ACTUATOR, IF-FAULT-EVENT, IF-DDS-FRONT-CMD, IF-DDS-REAR-CMD | Pause/reset/slow Target; F01–F04 | TC-PERF-001, TC-PERF-002 | M3/M5/M6/M7 | NOT RUN |
| SYS-EV-001 | ARCH-CENTRAL, ARCH-ZONE, ARCH-BMS, ARCH-VECU, ARCH-EV-PLANT, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM | IF-CENTRAL-POWER-REQUEST, IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-MODEL-BMS, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-MODEL-DRIVE-POWER, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | EV-S01, EV-F02 startup/shutdown; ZON-F01/F02 | TC-EV-001, TC-EV-004, TC-ZON-003 | M1/M2/M4/M6/M7 | NOT RUN |
| SYS-EV-002 | ARCH-BMS, ARCH-ZONE, ARCH-VECU, ARCH-ADAPTER, ARCH-CENTRAL-BRIDGE | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-DDS-ZONE-STATUS, IF-HOST-EV-STATUS, IF-DDS-FRONT-STATUS, IF-DDS-REAR-STATUS, IF-DDS-REAR-CMD | EV-S02, EV-F01 valid 0/unknown/cached source | TC-EV-002, TC-EV-003 | M1/M2/M3/M4/M5/M6/M7 | NOT RUN |
| SYS-EV-003 | ARCH-VECU, ARCH-ZONE, ARCH-BMS, ARCH-CENTRAL-VM, ARCH-CENTRAL-ALLOC | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-CAN-DRIVE, IF-CAN-BRAKE, IF-MODEL-DRIVE-POWER, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS | EV-S02; RG-01 cap change/invalid | TC-EV-003, TC-REG-001, TC-REG-002, TC-REG-004 | M2/M4/M6/M7 | NOT RUN |
| SYS-EV-004 | ARCH-BMS, ARCH-ZONE, ARCH-VECU, ARCH-EV-PLANT, ARCH-DIAG, ARCH-ZONE-FRONT, ARCH-ZONE-REAR, ARCH-CENTRAL-VM | IF-CAN-BMS, IF-CAN-DRIVE-CONSTRAINT, IF-MODEL-BMS, IF-FAULT-EVENT, IF-DDS-REAR-CMD, IF-DDS-REAR-STATUS, IF-DDS-REAR-SESSION, IF-MODEL-DRIVE-POWER, IF-DDS-FRONT-CMD, IF-DDS-FRONT-STATUS, IF-DDS-FRONT-SESSION | EV-F01/02 fault/clear/reinitialize; ZON-F01/F02 | TC-EV-002, TC-EV-004, TC-ZON-002, TC-ZON-003 | M1/M2/M3/M4/M6/M7/M9 | NOT RUN |
| SYS-EV-005 | ARCH-EV-PLANT, ARCH-BMS, ARCH-VECU, ARCH-ADAPTER | IF-MODEL-BMS, IF-CAN-DRIVE, IF-HOST-EV-STATUS | EV-S02 energy/full/empty/invalid | TC-EV-005, TC-REG-005 | M2/M6; M7 mapping review | NOT RUN |

정의: [requirements](../requirements/system-requirements.md),
[components](../architecture/README.md), [interfaces](../interfaces/README.md),
[scenarios](scenario-baseline.md), [cases/results](verification-strategy.md).

변경 절차: Requirement revision/rationale 기록 → component/interface 영향 확인 →
scenario/test oracle 갱신 → 해당 milestone에서 실행 → Result ID/artifact/verdict 연결.
같은 test의 component-only/plant/board별 run은 별도 결과로 보존한다. 미구현이나 TBD를
빈 결과나 0 ms로 대체하지 않는다. 모든 required variant와 환경 조건을 검증하기 전에는
일부 PASS만으로 requirement 전체를 VERIFIED로 변경하지 않는다.

C-M9-COMPLETE-01–04는 [M9 후속](evidence/m9_completion/README.md)의 최초 native 원인·동일 설정 정지 복구/clear·서비스 거절·CARLA30 실제 물리/DTC·component 고장 조합·저장 capacity를 연결한다. 당시 미완료 항목의 후속 검증은 최신 프로젝트 상태를 따른다.

C-M9-CLOCK-01/C-M9-POWER-01/C-M9-RETENTION-01/C-M9-SOAK-01은
[Clock·Power lifecycle·유한 운용](evidence/m9_remaining/README.md)의 명시적 Clock 재검증,
Power5조건의8-role 차량 복구, 비활성 store의 원형 보관/복원과 고정 native 서비스 반복을
연결한다. Source/expiry·보호 기한·과거 고장을 유지한다. Silent-loss의 실제 CARLA subinterval,
자동 장기 상태 이관/용량 회수와 학습자 수용까지 검증한 전체 TC 결과로 올리지 않는다.

C-M8-BRAKING-01/C-M9-STORAGE-01은 [소프트웨어 후속](evidence/milestone-followup/README.md)의
제동 방향별 적분·실제 allocator ancestry와 저장 syscall 오류/프로세스 중단·복원 실패 경계를
연결한다. 독립 모델/원본 획득 입력 재생과 실제 CARLA·Target 물리 시험을 구별한다.
새 CARLA 고정 S03 8000구간도 별도로 검증했으며 실제 전원 차단·무제한 보존·전체
Reference의 TC 판정은 변경하지 않는다.


## M10 Host 인지의 부분 추적성

`SYS-AI-001`의 learned trajectory/target/risk·유효 classical fallback 전체 TC-AI-001은 M11
NOT RUN을 유지한다. M10의 RGB 추론·2D history·원천 수신·고장·평가 경계는 선행 component
TC-PER-001–007이며 [프로토콜](perception-protocol.md)·[근거](evidence/m10_perception/README.md)와
component CSV의 C-M10-PER-01–04에 연결한다. Camera20Hz 수집과 실제 model20Hz 처리량은
다르다. 현재 CPU 지연/overwrite를 SYS-PERF-002의 전체 수용으로 올리지 않는다. Stage wall
측정은 SYS-PERF-001/003의 부분 근거이며 camera→validated trajectory나 Target 측정은 아니다.

TC-PER-008–010과 C-M10-PER-05–07은 [준비·live 경계](evidence/m10_live_perception/README.md),
TC-PER-011–013과 C-M10-PER-08–09는 [정확도 확장 프로토콜](perception-quality-protocol.md)과
[개발/보류 평가](evidence/m10_quality/README.md)에 연결한다. 고정 gate·원본 재구성·후보 회귀
검출의 기술 PASS와 실제 정확도 FAIL을 구분한다. 탑승자 annotation·visible/amodal box 차이는
남은 정답 정의 문제이며 전체 SYS-AI-001 수용으로 올리지 않는다.

TC-PER-014–015 및 C-M10-PER-10–11은 [V2 기준](perception-quality-v2-protocol.md)·
[새 수집/평가](evidence/m10_quality_v2/README.md)에 연결한다. Pedestrians12/Rider13 매핑 중복/누락과
실제 pose를 검사하고 strict IoU·최소 지원을 유지한다. Coverage 빈 조건·호환되지 않는
차량 asset·잘못된 차량 class를 확인한 결과는 FAIL로 남기며 전체 requirement 수용과 구분한다.

TC-PER-016–017 및 C-M10-PER-12–13은 [V3 기준](perception-quality-v3-protocol.md)·
[준비와 모델 비교](evidence/m10_quality_v3/README.md)에 연결한다. 별도 준비셋의 가시성·실제 부분
가림, 모델별 SHA·CPU/CUDA/OpenCV 수치 동등성과 새 평가 순서를 검사한다. 준비 통과와
모델 정확도·live20Hz·M11 주행 수용을 구분한다.

TC-PER-018–019 및 C-M10-PER-14–15는 [실제 site 도로 준비 기준](perception-road-preparation-v4-protocol.md)·
[V4 준비 근거](evidence/m10_road_preparation_v4/README.md)에 연결한다. 경로 전체의 junction과
실제 road/lane을 대조하고, 두 site의 계획 actor/rider·조건별 visible support를 검사한다.
준비 PASS·미래 계획 봉인은 새 정확도/주행 성능의 수용이 아니다. 작은 held 보행자 far26m의
제한과 이전 실패, 새로운 실제 평가가 필요함을 유지한다.

TC-PER-020–021 및 C-M10-PER-16–17은 [V4 새 정확도 기준](perception-quality-v4-protocol.md)·
[도로 맞춤 모델 비교](evidence/m10_quality_v4/README.md)에 연결한다. 불변 준비 봉인·원래1387개와 거절/진단324개를 합친1711개
RGB 제외·모델/품질 기준 freeze·보류 수집 이전 지명 재계산과 실제 actor/rider 지원을 검사한다.
SYS-AI-001/SYS-PERF-003의 부분 근거이며 감사 PASS가 모델 채택·실제wall20Hz·차량 수용은 아니다.

V4의 최종162개 actor/rider·조건 coverage는 PASS이나 지명 M의 absolute/relative 품질은 FAIL로
미채택이다. 원본 재감사·118개 Python/설정별13개 component 통과는 전체 정확도·wall 수용을 뜻하지 않는다.

TC-PER-022–024 및 C-M10-PER-18–20은 [V5 기준](perception-quality-v5-protocol.md)·
[후보/새 평가 근거](evidence/m10_quality_v5/README.md)에 연결한다. 약한 시야 지지·body 충돌
정책과 새31/35번 준비/평가를 검증했다. 개발 절대·상대 PASS와 보류 FAIL을 구분하며
SYS-AI-001/SYS-PERF-003의 부분 근거다. Learned trajectory·전체wall20Hz·차량 수용을 완료하지 않는다.

TC-PER-025–027 및 C-M10-PER-21–23은 [V6 기준](perception-quality-v6-protocol.md)·
[L 모델/새 평가 근거](evidence/m10_quality_v6/README.md)에 연결한다. L 모델 identity·수치
동등성·전체 class context 판단·새 도로/원본 재감사를 검증한다. 개발 지명의 상대 gate를
F1보다 우선하며 보류에는 S와 지명만 실행한다. SYS-AI-001/SYS-PERF-003의 부분 근거이며
전체 learned trajectory·실제wall20Hz·차량 수용을 완료하지 않는다.

TC-PER-028–030/C-M10-PER-24–26은 [전용 개발 데이터](evidence/m10_domain_data_v1/README.md)의
실제 raw/pose·작은 양성·COCO/PNG·train/validation 분리·원본 재현과 연결한다. 모델 없는
자료 단계의 SYS-AI-001 부분 근거이며 trainer·새 model accuracy·quality holdout·wall20Hz·
차량 수용은 완료하지 않는다. Bus/truck 자산 공유와 원래 coverage/시작 FAIL도 유지한다.

TC-PER-031–033/C-M10-PER-27–29은 [첫 L6 학습 후보](evidence/m10_training_v1/README.md)의
초기 tensor 이식·실제 학습·모든 validation score/선택·새 ONNX 출력과 수치/원본 재현을 연결한다.
개발 validation을 선택에 사용했으므로 독립 quality holdout·SYS-AI-001 전체 정확도·wall20Hz·
차량 수용을 완료한 것은 아니다. 초기 epoch 하락과 모든 양성을 유지하고 기본 S를 교체하지 않는다.

TC-PER-034–036/C-M10-PER-30–32은 [V7 새 L6 품질 평가](evidence/m10_quality_v7/README.md)의
모델/native identity·실제 road/pose/Rider·엄격 score/지명/순서·실패/복구·원본 재현을 연결한다.
감사 PASS와 model quality 판정·시작 안정성·wall20Hz·SYS-AI-001 전체/차량 수용을 구분한다.
개발 bus/precision 회귀와 새 보류 결과를 유지하며 후보를 수정한 뒤 기존 보류를 재사용하지 않는다.

TC-PER-047–049/C-M10-PER-43–45는 [V9 새 도로 평가](evidence/m10_quality_v9/README.md)의
지도만 사용한 미사용 경로 선정·모델 없는 준비·고정 native 모델/클래스 vector·full raw 재해석·
개발 지명 이후 보류 취득·실패/모든 시도 제외·압축 새 source 재현을 연결한다. SYS-AI-001/
SYS-PERF-003의 부분 근거이며 최종 모델 채택·전체wall20Hz·차량·각 Jetson 수용은 별도다.

TC-PER-050–053/C-M10-PER-46–49는 [해상도·car 후속 근거](evidence/m10_resolution_v2/README.md)에
연결한다. 원래 수치/640 cache 실패·1280 제외·검증된960 비교와 car 회귀 거절·별도 개발 설계
revision을 구분한다. 원본1458/파생486 raw·원래 gate·source/압축 재현의 부분 근거이며,
새 개발/보류·전체wall20Hz·차량·Thor/Orin 각각의 전체 stack 수용은 후속이다.

TC-PER-054–056/C-M10-PER-50–52는 [4K 원본 비교](evidence/m10_camera_resolution_v1/README.md)의
실제 native RGB/instance·독립 variable-size frame·동일 angular 지원·full300 수치/최대 source
사전 지명·원본/실패/압축 새 source 재현에 연결한다. 같은 소비 개발 배치이며 새 보류·전체
wall20Hz·기존 runtime 교체·Thor/Orin 전체 stack 수용을 완료하지 않는다.

TC-PER-057–059/C-M10-PER-53–55는 [4K 비동기 component](evidence/m10_async_native_v1/README.md)에
연결한다. Native BGRA→RGB/고정960 모델·native typed box·bounded latest1 owner와 독립
state/관측 consumer 진행·session/clock/expiry 경계·trace 재생의 부분 근거다. 즉시 예외 fixture의
overlap FAIL과 별도25ms 보완을 유지하며 실제 차량 제어/live camera·ROS/Target 연결·인지20Hz와
유효 출력 공급을 수용하지 않는다. 정상43개 call도100ms 초과·publication0임을 공개한다.

TC-PER-060–062/C-M10-PER-56–58은 [전처리 동등성·실제4K 비동기](evidence/m10_native_preprocess_v1/README.md)에 연결한다.
84장 입력 동등성·재생4조건의 실제111개 검출·실제 camera60개와 world/consumer 독립 진행을 검사한다.
실제37개 모두 late/fresh-output FAIL을 보존하며 source/raw 재감사 PASS로 뒤집지 않는다.
5689개 미래 제외·기본 S/runtime·100ms·M10 OPEN을 유지한다.

TC-PER-063–065/C-M10-PER-59–61은 [native CPU4K·완료 clock 검증](evidence/m10_native_kernel_v1/README.md)에 연결한다.
원래 Pillow 입력과 동등한 병렬 축소·bounded trace·실제27개 fresh 관측·초기4개 late를 구분한다.
533개 source와72개 raw를 재감사하고5761개 미래 제외를 유지한다. 기존 FAIL/100ms/S/runtime은
유지하며 전체20Hz·새 독립 품질·실제 controller·각 Jetson 수용을 대체하지 않는다.

TC-PER-066–068/C-M10-PER-62–64는 [native4K 준비·가용성 비교](evidence/m10_native_startup_v1/README.md)에
연결한다. 같은 추론 owner의 명시적 합성3회와 센서 분모를 모두 보존하고,10/13/20Hz에서
50Hz 관측의 유효 비율과 실제 CARLA 두 유한 반복의 원래 source/receipt age를 재생한다.
SYS-PERF-002의 Reference20Hz를 낮추거나 유효기간100ms를 늘리지 않는다. 준비 READY·일부
fresh 관측·원본 보존을 전체wall20Hz·장기 운용·실제 controller·각 Jetson 수용으로 올리지 않는다.

TC-PER-069/C-M10-PER-65는 같은 근거의 [유한 메모리 기록 기준](perception-native-memory-v1-protocol.md)에
연결한다. 원래180s 시작 실패와8-slot 저장 overflow232장 FAIL을 보존한다. 새 Host 진단 조건은
240장의 immutable reference를 보관해 측정 중 정상 disk write를 없애며 종료 후 해제/압축한다.
최대8.49GB는 유한 원본 수집기의 상한이고 production inference의 latest1 계약이나 Jetson
메모리 요구로 옮기지 않는다.554개 source에 원래547개를 그대로 포함한다.


TC-PER-070–072/C-M10-PER-66–68은 [비동기 월드 관측 기준](perception-world-async-v1-protocol.md)과
[유한 실측·전체 원본](evidence/m10_world_async_v1/README.md)에 연결한다. 실제 clock/gap/duplicate와
100ms 상태 침묵·복귀에서 과거 결과의 부활을 차단한다. 동기1회/비동기2회의 전체 관측 가용성·
원래 source/receipt 기한·클라이언트 tick0회·사후 raw payload 및 exact 입력 재생을 검사한다.
SYS-PERF-002 Reference20Hz는 그대로이며 실측 wall 수용이나 actuator 연결을 대신하지 않는다.


TC-PER-073–075/C-M10-PER-69–71은 [GPU readback 사전 기준](perception-readback-v1-protocol.md),
[재할당 후속 기준](perception-readback-pool-v1-protocol.md), [전체 실행 근거](evidence/m10_readback_pool_v1/README.md)에 연결한다.
원래 acquisition/receipt100ms·4K/Epic를 유지하며 CPU stage clock과 SDK frame/time을 대조한다.
성공4회/실패2회·원본600장·future exclusion7613·source565→574→580을 보존한다.
모든 wall 통계/실패 판정/원본 BGRA·RGB/정확한 입력을 재감사하고 변조96건을 거절한다.
카메라15.63Hz 조건도 유효 조회16.10%이므로 기본값·wall20Hz·전체 인식 경로 수용으로 올리지 않는다.

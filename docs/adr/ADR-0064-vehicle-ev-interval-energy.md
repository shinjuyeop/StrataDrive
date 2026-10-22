# ADR-0064: 차량 운동과 EV의 구간 에너지 결합

Date: 2026-10-22. Status: **구현·component 및 일부 Host 기능 검증 / 전체 M6 수용 보류**.

M6 후속으로 actual 기반 차량 운동, 회생/마찰 배분과 실제 EV 전원·배터리 에너지 수지를
연결한다. 기존 SimpleVehicle 거리 적분과 electrical beginning-speed ZOH는0.2s 재현에서
1.792405J 차이가 났다. 새 물리 결합은 같은 구간 motor work를 명시적 interval port로
전달한다. scalar source를 바꾸거나 end speed를 과거 acquisition으로 쓰지 않는다.

`VehicleEvModel`이 candidate vehicle/electrical/Battery를 함께 commit하고, 독립 ledger는
kinetic/friction/road/motor/circuit/auxiliary/ohmic/capacitor/chemical 항을 비교한다.
기존 모델·일반 receiver defaults를 전면 교체하지 않는다. 기존 physical process만 이 결합을
소유하며 session/ACK/permission/control 경계에는 물리 bus 우회를 추가하지 않는다.

실제 주행에서 확인한 EV capability 소실은 Central/Rear receiver의 generic30ms dependency
설정이었다. 이미 정의·지원된 EV70ms를 명시한다. 실제 source30ms,80ms RX timeout,
원래 command expiry·20ms envelope·allocator20ms support 및 host10-v1은 그대로다.
처음 의심한 optional20ms support 가설은 실제 Unavailable 분기로 기각했고 수정하지 않았다.

정상8s quiet FIFO energy cycle와 charge-zero는 실제3-process/8참여자 session으로 통과했다.
Normal owner pause/Rear rejoin도 통과했으나 **command-loss의 기존 physical100ms 기준은 FAIL**이다.
주입 후 local zero-target 선택은 약18ms였고, 관측 torque와 기존2000Nm/s ramp로는 남은
시간 안에 actual zero를 만들 수 없다. SYS-SAFE-004의 zero-target 선택과 실제 물리 응답을
구분한다. 기존100ms raw 판정·모델 rate를 바꿔 통과시키지 않으며 새 profile의 전체 수용을 보류한다.
실제 response budget(TBD-03)/해당 gate 적용 범위의 다음 검토가 필요하다.

ASan 재가입과 TSan 실행에도 wall/transport 실패·SDK queue drop이 남았다. 실제
memory/UB/race 진단0이 기능 실행 완료를 뜻하지 않는다. 원본 분모를 유지하며 SDK 오류를
일괄 면제하지 않는다. 이 실패 때문에 기존에 수용한 M5 범위를 다시 무효화하지 않는다.

상세 [모델 경계](../icd/vehicle_energy.md), [protocol/근거와 미완료](../test-plan/evidence/m6_vehicle_energy/README.md)를 따른다.
M6 전체 종료/M7 CARLA/M8 C++ controller·동등성/Jetson·전체 시스템으로 확대하지 않는다.

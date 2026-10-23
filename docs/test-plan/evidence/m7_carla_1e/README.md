# M7-1e — wheel 원천·clock·수집 비용과 종료 실패 진단

2026-10-23, HEAD7a2b0fa + 기존 미커밋 M7 작업. 사용자가 후속 확인과 대안 검토를 요청했다.
**판정: CARLA 패키지 유지·추가 제한 검증에 근거가 있다. 실제 M6 wall runtime 정상 주행은 여전히 BLOCKED.**
샘플링10ms/영상50ms·freshness30ms 및 M6 계약/결과는 변경하지 않았다.
정상 제어 연결, 비영 actuation, source build, AI 학습, Jetson 실행은 수행하지 않았다.

## 1. 새로 확인한 wheel 원천

공식0.9.16 tag의 소스를 읽기 전용으로 조회했다. [URL/SHA manifest](sources/manifest.json),
원문은 sources/ 아래 MIT notice와 함께 보관했다. tag 소스가 패키지 바이너리와 완전히
동일하다는 독립 rebuild 검증은 아니다. 설치된 API와 실제 호출 결과를 함께 대조했다.

- [Vehicle.cpp](https://github.com/carla-simulator/carla/blob/0.9.16/LibCarla/source/carla/client/Vehicle.cpp#L102)의
  `GetWheelPitchAngle`은 episode 경유 RPC다.
- [서버 RPC](https://github.com/carla-simulator/carla/blob/0.9.16/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Server/CarlaServer.cpp#L2013)는
  `BIND_SYNC`, 반환형 float이며 원천 frame/time을 포함하지 않는다. WorldSnapshot의 wheel-speed 필드가 아니다.
- [물리 분기](https://github.com/carla-simulator/carla/blob/0.9.16/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/CarlaWheeledVehicle.cpp#L984)는
  physics on이면 wheel `GetRotationAngle()`, off이면 animation pitch를 읽는다.
  따라서 1b/1d의 physics-off 정적 값만으로 wheel 원천을 판정할 수 없었다.

[실제 probe](run-01/matrix_TERM/attempt/wheel-clock.json)는 physics on·autopilot off·제어 입력 없이
120tick에서4wheel RPC를 호출했다. 같은 snapshot frame을 RPC 전후 확인했고 유한 값480개를 얻었다.
4RPC 합계 Mean0.591/P99 1.003/Max2.912ms. 회전각 최대 약1.16e-6deg로 사실상 무회전이다.
scope 문자열의 stationary는 의도한 정지 fixture를 뜻한다. 실제 spawn 후 **중력 settling**이
발생했으며 최대 수직 속도3.09145m/s, 수평 속도3.86e-7m/s다. 이동 주행/유효 회전 자극 시험으로 세지 않는다.
기본 physics readback의 radius/steer/brake torque도 보관했으며 새 calibration 값으로 채택하지 않았다.

**결론:** 물리 wheel 회전각을 읽을 후보는 존재한다. 직접 각속도·누적 회전·slip/energy 지원은
입증되지 않았다. 두 회전각 차분은 구간 평균 angular speed의 후보이며 wrap/aliasing/부호/단위와
두 원천 시각·oldest dependency를 검증해야 한다. instantaneous measured speed로 바로 승격하지 않는다.
서로 다른4RPC도 외부 tick 차단·physics 완료와 frame 일관성 입증이 필요하다.
현재 Drive의 rad/s sensor 계약 적합 여부와 물리량 calibration은 OPEN이다.

## 2. 비용 분리 시험

[환경](environment.json), [수집기](../../../../tests/integration/carla/m7_1e_diagnose.py),
[서버 runner](../../../../tests/integration/carla/run_m7_1e.py),
[독립 재계산기](../../../../tests/integration/carla/analyze_m7_1e.py).
설치는 기존 공식0.9.16/bundled Python3.10 venv, RTX3090/driver580.178.04를 사용했다.
Town10HD_Opt/mkz_2020, ClearNoon, traffic0, offscreen Vulkan Low. 비용 비교 ego는 physics off다.
world10ms, 카메라가 있는 case만 RGB/GT800×600/FOV90/sensor_tick50ms,
rigid actor-relative(1.5,0,1.7)m. GT는 이 진단에서도 제어 입력으로 사용하지 않는다.

profile을 실행 전에 summary에 고정했다. 네 조건을 정순/역순 각1회, 총8case로 비교했다.
각600tick=startup100/main400/drain100. 아래는 **main400tick(4sim s) 각각의 유한 관측**이다.
첫 camera 위상 변동은 startup 원본에 보존하고 마지막50startup tick에서 위상을 고정했다.
모든 camera main RGB/GT 각각80/80, 모든 state400/400, overflow0. pause는 matrix 밖 별도 probe다.
hash/histogram 조건만 main thread에서 raw 복사·SHA256·GT Counter를 수행한다.
metadata 조건도 sensor callback/영상 수신·큐 비용은 포함한다. 실시간 pacing sleep은 넣지 않았다.

| 조건 | RTF 정순 / 역순 | snapshot 완료 간격 P99 정순 / 역순 ms | Max 정순 / 역순 ms | >30ms 정순 / 역순 |
| --- | --- | --- | --- | --- |
| rendering off, state만 | 21.272 / 23.673 | 0.949 / 0.747 | 3.161 / 2.614 | 0/400 / 0/400 |
| rendering on, state만 | 1.422 / 1.424 | 11.173 / 8.996 | 12.835 / 9.186 | 0/400 / 0/400 |
| RGB/GT 수신·metadata만 | 1.033 / 1.014 | 24.493 / 24.662 | 26.002 / 26.654 | 0/400 / 0/400 |
| RGB/GT + hash/histogram | 0.930 / 0.919 | 25.348 / 25.083 | 29.750 / 26.743 | 0/400 / 0/400 |

전체 원본/분포: [analysis](run-01/analysis.json), [manifest](run-01/matrix_TERM/attempt/summary.json).
percentile은 nearest-rank, RTF는 main4sim s/(첫 main tick 시작→마지막 main consume 완료).
gap 분모400에는 마지막 startup snapshot→첫 main snapshot 간격1개가 포함된다.
Mean consume 비용은 metadata0.021~0.023ms, audit3.580~3.677ms/tick이었다.
정순/역순 반복은 순서 효과를 줄이는 작은 대조이며 randomized 실험·장기/부하 보장은 아니다.

**해석:** rendering/카메라가 큰 비용이고, main thread의 audit 작업도 관측 속도를 낮춘다.
패키지 자체가 Host에서 절대100Hz에 도달할 수 없다는 판단은 근거가 없다. 반대로 metadata만
RTF1을 조금 넘었다는 사실도10ms deadline/Drive30ms 수용이 아니다. 카메라 동반 간격은
최대26.654ms로 실제 ECU·네트워크·clock uncertainty를 더할 여유가 작다. wheel4RPC 비용은
별도 no-render probe에서 측정했으므로 위 비용에 단순 합산해 실제 연동 결과로 쓰지 않는다.
이 비교는 M7-1d의30ms 초과 관측·FAIL을 소급 면제하지 않는다. no-rendering은 영상 생성
경로의 대체가 될 수 없으며 state-only 비용 대조군이다.

## 3. Clock 원천과 실패한 단순 mapping 가정

[WorldObserver.cpp](https://github.com/carla-simulator/carla/blob/0.9.16/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Sensor/WorldObserver.cpp#L296)는
snapshot header를 만들 때 `FPlatformTime::Seconds()`를 `platform_timestamp`에 넣는다.
그 뒤 actor state를 직렬화한다. 이는 개별 wheel 물리 취득 시각이라는 근거가 아니다.
이번에는 sim elapsed, platform timestamp, Host monotonic tick 시작/반환을 모두 기록했다.

각 tick에서 platform 이벤트가 request begin~snapshot end 안에 있다고 가정하고
Host monotonic−platform offset의 가능한 구간을 계산했다. case별main에서는 구간 교집합이
존재했지만, **전체8case를 관통하는 고정 offset은 교집합이 없었다**:
lower2,417,379,612ns > upper2,417,195,606ns,184,006ns 불일치.
즉 zero-offset뿐 아니라 한 번 보정한 상수 offset도 이 관측 전체에 맞지 않는다.
이 bracket 결과는 시계 원인 확정/원천 freshness 증명이 아니며 RPC/serialization provenance
가정의 한계도 포함한다. [Host-only clock 조회](host-clock-readings.json)의 MONOTONIC−RAW
차이는 약2.418s로 관측 차이와 비슷하다. 패키지 UE의 정확한 platform clock 구현을 입증하지
않았으므로 **RAW clock 후보 추론**으로만 남긴다. RAW와 MONOTONIC을 그대로 혼용하지 않는다.

pause250.298ms 동안 frame/sim/platform snapshot 값이 모두 고정됐다. 이는 마지막 snapshot이
재사용된 결과이며 OS clock이 멈췄다는 뜻이 아니다. arrival로 acquisition을 덮어쓰지 않았다.
후속 wall 연결은 물리 취득 이벤트·clock domain·offset/drift/uncertainty·reset 재동기화와
consumer 시점의 age를 함께 검증해야 한다. 실제 owner-wire/ECU wall freshness는 **NOT RUN**이다.

## 4. 서버 종료 실패 범위

매번 새 전용 서버를 실행하고 정상 world 연결·client retire 후 종료했다.
초기 readiness 실패는 각 process.json에1건씩, 총3건 보존했다. 외부 actor/client가 없는 환경이다.

| 조건 | 종료 / 로그 | 의미 |
| --- | --- | --- |
| [empty_TERM](run-01/empty_TERM/process.json) | SIGTERM→exit139/Signal11 | ego/sensor/reset 없이도 재현 |
| [empty_INT](run-01/empty_INT/process.json) | SIGINT→exit139/Signal11 | 종료 신호 변경으로 해결되지 않음 |
| [matrix_TERM](run-01/matrix_TERM/process.json) | actor0·설정 복원·client 종료 뒤 SIGTERM→exit139/Signal11 | 진단 후에도 재현 |

**OPEN-M7-1D-01 유지.** 모든 로그는 server.log에 있다. 새3프로세스 모두 같은 종료 증상을
보였지만 root cause가 동일하다는 symbolized stack 근거는 없다. M7-1b native client reload
crash와도 합치지 않는다. 무센서 재현으로 센서 cleanup이 필수 원인이라는 가정은 배제할 수 있다.
core 크기 제한0을 child에만 설정했고 로그/exit는 보존했다. 강제SIGKILL은 사용하지 않았다.
현재 시험 서버와2000/2001/2002 listener는 없다. 서버 종료 안정성 PASS는 기록하지 않는다.

## 5. 대안과 다음 작은 작업

현재 결과만으로 simulator 교체나 GPU 교체를 결정할 필요는 없다. 다음 경로를 구분한다.

| 경로 | 가능성 / 필요한 작업 / 포기하거나 바뀌는 범위 |
| --- | --- |
| 현 CARLA + 별도 functional simulation clock | **우선 설계 후보**. 전체 ECU/통신/lease/expiry를 명시적 동일 논리 clock·barrier에 묶어 느린 Host에서도 기능 검증.30ms 값·Actual-only 경로 유지. 기존 wall runtime에 sim timestamp를 주입하는 방식은 금지. 별도 opt-in entrypoint·계약 검토가 필요하며 wall100ms/2ms/4ms 증거가 되지 않음 |
| 현 CARLA + 실제 wall runtime | audit/저장/GT 처리를 bounded 별도 process로 옮기는 후보; queue overload·원래 metadata 보존. clock provenance와 wheel source, 장기/부하·native guard/Actual apply 지연까지 검증 필요. 이번 metadata 수집 성공만으로 연결 승인 불가 |
| 기존 SIL plant + CARLA 영상/환경만 | wall 제어 유지가 우선이면 후속 대안. 기존 physical owner가 운동/에너지를 단독 소유하고 CARLA ego physics off·pose 투영. CARLA 타이어/충돌 dynamics 검증 범위를 포기하며 현재 CARLA-motion 소유권을 개정해야 함. **미채택/미구현** |
| CARLA 서버 확장 또는 다른 simulator | timestamp 포함 coherent wheel/actuation telemetry·energy 인터페이스가 패키지로 불가할 때 검토. source build/교체 비용과 mapping 재검증 필요, 이번에는 미착수 |

권장 다음 단위는 **M7-1f functional clock 설계와 wheel 센서 의미 검증 계획**이다.
먼저 simulation/monotonic 경계를 문서로 고정하고 pure ECU API의 `now_ns` 주입 가능 범위와
실제8-role session/lease/ACK barrier를 검토한다. 이후 제한된 물리 wheel 회전 자극 시험의
별도 calibration 경계를 설계한다. 지금은 control API로 직접 토크를 넣는 우회 시험을 하지 않았다.
기존 M6 wall profile/실측·요구를 바꾸거나 실제8-role 경로를 생략하지 않는다.

## 재현과 검증

서버 포트가 비어 있을 때 저장소 root에서 실행한다. output은 새 경로여야 한다.

```sh
/d/shin/stratadrive-tools/carla-0.9.16/venv-bundled/bin/python -I tests/integration/carla/run_m7_1e.py --server /d/shin/stratadrive-tools/carla-0.9.16/server --output /d/shin/stratadrive-tools/carla-0.9.16/m7-1e/new-run
python3 tests/integration/carla/analyze_m7_1e.py /d/shin/stratadrive-tools/carla-0.9.16/m7-1e/new-run
```

runner exit0는 진단 절차가 관측을 완료했다는 뜻이며 server139를 PASS로 바꾸지 않는다.
원본 JSONL은 저장소 밖 보존, 저장소 보관본은 gzip만 적용했다. 임시 복사본에 압축을 풀면
동일 oracle로 재계산 가능하다. [harness SHA](sources-harness.json), [검증 기록](validation.json),
[전체 hash](SHA256SUMS). M6 C++/SDK 전체 회귀는 새로 실행하지 않았다.

# 기록 이관·가용력 목표·M10 Host 착수 검증

실행일2026-11-06, baseline `3de8efb48b70a8a77e7468ab6e493fb19b4c0bb8`.
판정은 **선택형 Host component·CLI 검증 완료**다. M3/M4 원인 규명, 기존 SOME/IP/CARLA
운영 경로의 장기 기록 전환, 인지/학습 모델 또는 전체 milestone 종료 판정이 아니다.

## 구현과 확인

- M9 EpochRecorder: 실제 새 Session/Attempt에서 활성 창을 회수하고 DTC key/count/generation,
  최초·최종 identity와 원본 predecessor를 보존한다. 과거 pass 권한은 옮기지 않는다.
  원본 이력에 대한 event/clear 재전송은 durable Duplicate이며 변조는 Conflict다.
- M8 AvailableForceReference: 구동·제동 힘과 저항의 모든 허용 값에서 가능한 가속 구간으로
  20ms 목표를 제한한다. 실제 속도와의 추종 차이도 제한하고 source/expiry를 보존한다.
- M10 Host 상태 기반 `[4,6]` 입력과 속도 `[16]`·risk·valid 출력, trusted binding,
  Supervisor의 검증/fallback/보호 요구를 기존 PI와 ControlAllocation까지 연결했다.
- 기존 배분 시험의 입력 helper를 allocation_fixture.hpp로 합쳐 신규 통합 시험에서도 같은
  실제 readiness/permission 계약을 사용한다. 기존 모델·wire·수용 기준은 변경하지 않았다.

## 검증 결과

| 검사 | 결과·범위 |
| --- | --- |
| Debug 회귀 | 기존 및 신규1507개 통과: unit1155·logical347·transport5 |
| 추가 반복 고장 | Debug1개 통과. 총 고유 Debug 검사1508개 |
| ASan/UBSan | 관련 unit217개 + 추가 반복 고장1개, 총218개 통과 |
| 정적 검사 | clang-tidy 변경7개 translation unit 경고/오류0; 마지막 추가 시험 파일 재검사 포함 |
| 이관 저장 경계 | fsync16·rename3 경계 각각 EIO와 직후 프로세스 종료, 총38개 주입 통과 |
| 반복 이관 | 활성 창16의100세션/1500event, 재개방·초기 receipt 재전송 통과 |
| 반복 고장 상태 | occurrence 창8보다 많은40세션의160entry; DTC count40·generation1 보존, 활성 event≤5 |
| 합성 제어 | 20ms×5000의100초 가용력 참조 및 별도 PI/point-mass 시험; 후자는 출력 속도1m/s±0.02 수렴 |
| 기존 배분 연결 | 20..200ms의10회 실제 배분 tick. Classical→Learned proposal fixture→Classical 전환, 실제 selection의 PI 피드백과 원래 child dependency 검증 |
| CLI | 기존 native input-loss canonical event15개 입력·재개방·동일15개 durable Duplicate, 잘못된 hex와 기존 경로 bootstrap 거절 |

합성 plant는 질량1000kg·외력 저항150N과 clip된 구동/제동 힘을 사용하는 독립 point-mass다.
CARLA/실차 성능 향상 주장으로 쓰지 않는다. Learned 분기의 입력은 계약 fixture이며 학습된 모델을
실행하지 않았다. 저장 중단 시험도 실제 전원 차단/디스크 캐시 소실을 대신하지 않는다.

개발 중 첫 빌드는 누락 include와 indentation 경고를 수정했다. 첫 연결 시험은 allocator를
시작한 뒤100ms 동안 tick 없이 접수해 기존30ms 감시기에 걸렸다. 이를 기준 완화로 고치지 않고
같은 INIT에서20ms마다 실제 allocation tick을 실행하고 history warm-up 동안 classical 입력을
사용하도록 수정했다. 최초 실패 로그는 최종 통과와 함께 보존했다.

## M3/M4 조사와 남은 작업

현재 kernel6.8.0-138-generic에서 FIFO1은 가능하다. tracefs 접근은 Permission denied,
perf_event_paranoid=4이며 perf probe는255로 종료했다. `sudo -n -l`도 암호가 필요해 실패했다.
새 wall workload나 privileged capture는 실행하지 않았다. 과거 timer→wakeup→switch/IRQ
관측을 사후 생성할 수 없으므로 기존 실패의 근본 원인을 CLOSED로 바꾸지 않는다.

남은 경계는 아래 계약에서 관리한다.

- [세션 이관 계약](../../../interfaces/epoch-retention.md): 단일 epoch 중 회전, 통신 stream/ACK 운영
  연결, family 외부 보관/디스크 삭제 정책·더 큰 보관량의 조회 성능과 실제 매체 시험.
- [속도 제안 계약](../../../interfaces/supervised-speed-proposal.md): 실제 가용력/저항 추정 adapter,
  인지/학습 모델, coordinator 보호 연결의 전체 CARLA/Target 검증과 Reference ODD.
- M7 전체 wall 실시간 연동은 사용자 선택에 따라 후순위다. 기존 renderer/GC 원인까지 해결된
  것으로 올리지 않는다. M12/M13과 학습자 최종 수용도 후속이다.

## 원본과 재현

[acceptance.json](acceptance.json), [sources.json](sources.json), [SHA256SUMS](SHA256SUMS)를
기준으로 [sources.tar.gz](sources.tar.gz)의 변경 소스/문서와 [validation.tar.gz](validation.tar.gz)의
개발 실패·최종 검사 로그, raw CLI family·canonical 입력/receipt, syscall XML·timing capability를
대조한다. 기존 native canonical 입력의 경로/원본 hash와 실행 binary hash도 포함한다.

```sh
cmake -S . -B build/m1-angle
cmake --build build/m1-angle -j4
ctest --test-dir build/m1-angle -L '^(unit|integration.logical|integration.transport)$' -j4 --output-on-failure
cmake -S . -B build/epoch-asan -DSTRATADRIVE_SANITIZERS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build/epoch-asan --target epoch_recorder_test speed_supervisor_test -j4
ctest --test-dir build/epoch-asan -R '^(EpochRecorderTest|EpochCheckpoint|AvailableForceReference|SpeedSupervisor|SupervisedSpeedRequest)' --output-on-failure
```

Fresh build의 option/profile에 따라 전체 등록 시험 수는 달라질 수 있다. 보관된 CMake cache와
compile command subset은 이번 실제 빌드의 기준이다. 과거 원본 evidence는 수정하지 않았다.

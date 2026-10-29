# M8 전 코드 정리와 회귀 검증

2026-10-29, 기준 commit `b8b5f6a`. 사용자 요청에 따라 공통 구현·빌드·감사 도구를 정리했다.
**코드 회귀 검사는 통과했다. 실제 CARLA는4개 중3개 전체 통과, 정상 wall 주행1개는
900구간 검사 통과 후 UE 종료−11로 실패했다.** M6/M7의 기존 수치·수용 범위·과거 원본을
변경하지 않으며 M8 기능 구현은 하지 않았다. 현재 상태는 [프로젝트 상태](../../../project-status.md)를 따른다.

## 변경과 유지한 경계

- 문자열 치환으로 생성하던 `WallDriveController`/`WallLeafOwner`와 생성 CMake2개를 제거했다.
  공통 `DriveControllerConfig`/`LeafOwnerConfig`에서 HV dependency 예산과 Drive 센서 관측 순서를
  명시한다. 미설정은 기존 local age/ControlTick을 따르고 wall rig만 BeforeIo와30/50ms를 선택한다.
  Controller/Zone/vECU 주기, source 시각·명령·권한·expiry·보호 latch는 그대로다.
- 루트 CMake574줄을81줄로 줄이고 core library, Linux runtime, core test 구성을3개 파일로
  나눴다. 반복 test 선언41개를 공통 함수로 묶었다. 기존1168개 test의 이름·property가 모두
  같고 컴파일 명령149개는 동일하다.6개는 생성 header include만 제거했고 생성 CPP2개가 사라졌다.
- CARLA 감사4개의 plain/gzip reader를 공유한다. Wall 감사는 원본320 substep을 모두 검사한 후
  큰 payload를 메모리에서 버리고, 마지막 정지 구간은 큰 dictionary 목록 탐색 없이 검사한다.
  원본 파일은 수정하지 않는다. Source snapshot에 reader도 포함한다.
- 삭제된 추적 파일 때문에 source fingerprint가 실패하던 문제를 고쳤다. 삭제 전후·staging 전후,
  미추적 CMake 변경을 검증하고 timing/RTOS manifest에도 CMake 모듈을 포함했다.

공유 M6 **구현 파일**도 이번 사용자 요청 범위에서 변경했다. M6의 기본 동작·통신/안전 계약을
바꾸거나 원본 구현이 byte 단위로 동일하다고 주장하지 않는다. Central/Zone/CAN 역할 분리,
물리·에너지 모델, UE/CARLA 엔진 코드와 과거 실행 script는 유지했다. 서로 다른 책임을 단순히
비슷해 보인다는 이유로 합치지 않았다.

## 실행 결과

| 검사 | 실제 결과와 범위 |
| --- | --- |
| Normal / ASan·UBSan | 각각1170/1170. 기본·논리1161개 후 timing 민감9개를 별도 직렬 실행 |
| TSan | 지정 경계36/36: wall watch3, owner/mailbox/terminal/clock/HV25, admission/shared channel8 |
| Python | 최종201/201. 최초199개 중26개 실패/오류는 unstaged 삭제 파일 fingerprint 예외였고 수정·회귀 추가 후 재실행 |
| BUILD_TESTING=OFF | 별도 깨끗한 Release build에서 core library/demo 빌드 통과 |
| clang-tidy | 변경 DriveController·AsyncLeafOwner·functional rig3개 TU, 현재 compile database로 진단0 |
| Native replay | 과거 정상901개·보호401개 입력에 새 binary 출력이 정확히 동일. CARLA 재실행과 구분 |
| 감사 동등성 | 기존 성공·실패 raw 입력으로 이전/이후19개 결과 정확히 일치 |
| 감사 손상 거부 | 마지막 substep 누락/변경·마지막 record 절단3/3 거부. reader의 blank/truncated/plain 우선순위 시험도 포함 |

최초 TSan functional binary에 wall-watch filter를 잘못 지정해0개가 실행된 로그도 남긴다.
이를 통과 분모에 세지 않고 실제 wall-watch가 있는 wheel binary에서3개를 실행했다.
`validation/quiet-tests.json`, `post-run-validation.json`의 명령·종료 코드와 각 로그를 따른다.
전체 SDK/TSan/Target 수용은 아니다.

동일한 보관 run01의900개 raw receipt를 별도 process에서 순차 감사했을 때 최대 RSS는
**616308→59020KiB, 약90.4% 감소**했다. 결과 JSON은 같고 elapsed는7.37→6.72s였다.
단일 감사 실행 관측이며 CARLA physics/실시간 성능 향상으로 해석하지 않는다.
`validation/audit-performance.json`이 기준이다. 최초 build와 겹쳤던 예비 측정은
`audit-before-performance.json`에 남겼으며 최종 시간 비교에는 사용하지 않았다.

## 실제 CARLA 회귀

| 실행 | Physics/EV | 관측 | 전체 실행 |
| --- | --- | --- | --- |
| wall normal,5ms/HV50 | 900/900 | 정상734, miss/late/expiry0; model4.5s / wall4.502438s | **FAIL: 주행 감사 PASS, 종료−11** |
| wall100ms gap,5ms/HV50 | 900/900 | 정상50→보호684,1MPa213.180ms·자연 정지379.006ms, 마지막100구간 pose 동일 | PASS, 종료130 |
| functional camera,10ms | 900/900 | 정상819, RGB/GT 각180, 원본 시각 일치·누락0 | PASS, 종료130 |
| functional protected sleep,10ms | 400/400 | index278부터 자연 sleep122구간, 마지막100구간 exact stationary | PASS, 종료130 |

종료130은 runner가 전용 서버에 SIGINT를 보내 끝낸 결과다. normal의−11은 UE 종료 중
`UEdGraphNode::AddReferencedObjects`/GC task stack에서 관측했다. 이번4개 실행의
PhysXVehicles/Carla/M7Native library hash는 이전 HV 예산 시험과 같다. 기존에도 종료−11이
있었지만 동일 원인이라고 확정하지 않으며, 엔진 종료 문제는 OPEN이다. 통과할 때까지 재실행해
실패를 숨기지 않았다. `carla/server-normal.json`과 `carla/runtime-normal/server.log.gz`를 따른다.

기능 camera는 simulation-time 실행이며 wall 실시간 수용이 아니다. 비영상 시험도 짧은 고정
Town03/V1 범위다. M7 기능 CLOSED/실제 wall 전체 OPEN을 유지하고 M8의 모델/C++ 동등성 및
속도 폐루프 작업으로 넘어갈 수 있다. 엔진 종료 안정성·영상/장시간 wall gate는 별도 후속이다.

## 원본과 재현

- `build-manifest.json`: 기준 commit, 실제 source/binary hash, 빌드 옵션, 서버별 artifact와 종료 코드.
- `sources/`: 변경 코드 snapshot. `validation/`: build/test/정적 분석·동등성·성능·replay 결과와 재현 script.
- `carla/`: 이번4개 실행의 result·raw trace·CAN/owner CSV·sensor·server/client log와 실행 argv.
- `archive-map.json`: 실행 당시 원본 경로, archive 상대 경로, 압축 여부, 압축 전 SHA256.
  큰 파일은 무손실 gzip이다. `SHA256SUMS`는 README와 manifest를 포함한 보관 파일의 SHA다.

기본 재실행은 저장소 루트에서 아래 순서로 한다. 시간 민감 시험 중 build/다른 시험을 병행하지 않는다.

```sh
cmake -S . -B build/m7-functional -DSTRATADRIVE_M7_CONTRACT_TESTS=ON -DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON
cmake --build build/m7-functional --parallel 2
ctest --test-dir build/m7-functional -LE runtime.wall --output-on-failure
ctest --test-dir build/m7-functional -L runtime.wall --output-on-failure
python3 -m unittest discover -s tests/unit -p '*_test.py'
```

ASan은 별도 build와 `-DSTRATADRIVE_SANITIZERS=ON`, TSan은 manifest의 별도 Debug build와
기록한 `setarch x86_64 -R`/filter를 사용한다. 실제 CARLA 실행은 `validation/run_carla.py`의
기존 engine/source/venv/fixture와 **새 output/runtime 경로**를 사용한다. 과거 디렉터리를
덮어쓰지 않는다. 재현 script의 `build/pre-m8-refactor` 경로에는 필요한 보관 validation 파일을
복원한다. 보관 raw를 압축 해제해 다시 감사할 때는 임시 복사본을 사용한다.

```sh
cd docs/test-plan/evidence/pre-m8-refactor
sha256sum -c SHA256SUMS
```

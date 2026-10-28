# M7 종료 교착 수정과 보호 Actual 연속 적용

2026-10-28. **기능 경로 수정·검증 완료, 전체 M7 NOT CLOSED.** M6 구현·계약·수용은 유지한다.
기존 [통합 근거](../m7_carla_integrated/README.md)와 이번 실패 원본을 덮어쓰지 않는다.

## 수정과 관측

1. 로딩 중 `get_world`의 sync RPC는 game-thread callback을 기다리고, 종료 game thread는
   RPC worker join을 기다렸다. `diagnostic-a`에서15s 이후 소유 프로세스의 최소 GDB stack을
   얻었다. main의 `rpc::detail::thread_group::join_all` 주소와 EpisodeInfo packaged-task 관련
   worker 주소를 관측했다. 전체 debug symbol을 생략한 stack의 일부 unwind는 불완전하다.
   실제 pinned RPC header의 독립 재현에서 queued/network Stop TIMEOUT을 확인했다.
   `_stopping`을 join 전에 알리고 sync wait/queued callback을 취소하도록 수정했다.
   queued game/physics mutation을 실행해서 종료를 풀지 않는다. 이전 M7-1s accept/close 수정은 유지한다.
2. 기존 M7 harness는 보호 선택 뒤 정상 credit 검사를 통과할 수 없어 끝났다.
   trusted `PROTECT`는 기존 native actor의 안전 선택만 요청하고, 이후 원래 owner/feedback service를
   계속한다. 명령·pressure 값을 주입하지 않는다. 서버는 고정 Release/epoch·보호 선택 관측·
   FailSafe/LocalProtection CAN/P05 Actual·원래30ms whole-interval freshness를 별도 검사한다.
   정상 credit/permission을 재발급하거나 정상 모드로 복귀하지 않는다.
3. `protection-a`의 보호 직전 속도0.098321266m/s, scenario 보호의0.433586922m/s에서 실제 감속했다.
   각400physics/400정산 중 뒤200구간은 보호 Actual이다. 마지막100구간 모두 wheel exact0,
   실제 torque0/pressure1MPa였다. body 잔류 속도는 원본 그대로 기록했다. 마지막100구간 범위는
   저속 사례−1.5822e−5..0m/s, scenario 사례−2.0491e−4..0m/s다.
   **world freeze가 아닌 감속/휠 정지 관측이며, 차체 완전 정지 수용은 아니다.**

## 실행 분모와 실패

fresh server 총11회: 수정 전 진단1회 강제−9, 수정 후10회 SIGINT130.
로딩 중단 수정 후3회는4.374/3.621/3.471s로 기존30s 한도 안에 종료했다. 디스크 캐시를 강제로
비우지는 않았으며, 매번 world 준비 전200ms read-only RPC timeout을 확인한 실제 loading abort다.
전체 content/다른 종료 원인을 수용한 것은 아니다.

| 실행 | launcher 결과 | receipt/EV 정산 | server exit / SIGINT 이후 |
| --- | --- | --- | --- |
| final/camera-a | COMPLETE_ISOLATED_RUN | 900/900 | 130 / 1.867s |
| final/loading-abort | COMPLETE_LOADING_ABORT | —/— | 130 / 3.471s |
| final/protection | COMPLETE_ISOLATED_RUN | 400/400 | 130 / 1.817s |
| final/work-missing | COMPLETE_ISOLATED_RUN | 200/199 | 130 / 2.068s |
| diagnostic-a | SERVER_EXIT_FAIL | —/— | -9 / 30.866s |
| loading-fixed-a | COMPLETE_LOADING_ABORT | —/— | 130 / 4.374s |
| normal-camera | COMPLETE_ISOLATED_RUN | 900/900 | 130 / 1.667s |
| protection-a | COMPLETE_ISOLATED_RUN | 400/400 | 130 / 1.667s |
| suite/loading-abort | COMPLETE_LOADING_ABORT | —/— | 130 / 3.621s |
| suite/protection | COMPLETE_ISOLATED_RUN | 400/400 | 130 / 1.717s |
| suite/work-missing | COMPLETE_ISOLATED_RUN | 200/199 | 130 / 1.767s |

- 최초 `diagnostic-a`: GDB exit0, 종료30s 초과/−9. 진단 자체의 성공을 서버 종료 PASS로 쓰지 않았다.
- `rpc-original`: normal 통과, queued/network TIMEOUT, ignored/late는 callback 금지 assertion 실패−6.
  `rpc-patched`: 동일5case 모두 통과, ASan/UBSan 적용. 정적 rpclib 전체를 sanitizer로 재빌드한 것은 아니다.
- 첫 UE RPC header 재빌드는 대화 중단으로 완료 증거가 없다. `ue-rpc-build-resume.log` 및
  최종 `ue-final-build.log`는 exit0. libcarla build/install도 exit0. Client API 변경은 없어 wheel 재설치 없음.
- native 최종 Normal/ASan **각73/73**, 전체 SDK/M6 회귀의 새 수용 숫자가 아니다.
- 정상 영상2회 각각900receipt/900정산, RGB/GT 각각180개·원래frame/source timestamp.
  GT는 TRAIN_EVAL_ONLY이며 제어 입력에 사용하지 않았다.
- 보호3회 각각400receipt/400정산,119정상·200보호·4empty INIT. 나머지77구간은 기존 INIT Actual.
  독립 raw-wire/P05·물리 effort·solver 방정식·EV 장부 검사와 보호 metadata4종 손상 거부.
- work 누락2회는200receipt/199정산 후 다음tick 차단, native exit1이 기대 결과다.
  누락한 work를0으로 대체하거나 마지막 미정산 구간을 에너지 PASS로 세지 않았다.
- 최종 `final/suite.json` 4case(protection/camera/work-missing/loading-abort) 전부 통과.
  native admission 최종 보강은 bootstrap의 보호 위장, 첫 선택 시각 역행, 선택시각 변경,
  보호 Actual replay/future/다른 Zone을 거부한다. M6 receiver를 reset하지 않는다.

## 보존과 대조

[run-summary.json](run-summary.json)은 launcher/probe 결과를 분리하고 마지막 포트 상태를 기록한다.
[installation-audit.json](installation-audit.json): M6 원천40파일 hash 동일, UE tracked diff 없음.
기존 integration 중 변경은 CARLA RPC Server.h이며, 생성 M7 admission/port 파일도 갱신했다.
모든 실제 server/module/native executable hash는 각 server JSON에 있다.

[physics-comparison.json](physics-comparison.json): 이전 통합 normal-b와 최종 camera의900구간,
보강 전후 scenario protection의400구간, 최종 정상/보호의 전환 전200구간에서
**generation을 제외한 전체 physics 객체가 정확히 같았다.** wall 시간·floating timestamp·EV SOC의
bit 동일성을 이 비교로 주장하지 않는다.

원본 trace/log는 lossless gzip으로 보존한다. [archive-manifest.json](archive-manifest.json)에
원본SHA256와 archiveSHA256를 모두 기록하고 압축 해제 바이트 hash를 확인했다.
`executed-sources`는 실제 실행 hash와 맞는 Python/프로젝트 source snapshot이며, UE/native binary는
외부에 두고 hash만 보존한다. `SHA256SUMS`는 저장되는 evidence 전체의 바이트를 대상으로 한다.

## 남은 실시간 문제

최종 camera 실행에서 native 왕복 평균1.652ms/최대3.083ms였지만 이것은 개별 job4ms 판정이 아니다.
CARLA/trace 대기 중 native 실행 공백 평균36.801ms/P99 70.343ms,900/900공백이2ms를 넘었다.
250ms 의도적 pause를 포함한 수치다. 원래2ms/4ms와 clock agreement는 **NOT ACCEPTED**다.
본 작업은 독립 wall executor 또는 deadline fault 자동 보호 연동을 구현했다고 주장하지 않는다.

현재 native runner는 WHEEL 한 번에 logical job을 묶어 실행한다. 이를 실제 wall owner/monitor와
CARLA IPC·trace worker로 나눠야 하며, 실제 clock mapping/uncertainty·job release/completion 및
fault→LocalProtection→fresh Actual을 검증해야 한다. 단순 heartbeat, source restamp, expiry 연장으로
해결하지 않는다. Actual/work 자체가 없는 경우 다음 tick 차단을 유지한다.
원래 renderer Distance Field crash 원인과 차체 완전 정지 수용도 이번 통과로 닫지 않는다.
M8 route/controller, AI/Jetson은 이번 범위가 아니다.

## 재현

기존 별도 설치 경로를 사용한다. 아래 suite는 각각 새 서버를 띄우며 기존 포트 점유를 거부한다.

```sh
python3 tests/integration/carla/m7_integrated_run.py \
  --engine /d/shin/stratadrive-tools/UnrealEngine_4.26 \
  --source /d/shin/stratadrive-tools/m7-source/carla-0.9.16 \
  --python /d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python \
  --fixture /d/shin/stratadrive-tools/m7-source/m7-1m-fixture \
  --native build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow \
  --runtime /새로운/외부/runtime --output /새로운/evidence \
  --cases protection camera-a work-missing loading-abort
```

정확한 실행 argv는 server/suite JSON, component build/run은 rpc-original/rpc-patched 결과를 따른다.
GDB는 소유 child와 supervisor에만 허용하고 host Yama/ASLR를 변경하지 않았다.

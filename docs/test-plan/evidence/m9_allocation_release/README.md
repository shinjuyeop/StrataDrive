# 지연된 배분 회차와 권한 심사 일치

2026-11-05, base `da19483`. 제어 결함은 재현·수정했지만 이 후보의 native 서비스
전체는 **27/30**으로 미수용이다. 원본 실패를 성공으로 합치지 않는다.
[사전 입력/위상 protocol](../../owner-input-phase-protocol.md),
[배분 회차 protocol](../../allocation-release-protocol.md), [개별 결과](results.json)를 따른다.

## 확인한 결함과 수정

외부 release 작업이 지연되면 기존 코드는 이전 대기 회차로 grant를 심사한 뒤,
현재 회차를 완료로 기록했다. `input-phase/tsan-normal`에서 심사 회차는
823332210120072ns, 실제 기록 회차는823332220120072ns였다. 기존 명령 expiry는
823332229714461ns로 다음 회차보다405611ns 빨랐다. Front/Rear의 명령 수신은
만료보다4.837ms/3.305ms 앞섰으므로 이 실패를 단순 전송 지연으로 해석하지 않는다.

수정은 현재 enable grid의 회차로 심사하고 callback 중 다른 회차로 넘어가면 다시
심사하도록 보류한다. 입력 issuer도 대기 중인 allocator와 독립된10ms grid에서 실제
새 root를 발행한다. 원본 source/expiry,18ms support는 늘리지 않는다.
기존 구현에서 실패하는 회귀2개가 수정 후 통과했다. 원본 CSV의 명령 생성 시각과
직전 심사 회차 대조는4422개 중1개 불일치에서4441개 중0개로 바뀌었다.
이 대조의 grid phase는 원본 release row에서 구하며 별도 Clock agreement 증명은 아니다.

선행 수정은 물리 IO 뒤/VM snapshot 직전의 두 ingress pass가 lane별8건 총 budget을
공유하게 했다. 원본 PowerStatus의 ingress와 VM snapshot 시각을 남긴다. StopRequest는
원래20ms period를 VM의+4ms grid에 맞추고 놓친 회차를 재생하지 않는다.

## 고정 분모

| 후보 | 기능 | 서비스 최초 감사 | 원본 재감사 |
| --- | ---: | ---: | ---: |
| input-phase | 12/12 | 26/30 | 29/30 |
| release-slot | 12/12 | 27/30 | 재분류 없음 |

Input-phase의 stop-request-loss3건은 NormalStop이 실제 SD-1105를 먼저 기록했다.
Allocator SD-1002만 허용하던 감사기에 원본 Braking/root/source/expiry/검출시각과
Coordinator Stop 전파의 엄격한 대조 및 추가 mutation4개를 넣었다. 각8개 mutation을
거절했고 기존 최초 실패 로그를 보존한다. 남은1건은 위 실제 회차 결함이다.

Release-slot은 Normal6/6·ASan6/6·TSan15/18이다. 남은3건은 다음과 같다.

- `tsan-ack-loss-r2`: 의도된 고장 주입 전 Epoch2 정상 정지 중 Rear 갱신이 기존 expiry보다143904ns 늦게 수신됐다.
- `tsan-normal-r3`: Epoch3 정상 정지 중 Rear 갱신이 기존 expiry보다282079ns 늦게 수신됐다.
- `tsan-stop-request-loss-r3`: 의도된 요청 상실 뒤 source+50ms+1 경계에서 generic Central 보호가 먼저 선택됐다. Gateway의 원본 만료 DTC는 있으나 Central NormalStop의 최초 RequestLost 관측이 없어 엄격한 감사는 실패다.

[갱신 원본 연결](remaining-renewal-failures.json)을 보존한다. 후자의 관리 주기 사이
진단 연결은 별도 [poll 후보](../m9_stop_deadline/README.md)에서 수정·재검증한다.
별도 [SMT 배치 후보](../m9_sdk_smt/README.md)도 채택하지 않았다.

## 검증과 보관

기능 변경 후 Debug·ASan/UBSan 전체1269개씩과 관련 TSan59개가 통과했다.
정적 분석의 기존 설정 객체 복사 경고를 const reference로 정리한 뒤 영향 제어81개씩을
Normal/ASan/TSan으로 다시 확인했다. 변경 TU cppcheck·clang-tidy 및 Python38개가 통과했다.
CARLA `-L m7` 선택은0건이어서 통과로 세지 않는다. `^M7`125개 후6개 target 전체162개를
직접 실행해 통과했다. 전체 로그와 초기 실패를 보존한다.

`input-phase-*`와 `release-slot-*`는 서로 다른 source/binary의 기록이다.
각5개 service archive는 Normal1·ASan1·TSan1/2/3 round를 포함하고 기능12건은 별도다.
Source archive와 manifest, 당시 빌드 설정, orchestration/분석 도구, 실패·재감사 로그를
분리 보관한다. [동일성 확인](identity-checks.json)은 해당 후보를 포장한 시점 기준이다.
후속 변경의 전체 재검증이나 Target·native4ms·M9 전체 완료를 뜻하지 않는다.

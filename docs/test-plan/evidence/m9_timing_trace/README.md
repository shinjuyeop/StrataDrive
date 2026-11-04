# M9 SDK 계측 잠금 제거와 직접 호출 시각

2026-11-04, base `81be788` 및 [앞선 후보](../m9_feedback_order/README.md) 위의 별도 변경.
**서비스28/30(Normal6/6·ASan6/6·TSan16/18), overflow/close-full4/4.**
응답 지연 전체는 아직 미해결이다. 앞선29/30·12/12와 합쳐 통과율을 만들지 않는다.
[사전 protocol](../../timing-trace-protocol.md), [ADR-0100](../../../archive/design-decisions.md#adr-0100).

SDK timing의 공용 기록 mutex를 시작 전에 초기화한131072개 슬롯과 atomic reservation으로
바꿨다. Writer는 서로 다른 슬롯에 쓰고 모든 writer join 뒤에만 읽는다. 포화는 실패로
남으며 기존 행을 덮거나 count를 wrap하지 않는다. SDK 호출 직전/직후 wall/thread CPU를
읽고 return 뒤 기록하므로 trace append 대기를 SDK call 시간에서 분리했다.
SDK 구현/설정·CPU/policy·queue8·source/expiry·18ms support와 제어 주기는 유지한다.

## 검증과 남은 구간

동시 writer 완전성·포화 후 비덮어쓰기·멈춘 writer와 다른 슬롯 진행의3개 시험을
Normal/ASan·UBSan/TSan에서 각각 통과했다. Python30개, 실제 SDK3TU cppcheck/clang-tidy도
통과했다. Compiler/third-party warning 원문과 명령은 validation archive에 있다.
앞선 후보의 C++152개를 이번 후보에서 다시 실행한 것으로 세지 않는다.

Normal/ASan overflow와 close-full은4/4이며 두 close-full 모두 요청16건 negative 결과,
원래 시각/기한 대조·SDK 오류0·sender 생존·새 Epoch 재시작을 확인했다.
기능 runtime4개 뒤 서비스 runtime30개를 실행하고 모든 독립 감사는 마지막에 수행했다.
재시도/실패 제외/온도 기준 대기는 없었다.

서비스 실패2개는 의도한 손실 검증의 선행 정상 정지에서 발생한 갱신 실패다.
`analysis.json`의 원본 token/expiry/SDK stage와 raw capture를 따른다.

| Case | 원래 만료 대비 새 command 수신 | 인접 SDK 관측 |
| --- | --- | --- |
| tsan-ack-loss-r2 | Front token469가0.216268ms 늦음 | Rear Feedback SDK send→Central callback4.047359ms; SDK call9.133µs |
| tsan-stop-ack-loss-r2 | Rear token455가0.428308ms 늦음 | Central request SDK send→Rear callback3.230250ms; SDK call11.872µs |

정상 service/slow-signal 실행은 완료됐지만 의도한 고장 주입의 선행 정상 구간 실패도
분모에 포함한다. 순서·배치·accepted-response 감사 성공으로 service 실패를 바꾸지 않는다.
새 계측은 기록 잠금 없이도 SDK 호출 후 callback까지 수ms가 남음을 보여준다.
SDK IO/dispatcher 내부 대기와 OS runnable 대기는 아직 분리하지 못했다.

`direct-call-analysis.json`은 남아 있는 완전 send pair329451개의 관측이다. 가장 긴 SDK
call은2.434092ms/thread CPU34,196ns였지만 이는 위 두 실패의 직접 원인으로 단정하지 않는다.
SIGKILL process의 미저장 구간이나 완전 end-to-end 분모를 이 통계로 대체하지 않는다.
Wall/CPU 순차 clock 읽기는 정확한 kernel 대기 계측이 아니다.

Host24907표본, 최대100°C, thermal counter+814. 두 실패 전후25ms는 각각 최대88°C,
thermal 증가0이며 CPU1–7 모두 약800MHz인 표본도 없다. 외부 부하/냉각 통제가 없으므로
29/30→28/30의 차이로 성능 개선이나 악화를 입증하지 않는다. 시스템 전력/thermal 설정은
변경하지 않았다. Native4ms/Target·장기 부하·CARLA와 M9 전체 수용은 별도 OPEN이다.

## 재현 자료

`results.json`에 모든34개 실행·source/binary manifest·명령·감사 exit가 있다.
Service raw archive는 profile/repeat별이며 공통 metadata/source는 `service-metadata.tar.gz`다.
`source-final`과 `identity-checks.json`은 이 후보의 최종 측정 소스/실행 파일을 검증한다.
재추출 감사에서 정상과 의도한 Actual-loss 통과, ACK-loss-r2 실패 및 close-full 통과를
그대로 재현한다. `SHA256SUMS`는 전체 보관 파일의 무결성을 확인한다.

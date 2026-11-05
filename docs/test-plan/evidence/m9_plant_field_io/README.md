# Host SIL 필드별 IO 전달

2026-11-05, base `ddac8ec`. [사전 protocol](../../plant-field-io-protocol.md)의
기능 **12/12**, 서비스 **28/30**(Normal6/6·ASan5/6·TSan17/18)이다.
선행 실패·후속 후보와 분모를 합치지 않았다. 전체 M9는 OPEN이다.

## 원인과 변경

[선행 Brake 원본](original-analysis.json)의 Actual83은 Normal/1000000Pa,
84는 유효 NormalPath/Degraded/952000Pa다. 누락이나 command expiry가 아니었다.
물리 전달 지연과 monitor 응답 위반을 구분하며 원본에 없는 syscall 시각은 추정하지 않는다.
전체 파일 read/modify/write 잠금을 sensor·각 Leaf output·Release별 nonblocking
OFD lock으로 분리하고, Leaf 실행 직후 같은 turn에 출력을 전달한다. 다른 필드의
경합이 제동 출력까지 막지 않게 했고 busy 시 원래 source/epoch를 유지한다.
원래 control deadline·detector/tolerance·물리 적용 시각을 바꾸지 않았다.

원래 주입 전 Brake 실패는 이번30건에서 재발하지 않았다. 새 시험의 전체 통과나
Host 지연의 최악 상한을 뜻하지 않는다. 새 raw archive와 source/binary hash는
[결과](results.json) 및 [포장 시 동일성](identity-checks.json)을 따른다.

## 남은 실패

- ASan normal-slow-signals: 실제 Central1 단절 뒤 Rear SDK 외부8192-byte 송신
  큐가 포화되어5개 packet이 폐기됐다. 연결 불가 이후 enqueue를 계속한 경로를 확인했다.
- TSan normal-r3: Rear Stop token674의 원래20ms 기한보다 늦은25.304616ms에
  응답이 도착했다. [원본 SD-1102](tsan-stop-root.json)는 native reason0x20007이며,
  요청 source872247774855809/expiry872247794855809를 보존했다.
- 관련 TSan116개 중 메모리 기반 M4 wall 정상 시험1건이 실패했다(115/116).
  이 경로는 PlantIO를 사용하지 않는다. 실패를 재실행하거나 제외하지 않았다.

전체 Debug/ASan·UBSan 각1277개, 새 IO 경합/재시도/short-read4개, 변경 header 포함
cppcheck/clang-tidy, Python42, CARLA adapter 논리162개가 통과했다. CARLA 서버나
native4ms/Target의 재검증으로 표시하지 않는다. 실패 후 원래 계획의 native42건을
진단 근거로 진행한 이유와 gate 한계는 사전 protocol에 기록했다.

[이전 SDK 종료 오류 시각 대조](sdk-cause.json)와 [TCP 강제 종료 최소 재현5회](tcp-crash-proof.json)는
강제 종료와 OS reset/broken pipe의 관계를 설명한다. 원본 SDK 오류 판정은 변경하지 않았다.
전체 완료 항목은 [프로젝트 상태](../../../project-status.md)를 따른다.

# Proposal 이전 기동 incident 연결

2026-11-05. [고정 protocol](../../bootstrap-incidents-protocol.md)의 Linux Host 범위를
구현·검증했다. **M9 전체 완료는 아니다.**

EpochStore initialize/issue와 native journal initialize/open 실패를 DTC store와 별도인
영구 spool에 기록한다. Application Epoch를 만들지 않으며, begin을 확정한 뒤 작업하고
outcome을 확정한 뒤 다음 단계로 반환한다. 실패·SIGKILL 중단은 새 기동 성공 뒤에도 남는다.
Epoch 발급 후 outcome 기록 실패는 해당 번호를 반환하지 않고 다음 issue에서 건너뛴다.

Native writer의 초기 active source/context/collector 검증을 `start()`에서 기다리도록
연결했다. Central/Front/Rear의 실제 journal-open 실패에서 각 process의 owner 생성·
제어 Epoch·Release·armed가 모두 없음을 확인했다. 초기 실패 시 owner가 없는 종료 경로의
역참조도 차단했다. Spool 자체가 없으면 EpochStore 생성부터 시작하지 않는다.

| 검증 | 결과 |
| --- | --- |
| Debug·ASan/UBSan·TSan component | 각 **11/11**, 총33; sanitizer 오류0 |
| 실제 native startup 동일7조건+명시적 재시도 | normal·ASan·TSan 모두 통과; 각17 process, 총51 |
| 관련 journal/startup CTest | **32/32**; 초기 bootstrap11을 포함하며 최종33과 중복 합산하지 않음 |
| Python reader·기존 pilot·서비스 판정 | **43/43**; reader 변조17건 거절 |
| 조용한 환경의 정상 terminal 서비스 회귀 | **1/1**, 원래 split-v1 배치·기한·물리 기준 |
| 서비스·ordering·placement·response 감사 | **4/4**, 변조29건 거절 |
| clang-tidy·cppcheck | 변경3개 translation unit, 최종 검사 통과 |

Native startup의 기대 실패는 실제 exit1로 보존했다. 한 빌드당 missing-spool1건과
기록된 실패5건이며 성공으로 exit를 바꾸지 않았다. Epoch 경로 충돌 후에는 기존 경로를
자동 삭제하지 않고 **새 workspace를 명시해 같은 spool로 재시도**했다. 과거 failure bytes가
유지된다. SIGKILL·손상된 Epoch·outcome 충돌은 실제 filesystem/process component 시험이다.
첫 issue 실패의 native8-role 고장 주입을 별도로 수행했다고 주장하지 않는다. 정상 서비스는
실제 issue/re-INIT와9개 기동 기록, 원래 DTC/서비스 흐름까지 확인한다.

## 원본·무결성·초기 결과

[판정](acceptance.json), [보관본 검사](archive-verification.json), [source/hash](sources.json),
`sources.tar.gz`, `validation.tar.gz`, `SHA256SUMS`를 보존한다. Validation archive에는
모든 build/실행 명령·XML·stderr·raw journal·별도 persistent store 사본·PCAP·물리 trace·
초기 시도·독립 감사·포장 script가 있다. `/var/tmp` 원본도 지우지 않았다.
압축 해제 후 component/native spool51개와 서비스 감사4개를 다시 검사했다.
시험의 절대 symlink6개는 target 문자열만 대조하고 압축 해제 시 따라가지 않았다.

- 첫 compile은 같은 줄의 GoogleTest `EXPECT_THROW`2개가 label을 중복 생성하여 실패했다.
  줄을 분리한 뒤 모든 빌드가 통과했다. 초기 build 로그를 보존했다.
- 초기 clang14는 GCC13 `<chrono>`를 해석하지 못했다. 저장소에서 이미 쓰던
  libstdc++11 analysis include 방식으로 front adapter를 재검사했다. 실제 GCC13 빌드의
  헤더/언어 수준은 바꾸지 않았다.
- 초기 cppcheck의 `string_view` 값 전달 지적은 const reference로 수정했다.
- 초기 component3빌드 통과와 native5조건/7조건 통과도 남겼다. 최종 component에는
  실제 Epoch 비재사용 검사를 추가했고, 최종 native cohort는 sanitizer 실행 옵션까지
  동일한 runner로 실행했다. 최초 실패를 삭제하거나 최종 분모에 몰래 합치지 않았다.
- 정상 서비스 후 달라진 source fingerprint는 이 서비스에서 호출하지 않는 별도
  startup 시험 runner의 sanitizer 옵션 추가뿐이다. C++와 실제 서비스 launcher는 같다.

## 수용 범위

Quiet 서비스1회는 이전18건을 대체하지 않으며 native 전체 sanitizer 성능 수용도 아니다.
실제 storage power-cut·전체 디스크 장애의 독립 redundancy, 장기 spool 용량/rotation,
원격 운영 reconciliation은 시험하지 않았다. Spool 자체를 쓸 수 없으면 기동을 막지만
그 오류까지 같은 고장 난 저장 매체에 영구 기록했다고 주장하지 않는다.
Clock 복구·CARLA silent packet loss subinterval·남은 Power5원인의 차량 통합·
부하/장시간 timing과 보존 정책은 [현재 상태](../../../project-status.md)에 남아 있다.

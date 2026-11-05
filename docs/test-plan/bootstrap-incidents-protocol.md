# Proposal 이전 기동 incident 시험

고정 범위는 Linux Host의 EpochStore initialize/issue와 native 진단 journal initialize/open이다.
운영 세션의 DTC와 별도인 `BootstrapJournal`로 시도·결과를 보존한다. Application Epoch를
만들어 채우지 않으며 재시도 성공도 과거 실패/중단을 Passed/Clear로 바꾸지 않는다.

## 실행 전 판정

- 새 spool의 정상 작업, 실제 없는/손상된 EpochStore, 막힌 journal 생성 경로, 없는 journal
  open, spool 자체 손상/부재, 중복 initialize, symlink/private mode, outcome 중복/충돌,
  긴 exception, non-standard exception, begin 이후 SIGKILL와 새 process/attempt를 검사한다.
- Debug·ASan/UBSan·TSan에서 동일 component 시험을 실행한다. 각 executable watchdog은
  120초이며 TSan은 기존 `setarch x86_64 -R` 방법을 사용한다. 네이티브 wall 성능 판정이 아니다.
- 실제 `someip_front_adapter bootstrap`에서 정상/epoch 경로 충돌/journal 경로 충돌/spool
  부재를 검사한다. 실패 exit와 별도 spool, epoch 반환/제어 세션 부재를 원본으로 남긴다.
- 실제 Central/Front/Rear journal-open startup 실패는 SDK가 초기 journal 검증을 보고할 때까지 `start()`가
  기다리는 경계로 확인한다. 정상 서비스 1회는 모든 빌드·분석 종료 후 기존 split-v1 배치와
  원래 timing/물리 감사 기준으로 회귀한다. 이 1회로 기존 18회 cohort를 대체하지 않는다.
- Writer 초기화 future 경계는 native normal·ASan/UBSan·TSan의 같은7조건과 명시적 retry로
  검사한다. Process watchdog15초이며 실제 제어를 시작하지 않는 기동 실패 기능 시험이다.
  TSan만 process-local ASLR 해제를 쓰며 sanitizer diagnostic은 기대 실패에서도 허용하지 않는다.
- Python reader로 320-byte record의 CRC/고정 padding/identity/phase/순서를 독립 확인하고
  손상 CRC, CRC를 고친 잘못된 identity/kind/time, truncated record, pending outcome을 거절한다.
  유효한 begin에 outcome이 없으면 `interrupted`이며 성공으로 세지 않는다.
- 모든 실행 exit·실패 로그·source/binary hash를 보존한다. 초기 compile 실패도 분리 기록한다.

## 저장 계약과 한계

Root는 명시적 fresh initialize만 가능하고 mode0700의 소유자 전용 local filesystem이다.
`format`은 `SDBOOT\0\1` 8바이트다. 각 무작위128-bit attempt directory에 `begin`과
`outcome`을 별도 기록한다. 작업 전에 begin file·attempt directory·root directory를 fsync한다.
Outcome은 임시 파일 fsync→기존 destination을 덮어쓰지 않는 link→pending unlink→directory
fsync 후 반환한다. 오류가 나면 작업/epoch를 다음 단계로 반환하지 않는다. 이미 발급된 Epoch는
건너뛸 수 있으며 되돌리거나 재사용하지 않는다. 미완료 파일은 자동 삭제하지 않는다.

Record320의 little-endian 배치는 magic0:8, kind8(begin1/success2/failure3), operation9
(epoch-init1/journal-init2/journal-open3/epoch-issue4), role10(supervisor0/central1/front2/rear3),
reserved11, pid12:16, began_ns16:24, observed_ns24:32, random attempt32:48,
kernel boot UUID48:64, message length64:66, truncated66, reserved67,
message68:308(최대240바이트), zero padding308:316, IEEE CRC32 316:320이다.
Begin은 message가 없고 observed=began이다. Outcome은 같은 identity/operation/role/pid/began을
가진다. Clock은 같은 boot의 CLOCK_MONOTONIC이며 wall time으로 순서를 추정하지 않는다.

별도 `/var/tmp/stratadrive-bootstrap-*/incidents` 원본은 실행 후에도 유지하고 evidence에 복사한다.
Spool 자체를 만들거나 쓸 수 없으면 startup을 실패시킨다. 이 경우 영구 기록 성공을 주장하지
않으며 stderr와 supervisor 실패만 남을 수 있다. 전체 디스크/전원 손실의 독립 저장 redundancy,
장기 용량/rotation, 원격 전송/운영 수동 처리와 실제 power-cut 시험은 이 범위에 포함하지 않는다.

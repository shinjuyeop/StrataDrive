# M7-1q — native Actual/권한의 CARLA 적용

2026-10-27. 기준 commit `63119a8`. **실제 native Actual→CARLA 기능 연결 한정 검증 완료.**
전체 정상 주행·solver 구간 work/단일 EV 정산·wall2/4ms 수용은 미완료다.
M6 구현·통신/안전 계약·검증 수치/판정과 과거 실패는 바꾸지 않았다.

## 연결한 경로와 한계

`CARLA direct solver wheel → 원래 시각의 native 센서 → Central → Front/Rear → vECU →
Actual CAN/P05 → Zone → Central current feedback → Plant Adapter → NoDrive`다.
원래 command는 authority/인과 검사에만 쓰며 물리 입력은 세 Actual의 decode 값뿐이다.
실제8-role coordinator/participant/credit 및 Central/Zone/Leaf 구현을 기존 M7 functional rig에서
실행한다. 해당 rig는 단일 logical owner thread의 시험 구성으로 Host FIFO/SOME-IP/Target 배포가 아니다.

M7 전용 read-only mailbox delivery hook으로 **실제 소비된** 원본 Actual/명령/permission을 보존한다.
current Actual의 epoch/sequence/source, causal child sequence로 원본 프레임을 찾는다.
coordinator가 수용한8Release ACK·7remote RunLease와 Central local credit을 포함한8-role mask를
export한다. `--native-actual-export`만 이 경로를 사용하며 기존 shadow 모드의 행동은 유지한다.

서버의 별도 `-StrataM7NativeProbe -StrataM7V1Substeps320`는 기존 synthetic/zero 프로필과 상호
배타적이다. `stage_native`에서 owner-wire route/domain/CRC32C, 원본 receiver의 CAN/P05·cursor,
실제 ACK/동일 credit/원래 expiry, Actual·wheel source30ms/skew10ms, causal command/root30ms와
dependency70ms, 원래 BMS permission/parent50ms·dependency70ms를 **다음10ms 전체**에 검사한다.
Release ACK는 원래 exclusive commit deadline **미만**이어야 한다. 거부는 setter clear와 latch로 이어진다.
CRC를 인증으로 간주하지 않는다. local owner key는 child environment에만 있고 기록하지 않는다.
CARLA UUID/session/actor/generation/model/profile과 fresh native process의 scope를 결합한다.

시각은 같은 frame의 원래 CARLA elapsed seconds를 ns로 반올림한다. held 표본의 시각을 바꾸지
않으며 공개 corrected getter/abs/clamp/epsilon을 사용하지 않는다. 기존20ms Controller·10ms
Zone/vECU와30ms Drive source-age를 유지한다. 영상50ms 계약도 유지하되 이번에는 비렌더링이다.

처음4tick은 Actual이 없는 명시적 INIT 무입력 관측이며 전체80ms 미만으로 제한한다. 이후 native가
취득한 Init Actual(angle0.1rad, brake200kPa, torque0)을 그대로 적용한다. 정상 진입 뒤 INIT/empty
fallback은 불가능하다. 고정 upstream VehicleRequest는0.2m/s²·curvature0.02/m이며 본 시험은
그 입력에 대한 출발·전진 범위다. 일반 감속/정지/역회전·여러 차량/맵/영상·AI 검증으로 확대하지 않는다.

native external owner는 기존 actuator 응답과1ms 전기 ZOH 예측만 소유하고, 차량 운동은 CARLA만
계산한다. V1 가상 EV law/geometry/320분할은 변경하지 않았다. 예측 전기는 실제 solver work가
아니므로 `MODEL_ZOH_PREDICTION_NOT_CARLA_WORK`, `interval_work_valid=false`다. 서버의
`normal_driving_enabled=false`는 전체 수용 flag이며 실제 limited Actual 적용 여부와 구분한다.

## 실제 실행 결과

pinned UE4.26.2/CARLA0.9.16 source, Town03_Opt/mkz_2020/V1/NoDrive320, world10ms.
전용 source client/server version 문자열은 양쪽 `294096e-dirty`다. 아래 native는 source build
전용 Python client이며 공식 배포 wheel과 혼용하지 않는다. 실행 argv/hash/종료는 `server-*.json`에 있다.

| 새 소유 서버 | 실제 결과 | 범위 |
| --- | --- | --- |
| [live320a](live320a/result.json) | 400receipt,319정상 권한 구간,4empty INIT, 최종0.29092865m/s | 최초 functional 연결 |
| [live320-final](live320-final/result.json) | 동일400/319/4,18개 runtime 검사 | foreign batch writer/tick 거부, ticket 재사용 거부, synthetic stage 차단 포함 |
| [boundary-final](boundary-final/result.json) | 최종 ACK 경계 보강 binary:400receipt/319정상/4empty INIT,18검사 | 최종 수치는 독립 [audit](audit-boundary-final.json) 참조 |
| [credit](credit/result.json), [command](command/result.json) | 각각200receipt/119정상 뒤201번째 구간 적용 전 packet 누락 거부 | 최초 controlled fault; 아래 provenance 제한 참조 |
| [credit-final](credit-final/result.json), [command-final](command-final/result.json) | 각각200receipt/119정상 뒤 `native_owner_wire_route_crc`로 latch | 고정 실행 파일/스크립트 복사본으로 반복, 실제 run credit 또는 causal command packet 누락 |
| [snapshot-final](snapshot-final/result.json) | 200receipt/119정상 뒤 원래 이전 snapshot 유지,10s 한도 후 다음 native 입력/tick 차단 | local delivery 누락 주입. runtime 예외는 그대로 기록, containment만 기대 결과 |
| [legacy-zero](legacy-zero/result.json) | 최종 binary의 기존 zero 프로필:156검사/13receipt 통과 | 기존 oracle 결과 [audit](audit-legacy-zero.json) 참조 |

9개 소유 서버 모두 actor/설정을 정리하고 SIGINT130으로 종료했으며 forced kill은 없었다.
[cleanup 점검](cleanup-audit.json)에서2200/2201/2202 port가 모두 비어 있음을 확인했다. pause/실제 physics reset 후
기존 session은 latch 상태이며 다음 advance가 거부된다. 250ms wall 대기 중 frame/source는 그대로다.
누락 시 advance 재시도·timestamp 갱신·command 대체는 없다. snapshot 누락은 네트워크 전체 장애가
아니며10s 한도는 functional 수신 한도이지30ms freshness/2·4ms deadline 변경이 아니다.

독립 [raw-wire/physics oracle](../../../../tests/integration/carla/audit_m7_1q_native.py)은 server의
admission 결과 bool을 그대로 신뢰하지 않는다. 원본 owner CRC32C·CAN P05·명령 인과/expiry,
권한 plan, permission/parent, source·wheel 양자화 및 실제4륜 drive/brake/Ackermann setter를
재계산한다. 원본 epoch/sequence/source와 직접 solver→native→CAN 반환도 교차 확인한다.
구간 끝 source age 최대20ms, CAN wheel 차이≤0.005rad/s, torque0..60Nm를 확인했다.
각 audit의6종 손상 거부도 확인한다. 최소 command expiry 여유는 **1ns**다. 원래 exclusive
expiry 경계를 만족한 것이며 wall jitter/clock uncertainty 여유나 실제 deadline 수용은 아니다.

최종 Normal/ASan은 [각64/64](ctest-normal-boundary.log) / [64/64](ctest-asan-boundary.log)다.
기존 M7 60개와 새4개(정수·fractional clock/20종 wire·authority·인과 손상·bootstrap/skip·exclusive
ACK deadline)를 포함한다. Command CAN을 유효한 outer CRC로 Actual 자리에 넣어도 거부한다.
모든 손상 뒤 원본 재전달로 latch를 해제할 수 없다. M6 전체 회귀는 새로 실행하지 않았다.

## 발견한 실패와 수정

원본 로그/JSONL은 삭제하거나 PASS로 바꾸지 않고 무손실 gzip과 해시로 보존했다.

1. [native build01](build-native-01.log): SteeringMessage를 공통 metadata 기반형으로 간주해 실패.
   원래 필드만 명시적으로 읽도록 수정했다. [build03](build-native-03.log)은 codec CRC 함수의 서로
   다른 signature 때문에 실패했다. 이미 CRC를 검사하는 원본 decode를 사용해 중복 호출을 제거했다.
2. `native-preflight.jsonl.gz`: Drive Degraded NormalPath도 기존 정상 경로에서 합법적임을 확인했다.
   Normal만 허용한 초기 export 조건을 기존 계약과 일치시켰다. `admission-preflight-01.jsonl.gz`는
   build 실패 뒤 이전 실행 파일을 사용해 admission 필드가 없어 조사 script가 중단된 흔적이다.
3. `admission-preflight-02.jsonl.gz`: arm 때 BMS receiver를 처음 feed해 그 전에 수신 timeout을
   일으켰다. 원래 bootstrap Inhibit permission도 처음부터 receiver에 전달하며 timeout을 reset하지 않는다.
4. `admission-preflight-03.jsonl.gz`: 즉시 INIT 위상에서 index82의 Actual은 fresh지만 부모 명령의
   expiry는1.825000001s여서1.82→1.83s 전체 구간을 덮지 못했다. freshness/expiry를 늘리지 않고
   **새 적용 모드만** 최초 관측+8ms에 INIT을 시작한다. enable+29ms, leaf+9ms 부근 acquisition,
   Controller/management enable+14ms 위상으로 실제 job을 이동했다. 주기와 source는 그대로다.
   `admission-preflight-04.jsonl.gz`의 실패는 조사자가 clock domain에1을 넣은 입력 오류다.
   `admission-preflight-05.jsonl.gz`는 올바른 domain/새 위상에서400관측 전체 admission을 통과했다.
5. [server build01](build-server-01.log): UE uint64와 std::uint64_t 참조 타입 차이 및 pinned CARLA
   BoundingBoxCalculator.cpp의 우연한 unity include 의존 때문에 실패. 수신 임시값의 명시적 변환과
   해당 파일의 실제 의존 헤더2개를 installer에 추가했다. 최종 [server build](build-server-final.log) 성공.
   UE engine source는 수정하지 않았다.
6. 최초 `command` 실행의 서버 준비 중 native 실행 파일/검증 script를 보완했다. 시작 시 hash만
   기록하던 runner로는 나중 child가 읽은 파일의 동일성을 보장할 수 없어 그 실행은 provenance
   수용에서 제외한다. 이후 runner는 실행 파일과 import되는 probe 파일을 전용 runtime에 복사해
   고정하고 hash를 기록한다. `*-final` 시험은 이 복사본을 사용한다. 초기 functional/fault 관측은
   남기되 최종 고정 실행 반복 결과를 판단 근거로 사용한다.
7. 최종 검토에서 ACK commit deadline을 원래 exclusive 규칙과 맞추어 `>=` 거부로 보강하고
   plan의 prepare window 경계도 검사했다. 별도 boundary test와 새 server 실행으로 확인했다.

## 보존·재현·다음 단계

- [기존 plain SHA256SUMS 1,409개](frozen-all-prior-audit.json)는 모두 일치한다. frozen M6/M7 자료는
  변경하지 않았다. 새 installer는 원래 project 파일40개를 byte-for-byte 복사한다. [점검](install-audit-final.json).
- native/CARLA build와 실행 script는 repository에, 엔진/서버/venv·대형 binary는 기존 외부 경로에 둔다.
  각 `server-*.json`의 argv/probe_argv와 executed_artifact_sha256가 실제 실행 근거다. 새 복사본은
  `native_source_snapshots`에 경로를 기록한다. 토큰·owner key는 포함하지 않는다.
- `trace.jsonl.gz`에는 초기·실패 frame과 원본 native wire, Actual, physics/tire callback 관측이 모두 있다.
  `compression-*.json`은 압축 전 길이/해시/행 수를 보존한다. callback은 기존 진단값이며 완전한 work
  관측으로 승격하지 않는다. [SHA256SUMS](SHA256SUMS)는 이 디렉터리의 최종 파일을 고정한다.
- source guard/authority/expiry가 충족되는 이 local functional profile만 착수 가능하다. 일반 native
  운전 API, Host FIFO/SOME-IP 배포, 다중 입력/전체 ODD, renderer/AI/Jetson은 이번 범위 밖이다.

다음 **M7-1r**은 (1) solver 모든 구간의 work 관측점·누락 검출·원천 시간 설계/최소 실험,
(2) 성공 receipt의 관측 work만 단일 EV owner가 정산하는 연결, (3) 관측/정산 실패 시 중복 정산·
부분 적용·다음 tick을 막는 원자적 실패 시험으로 나눈다. 이후에 일반 가속/제동/정지 시나리오와
wall2/4ms·clock uncertainty 비용을 별도 검증한다. solver work가 없으면 모델 예측을 실측으로
대체하지 않고 해당 gate를 계속 OPEN으로 유지한다.

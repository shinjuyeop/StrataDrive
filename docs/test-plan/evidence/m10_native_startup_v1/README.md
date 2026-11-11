# Native4K 명시적 준비·입력 주파수·유한 실제 관측

2026-11-11. [사전 기준](../../perception-native-startup-v1-protocol.md)·
[547개 freeze](freeze.json)·[533개 parent](parent-freeze.json)를 따랐다.
저장 overflow 뒤의 [별도 메모리 기록 기준](../../perception-native-memory-v1-protocol.md)과
[554개 additive freeze](memory-freeze.json)는 원래547개를 그대로 포함한다.
4K3840×2304·D-FINE-M960 FP32·confidence·exact native resize·원래 source+100ms
**AND** offer receipt+100ms를 유지한다. 기본 S/runtime·M10 OPEN이며 실제 차량 제어,
ROS·Jetson 최적화/배포·새 독립 품질·wall20Hz·장기 운용 수용은 별도다.

## 구현과 준비 분모

PreparedNativePerception은 합성 BGRA XY gradient3회 준비 후 센서 session을 허용한다.
같은 추론 thread/backend를 유지하며 합성 결과는 발행하지 않는다. 전체 준비<10s,
2/3회 각각<100ms, 실패/취소 후 늦은 완료로 READY 복원 금지다. 동일 합성 byte buffer를
재사용하고 첫 생성 비용도 첫 call에 포함한다. Backend/session 생성은 별도 기록한다.
READY는 초기화 완료이며 인지 가용성/차량 permission을 뜻하지 않는다.

모든 준비와 센서 call의 identity/result/thread/time을 따로 보존한다. 기존 cold 실패를
성공으로 바꾸거나 준비 비용을 삭제하지 않는다. 모든 조회·출력 대기·late·missed slot을 남긴다.

## 녹화 개발3장:10/13/20Hz

각6초, 새 backend/명시적 준비, 실행 순서10→13→20Hz 각1회다. 영상은 사전 preload하고
렌더링/SDK 비용은 제외한다. 지연도 조건별로 달라지므로 주파수 하나의 효과나 보편적 안전
최소값으로 해석하지 않는다. State100Hz/관측50Hz는 각600/300회이며 missed slot0이다.

| camera | 센서 call / 발행 / 소비 frame | 유효 조회 / 전체 | 비율 | receipt→return P95 | 준비3회 ms |
| --- | --- | --- | --- | --- | --- |
| 10Hz | 60/60/60 | 127/300 | 42.33% | 52.518ms | 3863.137/41.793/34.733 |
| 13Hz | 78/78/78 | 185/300 | 61.67% | 47.880ms | 378.915/35.717/34.525 |
| 20Hz | 120/120/119 | 297/300 | 99.00% | 37.005ms | 371.871/35.440/35.074 |

258개 센서 추론 모두 발행됐다. 기존3 CUDA reference와 class/count, score1e-4/native box0.6px를
검사한다. 준비는 별도9회다.20Hz 마지막 발행은 마지막 조회 뒤여서120발행/119소비다.
10Hz의60frame이 모두 소비돼도 조회 가용성은42.33%다. Reference SYS-PERF-00220Hz는
유지한다.50Hz consumer가10Hz 관측을50Hz 새 정보로 만들지는 않는다. 유효기간을 연장하거나
빈 구간에 가짜 fresh result를 채우지 않는다. 다른 ODD/profile의10Hz 적합성을 판정한 결과는 아니다.

## 원래 두 실패와 개선

- prepared-01:180s 내 RPC 준비 실패,30s 종료도 초과해 exit-9/강제 종료. Client/합성 call/RGB0.
  [별도 복구 기준](recovery-protocol.md)과 [실행 전 선언](recovery-declaration.json)을 보존했다.
- prepared-01-recovery:서버 기동은 됐지만8-slot NVMe writer가 frame1300에서 overflow하여
 1161tick/232image에서 FAIL. 모든232장과 overflow 원본이 보존됐고 쓰기 오류0이다.
 231sensor call=226published+4late+1obsolete, pending1cancelled. V1 client가 early failure의
 per-completion trace를 저장하지 않았으므로 원인별 completion 재생을 꾸며내지 않는다.
 원래 packet/result/consumer age와 최종 counters, 준비3회 및 모든 원본은 감사한다.

이후 새 Host 진단 recorder는240개 immutable byte reference(최대8,493,465,600B)를 보관해
정상 측정 중 disk write를 없앤다. 센서/관측 종료 후 압축하며 순서대로 reference를 해제한다.
비정상 추가 frame은 FAIL과 기존 writer를 통한 긴급 보존이다. 이 큰 상한은 유한 PC 원본 수집용이며
production/Jetson 요구가 아니다. 실제 inference는 active1/pending1/current1이다.
새 client는 실패 때도 종료 후 worker/decision trace를 보존한다. 원래 V1을 수정하지 않았다.

## 실제 완료된 실행

모두 별도 새 Town04_Opt/Epic 서버, 소비 개발 site38/first person fixture, 공유 RTX3090다.
Prepared-02는 측정 중 NVMe writer, memory-01/02는 별도 사전 고정한 RAM recorder다.
기록 부하가 다르므로 성능 차이를 준비 또는 입력 주파수 하나의 효과로 단정하지 않는다.

| 실행 | tick / RGB | call / 발행 / late | 소비 frame | camera wall Hz | observer Hz / missed | primary 유효 조회 |
| --- | --- | --- | --- | --- | --- | --- |
| prepared-02 | 1202/240 | 240/238/2 | 237 | 11.637 | 49.763/5 | 450/1027=43.82% |
| memory-01 | 1200/240 | 240/234/6 | 234 | 11.709 | 49.476/11 | 450/1013=44.42% |
| memory-02 | 1202/240 | 240/240/0 | 239 | 11.324 | 50.000/0 | 461/1062=43.41% |

- prepared-02:active wall20.659s, world wall58.140Hz, 준비455.206ms. Receipt→return P9562.929ms. Late 원인 `{'receipt_only': 2}`.6개200-tick 구간 소비[39, 40, 38, 40, 40, 40]. Invalid 최장26조회/span599.983ms. Delivery tail 포함453/1037=43.68%. Exit130, 전체243.817s(사후 압축 포함).
- memory-01:active wall20.507s, world wall58.506Hz, 준비450.414ms. Receipt→return P9560.600ms. Late 원인 `{'receipt_only': 6}`.6개200-tick 구간 소비[40, 40, 37, 37, 40, 40]. Invalid 최장61조회/span1419.981ms. Delivery tail 포함455/1024=44.43%. Exit130, 전체236.702s(사후 압축 포함).
- memory-02:active wall21.249s, world wall56.561Hz, 준비505.275ms. Receipt→return P9564.739ms. Late 원인 `{}`.6개200-tick 구간 소비[39, 40, 40, 40, 40, 40]. Invalid 최장13조회/span239.987ms. Delivery tail 포함465/1072=43.38%. Exit130, 전체232.332s(사후 압축 포함).

Primary window는 camera enable→마지막 실제 tick 완료, secondary는200ms delivery tail을
포함해 sensor stop까지다. 첫 발행 전 구간을 삭제하지 않는다. 관측 sample 비율/invalid 첫·마지막
span은 정확한 연속시간 가용성/outage 길이가 아니다. 각 약12초 simulation의 유한 실행이며
장기 안정성이나 엄격한50Hz scheduling을 입증하지 않는다. 모든 완료 실행은6개200-tick 구간에
fresh 소비가 있고 source/camera 정지100ms 이후 최소5회 unavailable을 확인했다.

원래 SDK raw_data materialization은 offer 전 callback trace에 포함한다. Receipt budget을
renderer/acquisition부터의 wall end-to-end로 해석하지 않는다. Simulation source age와
monotonic receipt age를 따로 검사한다. OS cache는 통제되지 않았고 cold 서버 시작은 미수용이다.

## 원본·추적성·재감사

3개 완료 실행720장+실패232장=952개 모든 원본을60개씩16개 tar(마지막52개)에 보존한다.
각 archive1.5GB 미만이다. Zlib BGRA·RGB·압축 hash, 모든 raw의 Pillow/native tensor/health
exact,258개 녹화 개발 검출, source533→547→554를 fresh directory에서 검사한다.
실패 completion trace의 부재는 별도 제한이며 이 원본 감사 PASS로 원래 FAIL을 뒤집지 않는다.
미래 제외 union은 **6713개**다. 모든 새/실패 RGB를 포함하고 새 품질 표본으로 재사용하지 않는다.

```sh
OMP_WAIT_POLICY=PASSIVE build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_native_startup_v1/check-evidence.py \
  docs/test-plan/evidence/m10_native_startup_v1 build/m10-native-startup-v1/recheck-new.json
```

[validation.json](validation.json)·[SHA256SUMS](SHA256SUMS)·[검증 환경](verification-source.json)을 따른다.
Python318개, 기존 C++/boundary12개씩 Debug/Release/ASan, Ruff·문서 link/CSV를 확인한다.
Kernel C++는 parent와 동일하며 이전 standalone ASan/UBSan 근거를 유지한다.
준비 auditor의 pre-freeze unit fixture에 기본 camera/calibration identity 필드가 빠졌던 오류와
수정 전 로그도 보존한다. 모든 formal run은 수정/검증/소스 봉인 이후다.

원본 저장 공간 확보를 위해 repository-local Git LFS cache61개/19,853,243,520B를 같은 PC의
여유 filesystem으로 옮겼다. 모든 object 이름/SHA256/size 확인 후 local lfs.storage를 전환하고
검증된 이전 cache copy만 제거했다. [기록](lfs-cache-migration.json)을 남겼고 UE 시작/측정과
동시에 수행하지 않았다. 기존 evidence/history를 삭제하지 않았다.

## 다음 단계

초기 준비와 원본 수집기 문제를 구분했지만 실제 입력 공급 공백은 남아 있다. 다음은 renderer/SDK
source age·callback materialization·관측 scheduling을 분리 계측하고 인지 unavailable을 기존
상태/보호 경로로 전달하는 일이다. 현재 consumer는 관측용이며2D box를 actuator/metric state로
바로 바꾸지 않는다. 새 독립 품질·전체wall20Hz·장기 부하·Thor/Orin 각각의 전체 stack 배포가 남는다.
4K 유지·기본 S/runtime640·M10 OPEN·보드 최적화 후속 원칙을 유지한다.

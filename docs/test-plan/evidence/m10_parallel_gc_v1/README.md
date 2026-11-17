# M10 Parallel GC V1 — 30초 2회 PASS, 5분은 FAIL

동일 모듈에서 직렬 GC 옵션만 제거해 병렬 GC를 직접 비교했다.
**두 30초 시험은 통과했지만, 5분 시험은 60.241006517초에 HV 입력 만료로 실패했다.**
물리5ms·HV30ms·native2/4ms·GC61.1초와 원래 판정은 유지했다.
[사전 프로토콜](../../perception-parallel-gc-v1-protocol.md), [종합 결과](final-validation.json).

| 항목 | 30초 1회 | 30초 2회 | 5분 |
|---|---:|---:|---:|
| 원래 물리 판정 | PASS | PASS | FAIL |
| 정상 / INIT / 보호 구간 | 5838 / 162 / 0 | 5838 / 162 / 0 | 11881 / 162 / 47957 |
| native 누락 / 지연 | 0 / 0 | 0 / 0 | 18 / 0 |
| CPU 최고 | 78°C | 77°C | 90°C |
| 원본 영상 | 283 | 283 | 2789 |

GC 네 번은 21.210843 / 16.186567 / 17.388305 / 17.365686ms였다.
직렬 조건의32.55–38.62ms보다 짧지만 첫 GC 종료8.736304ms 뒤 HV 의존 나이가
30.095850ms에 도달했다. 새 held 입력이 이미22.863394ms 나이를 물려받고
7.232456ms 유지된 결과다. 첫 오류 전 native301,190슬롯은 누락·지연0이다.
218.915초의 owner9 한 슬롯과269.839초 부근17슬롯 누락은 별도 미해결 항목이다.
[최초 오류](normal-300s-01/first-fault-analysis.json),
[슬롯 분리](normal-300s-01/native-gap-analysis.json),
[누락 주변 원본 관측](normal-300s-01/native-gap-context.json).

원래 native CSV·최초 오류와 모든 admission60,000개·ingress36,009개가 재생에서
일치했다. 첫 post-GC 물리 구간 이후 다음 pump까지2.564712ms wall /2.565197ms
thread CPU가 들었고 문맥 전환은0이었다. 추가 여유2/1/0ms를 비교한50us 간격
읽기 전용 재생에서 실제 다음 pump는0ms 여유의 마지막 허용 표본보다도0.496209ms
늦었다. 여유만 줄이는 수정으로는 이 기록을 해결하지 못한다.
[정확 재생](normal-300s-01/admission-replay.json),
[갱신 구간 분석](normal-300s-01/recovery-window-analysis.json).
엔진 기본 분할 정리 예산2ms와 맞지만 이 과거 trace에서 해당 작업을 직접 계측한
것은 아니다. 후속 후보에서 직접 계측하고 분할 크기를 줄인다.

5분 카메라는 약9.28Hz다. 첫 오류 전 결과559개는 중앙78.55ms·p95 83.79ms·
100ms 초과1회다. 전체 결과 중앙78.27ms·p95 82.04ms·초과2회에는 보호 유지
영상이 섞여 있으므로 정상 주행 성능으로 승격하지 않는다. thermal throttle 증가는0이지만
90°C 최고값과 후반 native 누락이 있어 냉각·장기 안정성은 확정하지 않는다.
[오류 전후 지연](normal-300s-01/latency-phases.json).

모든 원본3355장과 독립 archive 검사,8개 동결 검사 재현,exact native replay를
보존했다. 미래 독립 품질 제외는27,550개다. 공유 runtime6개와 부스트100% 복원을
확인했다. 모든 물리 실행·서버 종료는70% lease가 끝나기 전에 완료됐으며, 이후
분석·압축은 물리 수용 근거가 아니다. [복원](restoration-confirmation.json).
source 동결본과 bounded-review는 Git에 포함하고, 전체 run/raw와 큰 metadata 묶음은
로컬에 보존한다. bounded-review는 부분 검토용이며 전체 실행 백업이 아니다. 원래 FAIL을 유지한다.

후속 [Purge slice V1](../m10_purge_slice_v1/README.md)은 owner의 증분 정리를 더
작게 나누고 직접 계측하는 시험 후보다. 현재 시작 도구는 후속 후보를 선택한다.
연속 주행·5분 안정성·native 인지 수용·전체 장면·독립 품질·각 Jetson 배포·M10은 OPEN이다.

무손실 압축·검증된 중복 추출 정리로 약29.48GB를 회수했다.
[정리 범위와 해시 근거](storage-closeout.json). 원본 source/run/raw archive와 active build는 유지한다.

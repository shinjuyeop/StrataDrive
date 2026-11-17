# M10 GC owner 3코어 V1 — 짧은 시험 PASS, 5분 FAIL

물리 owner를2→3코어, 렌더러·영상을4→3코어로 바꿨다. 첫 본 GC는 이전19.108ms에서
16.653ms로 줄었지만 **5분 시험은60.196초에 기존 HV 입력이 만료되어 실패**했다.
[사전 프로토콜](../../perception-gc-owner3-v1-protocol.md), [최종 검증](final-validation.json).

| 실행 | 정상 / INIT / 보호 | 판정 | 카메라 Hz | CPU 최고 |
|---|---:|---|---:|---:|
| 30초 1 | 5838 / 162 / 0 | PASS | 9.200 | 76°C |
| 30초 2 | 5838 / 162 / 0 | PASS | 9.200 | 78°C |
| 5분 | 11874 / 162 / 47964 | FAIL | 9.240 | 88°C |

5분의 직접 GC4회는16.653 /15.060 /17.504 /14.910ms다. 첫 증분 정리는419회·
최장164.231us로 나뉘어2.073초에 끝났다. 원래61.1초·12220프레임 주기와
정리100us 요청을 유지했고 모두 다음 GC 전에 완료했다.
[GC·정리 계측](normal-300s-01/gc-analysis.json).

첫 GC 뒤 정상 물리 프레임12331–12333이 진행됐지만, wheel/actuator를 통해
GC 전12330의 시각을 계속 상속했다. 마지막 HV의 상속 나이는21.389ms였고,
GC 종료13.607ms 뒤30.383242ms에 원래 보호가 걸렸다. 다음 pump는 GC 종료4.921ms에
시작했지만, 추가 preview1ms 조건에서102회 ineligible·7회 settlement 대기를 거쳤다.
[원본 프레임 발췌](normal-300s-01/gc-recovery-frames.json),
[원래 gate 재생·회복 구간](normal-300s-01/recovery-window-analysis.json).

원래 admission60000개·ingress36006개를 정확히 재생했다. 같은 원본 proof에 대한50us
간격 조회에서는 추가 여유1ms의 허용 구간이 GC 종료4.596ms에 끝났고,0.3ms 조회는
5.296ms까지 허용됐다. 이것은 다른 물리 궤적의 성공을 증명하지 않는다. 오류 전 정상
11874구간의 최종 preview 검사→적용은 p99 162.665us·최대251.494us였다.
이를 바탕으로 후속 [GC recovery preview V1](../m10_gc_recovery_v1/README.md)은
추가 여유만300us로 줄여 비교한다. 원래 최종5ms·HV30ms·held 만료 우선 순서는 유지한다.
관측 최대값은 미래의 지연 상한이 아니다.

5분 최초 오류 전 영상556개는 중앙80.604ms·p95 86.619ms·100ms 초과1회다.
이전2코어의78.37 /85.37ms보다 소폭 늘었다. 전체 영상2773개의 중앙80.192ms·
p95 84.318ms는 보호 유지 구간을 포함하므로 정상 주행 성능으로 대체하지 않는다.
이번 native1,500,010개 eligible 슬롯 누락·지연은0이며 exact replay·최초 오류 byte가
일치했다. 이전 간헐적 누락의 지속적 해결과88°C에서의 냉각 여유는 확정하지 않는다.

원본3338장을 보존했고 미래 품질 제외는34241개다. 세 실행의 원본·동결본 재감사와
판정을 보존한다. 실패를 성공으로 바꾸지 않는다. 공유6파일과 부스트100% 복원을
[확인](restoration-confirmation.json)했으며 측정·서버 종료는70% lease 안에서 끝났다.
최대30분 뒤 복원 후 남은 archive 검사가 진행됐다.

물리 owner CPU2,3,4,10,11,12 / native1,9 / renderer·영상5,6,7,13,14,15 /
관측0,8이며 SMT도 분리했다. 모듈은 이전 분할 정리와 동일한
`0520f2a91d3e918510e6f4631d869205bff524f1724adf8d395f8e1647a0066f`다.
Python526·동결본114·동일 C++28의 준비 근거와1576파일 동결본
`d18e60eeedf97c4da2aae471ecfd48ede027d4a889e77673d315621213965cc4`를 유지한다.
2K2560×1536·D-FINE-M960 CUDA·목표10Hz·renderer20Hz/MaxFPS60·CV/resize4도 같다.

초반 가감속 뒤 정지하는 유한 시나리오다. 연속 주행·전체 장면·독립 품질·native 인지 수용·
각 Jetson 배포·M10 종료는 OPEN이다. 현재 launcher는 후속 recovery 후보를 선택한다.

원본198개 raw 묶음을 무손실 압축하고, byte가 일치하는 추출본만 삭제해
29.35GB를 확보했다. 원본 source/run/raw archive와 전체 metadata는 로컬에
보존한다. Git의 bounded-review는 일부 검토 자료이며 전체 재현 원본을 대신하지 않는다.
[저장 정리](storage-closeout.json), [체크섬](SHA256SUMS), [해시 검증 근거](checksum-basis.json).

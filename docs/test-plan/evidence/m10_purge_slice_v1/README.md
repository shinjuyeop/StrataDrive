# M10 Purge slice V1 — 분할 정리 작동, 본 GC 뒤 만료는 남음

**30초 두 번은 PASS, 5분은60.226014049초 HV 만료로 FAIL**이다.
원래 물리5ms·HV30ms·native2/4ms와 판정을 유지했다.
[사전 프로토콜](../../perception-purge-slice-v1-protocol.md), [종합 결과](final-validation.json).

| 항목 | 30초1회 | 30초2회 | 5분 |
|---|---:|---:|---:|
| 정상 / INIT / 보호 구간 | 5834 /166 /0 | 5838 /162 /0 | 11881 /162 /47957 |
| native 누락 / 지연 | 0 /0 | 0 /0 | 0 /0 |
| CPU 최고 | 78°C | 77°C | 91°C |
| 원본 영상 | 283 | 282 | 2788 |

병렬 GC4회는19.108 /18.365 /18.363 /17.656ms였다. 첫 GC 뒤 증분 정리는407회에
나눠2.011초 동안 완료됐고 실제 작업 합계44.905ms·최장 호출153.288us였다.
나머지3회도 모두 완료됐으며, 원래12220프레임 간격과61.1초 주기를 유지했다.
[직접 GC·정리 기록](normal-300s-01/gc-analysis.json),
[원래6만 기록과 정리 무결성](normal-300s-01/admission-window.json).

첫 GC가 시작할 때 held HV의 의존 나이는 이미10.019119ms였다.19.107547ms GC가
끝나고 남은 만료 여유는0.873334ms였으며, 첫 분할 정리는 그 끝에서0.636933ms 뒤
시작했다. native가 원래 held 입력을 검사할 때 나이가30.002478ms여서 보호로 전환했다.
분할 정리만 줄여서는 본 GC와 기존 입력 나이가 합쳐지는 문제를 해결하지 못했다.
[최초 오류](normal-300s-01/first-fault-analysis.json),
[원래 입력 재생·남은 여유](normal-300s-01/expiry-window-analysis.json).

GC 종료를 기준으로 다음 프레임의 실제 admission은 +0.793ms에 통과했지만,
입력 준비 완료는 +0.957ms, 새 물리 관측 시작은 +1.625ms였다. 기존 held 입력은
+0.876ms에 만료됐다. 따라서 허용 검사 거절이 아니라, 허용 후 교체 입력을 만들기
전에 만료된 사례다. [원본 프레임 발췌](normal-300s-01/post-gc-frames.json)는
[추출 도구](extract-post-gc-frames.py)로 동일하게 재현한다.

native150만 eligible 슬롯의 누락·지연은 모두0이고 최초 오류와 전체 native 기록이
정확히 재생됐다. 이전 조건의18슬롯 누락이 이번에는 재발하지 않았다는 범위다.
CPU 최고91°C·관측 열 제한 카운터 증가0이며 장기 냉각 여유를 확정하지 않는다.
5분 카메라 약9.28Hz, 최초 오류 전 결과558개는 중앙78.37ms·p95 85.37ms·100ms
초과2회다. 전체의 초과3회와 보호 유지 영상을 정상 주행 수용으로 승격하지 않는다.
[전후 지연](normal-300s-01/latency-phases.json), [native 기한](normal-300s-01/native-gap-analysis.json).

원본3353장을 보존하고 미래 품질 제외는30903개로 이어간다. 전체 run/raw는 로컬,
source 동결본과 bounded-review는 Git에 포함한다. bounded-review는 부분 검토용이며
전체 백업이 아니다. 원본 archive·동결 검사 재현과 공유6파일·부스트100% 복원은
[종합 검증](final-validation.json), [복원 확인](restoration-confirmation.json)에 기록한다.

원본198개 묶음의 무손실 압축으로27.79GB, 해시 대조를 끝낸
추출 중복본 정리로1.68GB를 줄였다(합계29.47GB). 전체 원본·
동결본·검토 묶음·현재 빌드는 보존한다. [정리 근거](storage-closeout.json),
[최종 체크섬](SHA256SUMS), [대형 archive 해시 재사용 범위](checksum-basis.json).

후속 [GC owner3코어 V1](../m10_gc_owner3_v1/README.md)은 같은 모듈에서 물리 owner를
2→3코어, 렌더러·영상 공유를4→3코어로 비교하는 후보이며 아직 실행 전이다.
현재 시작 도구는 후속 후보를 선택한다. 연속 주행·5분 안정성·native 인지 수용·전체
장면·독립 품질·각 Jetson 배포·M10은 OPEN이다.

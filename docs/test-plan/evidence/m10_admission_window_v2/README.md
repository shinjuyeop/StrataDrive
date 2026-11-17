# M10 admission window V2 — 직렬 GC의 HV 만료 확인

수신 후 시각·structured 추가 여유 2ms와 실제 receipt 구조 검사기를 적용한
30초 시험 두 번은 모두 PASS다. 이어진 5분 시험은 **60.236004058초에 HV 의존 입력
30.077297ms 만료로 FAIL**했다. 원래 판정과 정확 native/최초 오류 재생을 보존한다.
[최종 검증](final-validation.json), [사전 프로토콜](../../perception-admission-window-v2-protocol.md).

| 실행 | 전체 / 정상 / INIT / 보호 구간 | native 누락 / 지연 | CPU 최고 | 카메라 |
| --- | --- | --- | --- | --- |
| 첫 30초 | 6000 / 5838 / 162 / 0 | 0 / 0 | 75°C | 9.30Hz |
| 둘째 30초 | 6000 / 5838 / 162 / 0 | 0 / 0 | 77°C | 9.27Hz |
| 5분 | 60000 / 11876 / 166 / 47958 | 0 / 0 | 89°C | 9.28Hz |

5분의 원래 native deadline 150만 슬롯은 최초 오류 전 301160개·이후 1198840개 모두
누락·지연 0이다. 관측된 thermal throttle 증가와 모든 CPU가 850MHz 이하인 구간도 0이다.
89°C 최고 온도와 유한 관측이므로 냉각·장시간 안정성을 수용하지 않는다.
[슬롯 분석](normal-300s-01/native-gap-analysis.json), [상태·클럭 분석](normal-300s-01/path-analysis.json).

직접 GC delegate 계측의 네 번 정지는 **38.242956 / 38.620542 / 32.994507 / 32.549041ms**다.
각각 thread CPU가 wall의 99.988% 이상이며 모두 원래 HV30ms보다 길다. 최초 오류는
첫 GC 안에서 발생했다. held HV sequence 12345의 선행 의존 나이 5.202451ms와
보유 시간 24.874846ms가 합쳐져 30.077297ms가 됐다. 최초 오류의 원본 입력과
GC 완료 frame 12345가 일치하며 exact replay도 같다. 따라서 직렬 GC 후보는 미채택이다.
[직접 원인 결합](normal-300s-01/first-fault-analysis.json), [GC 원본 검사](normal-300s-01/owner-gc.json).

짧은 시험의 영상 획득→결과 중앙값은 78.20 / 78.25ms, p95는 86.60 / 85.59ms,
100ms 초과는 5 / 2회다. 5분 전체 추론 2786개의 중앙값 78.04ms·p95 81.64ms·초과 6회는
보호 유지 구간을 포함한다. 최초 오류 전 물리 구간 내 결과 558개는 중앙값 78.06ms,
p95 83.61ms·초과 2회다. 보호 유지 이후의 수치를 정상 주행 성능으로 올리지 않는다.
[구간별 영상 지연](normal-300s-01/latency-phases.json).

준비는 두 번 보존했다. 첫 자산 준비 144.53초 이후에는 owner/lease/본시험이 없었고,
다시 실행한 준비 26.34초 후 새 owner PID 3006022로 70% 제한이 적용됐다.
세 실행의 측정·서버 종료가 모두 끝난 뒤 lease 1800초 제한으로 100%에 복원됐다.
그 후 보존 검사가 계속됐으며 공유 파일 6개와 원래 전원 설정도 확인했다.
[복원 확인](restoration-confirmation.json), [lease 원본](power-lease.jsonl).

모든 실행의 archive·동결 검사·정확 재생과 원본 판정 재현을 확인했다. 영상 원본
283 + 282 + 2790 = 3355장을 미래 독립 품질 평가에서 제외해 누계는 24195개다.
원래 BGRA·tar 바이트는 해시를 재확인한 무손실 압축으로 보존하고 검증된 추출 중복만
정리한다. 전체 source/run/raw와 큰 metadata 묶음은 로컬에 남고 Git의 bounded review는
부분 검토 자료다. 외부 전체 백업을 확보했다고 주장하지 않는다. [저장 정리](storage-closeout.json).

동일 모듈의 시각 수정·2ms 여유는 유지하고, 다음 [병렬 GC 비교](../m10_parallel_gc_v1/README.md)에서는
owner 직렬 GC 옵션 하나만 제거한다. 이전 기본 병렬 조건의 17–22ms 정지는 GC와의
상관관계였으므로 새 직접 계측이 필요하다. 원래 물리 5ms·HV30ms·native2/4ms,
GC61.1초·2K/D-FINE-M960·카메라10Hz·렌더러20Hz·배치·bounded boost 조건은 같다.
현재 시작 도구는 후속 후보를 선택하며 V2 실패를 덮어쓰지 않는다.

초반 가감속 후 정지 유지하는 유한 시나리오다. **5분 안정성·냉각 여유·native 인지 수용0·
전체 장면·독립 품질·각 Jetson 배포·M10 종료는 OPEN**이다.

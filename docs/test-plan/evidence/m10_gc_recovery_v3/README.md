# M10 GC recovery V3 — 30초 두 번 통과, 5분 GC 뒤 HV 만료

70% 조건에서 **30초 두 번은 PASS, 5분은60.242013606초에 원래 HV 입력 만료로 FAIL**이다.
이전 V2의 감사기 import 오류를 수정한 뒤 모든 추가 감사가 실행됐으며, 동결 감사기8개의
실제 기록 재실행도 일치했다. 물리 실패와 무결성 검사 통과는 별도 판정이다.
[원래 sequence](sequence-disposition.json) · [최종 검증](final-validation.json).

| 시험 | 물리 구간 / 정상 / INIT / 보호 | 카메라 Hz | 전체 영상 중앙 / p95 ms | 최고 CPU |
| --- | --- | --- | --- | --- |
| 30초1 | 6000 / 5838 / 162 / 0 | 9.266 | 80.497 / 86.674 | 78°C |
| 30초2 | 6000 / 5838 / 162 / 0 | 9.233 | 80.401 / 88.213 | 77°C |
| 5분 | 60000 / 11884 / 162 / 47954 | 9.233 | 80.040 / 84.443 | 89°C |

5분 영상 통계에는 보호 유지 구간이 섞여 있다. 오류 전 결과555개는 중앙80.227ms·
p95 85.999ms·최대125.022ms·100ms 초과1회이며, 이후2215개는 보호 유지 영상이다.
전체 inference2771개 중1개는 물리 구간 밖에 완료됐다. 각30초의100ms 초과는1회와4회다.
[구간별 영상](normal-300s-01/latency-phases.json).
Native eligible은 각각150010 /150010 /1500000개이며 누락·지연은 모두0이다.
이전 간헐적 누락의 영구 해결은 미확정이다. 관측 열 제한 증가0이나 냉각 여유는 OPEN이다.

첫 본 GC는17.925938ms였고, 이후 정상4프레임(12339–12342)도 GC 전 wheel/actuator
시각을 상속했다. 마지막 held HV는 source보다24.661935ms 오래된 의존 입력을 가졌고,
GC 종료12.777518ms 뒤 의존 입력 나이30.883485ms로 원래 보호가 동작했다.
본 GC는4회, 첫 증분 정리는408회·최장156.412us·완료까지2.016824초였다.
61.1초·12220프레임 주기와100us 정리 요청을 유지했다.100us는 실제 실행 상한이 아니다.

원래 admission60000개·ingress36009개와 native 출력·최초 오류가 정확히 재생된다.
실제 다음 pump(GC 종료6.955483ms 뒤)에 공개됐던 proof로 조회하면 추가 preview300us와0
모두 `native_wheel_interval`로 거절된다. 추가 여유만 더 줄여 해결된다고 볼 근거가 없다.
이 조회는 물리를 진행하지 않으며 다른 궤적의 성공을 입증하지 않는다. 실제 최종 검사→적용
최장은419.093us, admission→적용 최장은525.311us여서300us를 실측 실행 상한으로 보지 않는다.
[회복 구간](normal-300s-01/recovery-window-analysis.json) ·
[정확한 다음 pump 재생](normal-300s-01/exact-next-pump.json).

실행 조건은 owner3/image3/native1/관측1 물리 코어·SMT 분리, 병렬GC, 추가 preview300us,
2560×1536·D-FINE-M960 CUDA·카메라 목표10Hz·renderer20Hz/MaxFPS60이다.
물리5ms·native2/4ms·HV30ms·원래 source 시각·held 만료 우선·최종 물리 gate는 변경하지 않았다.
초반 가감속 뒤 정지 유지하는 유한 시나리오이며 연속 경로 주행 수용이 아니다.

원본282+281+2775=3338장과 누적 미래 품질 제외37860개를 보존했다.
원래 source/run/raw archive, 로컬 전체 metadata 및 추적 가능한 bounded review를 유지한다.
후처리 압축은 제어 종료 뒤 수행하고, 원본 tar와 독립 해제 결과의 SHA256이 일치한 뒤
원본 transport만 교체한다. 검증된 추출 중복만 [정리](storage-closeout.json)한다.
5분 renderer 종료에는23.626초가 걸렸으며10초 진단을 보존했다. 강제 종료는 없었다.
모든 물리 실행과 서버 종료는 lease 복원 전에 끝났다. lease는30분 TIME_LIMIT으로100%가
됐고 공유6파일도 복원했다. [복원](restoration-confirmation.json) · [lease](power-lease.jsonl).

사전 검사는 Python539·동결127·C++29(동일 입력 재사용)였다.1625파일 source SHA256은
`db505ed53ac956217864c5b4dcfbe277389d245bca61e043d3cdf3022195fa88`, 모듈은
`1feab7bc7a1c6788ec50fa507226ac01c99393d7b420912bba2e3cc1411a8eff`다.
[사전 프로토콜](../../perception-gc-recovery-v3-protocol.md) · [체크섬](SHA256SUMS).

후속은 동일 runtime에서 owner4/image2 배치를 비교하는
[GC owner4 V1](../m10_gc_owner4_v1/README.md)이다. GC 단축과 영상 지연을 함께 측정한다.
5분 안정성·전체 장면·native 인지 수용·독립 품질·각 Jetson 배포·M10 종료는 OPEN이다.

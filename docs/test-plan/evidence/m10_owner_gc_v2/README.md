# M10 owner GC V2 — 30초 PASS 후 30초 HV 만료

[GC V1](../m10_owner_gc_v1/README.md)은 영상 서버의 180초 기동 초과로 제어 전에 실패했다.
이번 후보는 같은 GC 모듈을 재사용하고, 시작 명령마다 별도 빈 영상 서버에서 자산을
준비한다. 준비는 최대 600초, 기존 100% 전원 설정에서 수행하며 제어 수용 시험에 포함하지
않는다. 차량·보행자·센서가 없는지 확인하고 정상 종료·공유 파일 복원 뒤 진행한다.

준비 검증 실행은 **104.676초**에 완료됐고 정상 종료·원본 파일 6개 복원을 통과했다.
[준비 결과](preparations/validation-1901827972216481/result.json).
이는 GC 성능이나 5분 안정성의 통과를 뜻하지 않는다.

[프로토콜](../../perception-owner-gc-v2-protocol.md)에 따라 Python 514개와 동결본 102개
검사가 통과했고 소스 1513개를 고정했다. [준비 결과](prepared.json),
[준비 시점 파일 검증](readiness-validation.json)의 NOT STARTED는 실행 전 기록이다.
이후 실제 준비는26.209초에 완료됐고 인증 후 다음 원래 시험을 수행했다.

| 시험 | 결과 | 정상/INIT/보호 구간 | CPU 최고 | 영상 획득→결과 중앙값/p95 |
| --- | --- | --- | --- | --- |
| 첫30초 | PASS | 5838/162/0 | 78°C | 78.98/86.18ms |
| 두 번째30초 | 28.053010185초 HV 만료 FAIL | 5445/166/389 | 79°C | 79.45/86.35ms |
| 5분 | 첫 실패로 NOT RUN | — | — | — |

영상565장과 원래 native 출력·최초 오류를 검증·재생했다. 카메라는9.27/9.30Hz,
100ms 초과 결과는1/2회다. 미래 품질 제외는20556개이며 보류 데이터는 사용하지 않았다.
두 시험 모두 owner GC가0회여서 직렬 GC 효과는 측정되지 않았다.

보유 HV 입력 나이는 **30.452587ms**: 획득 당시18.469211ms와 이후11.983376ms다.
직전 대기는 idle8.360423ms, outside최대0.565683ms, RPC최대0.133777ms였다.
6000회 원래 admission·5797회 ingress 및 모든 원래 proof byte를 재생한 결과,
긴 대기는 다음5ms와 추가4ms 여유를 함께 보장하지 못한 원래 명령의 만료에서 발생했다.
별도로 수신 전 시각으로 수신 후 검사하는 순서도 역행 시각 거절을 재현했다.
기록의 마지막 거절 이유를 전체52회 거절의 이유로 해석하지 않는다.
[첫 오류 분석](normal-30s-02/first-fault-analysis.json),
[원래 gate 재생 및 반사실적 여유 비교](normal-30s-02/admission-replay.json).

새 시료가 native에서 읽힐 때 이전 보유 시료를 먼저 만료 검사하는 순서는 유지한다.
후속 [admission window 후보](../m10_admission_window_v1/README.md)는 수신 후 시각을 읽고,
구조화 경로의 추가 준비 여유를2ms로 줄인다. 원래5ms·HV30ms 제한을 완화하지 않는다.
이전 기록에 대한50us 간격 비교는 새 live 시험의 통과를 뜻하지 않는다.

모듈 SHA `8089cd0dda69eebd5c8799f3927f91e2c0b920e6a8ad8e6da8bcdbd702eb917b`와
물리 계산·native 바이너리는 그대로다. owner GC만 단일 스레드이며 주기 61.1초,
HV 30ms·물리 5ms/320 steps·native 2/4ms·원래 시각·2K/D-FINE-M960 설정을 유지한다.
본시험 기동 제한은 180초다. 새 실행을 이 완료된 series에 덮어쓰지 않는다.

공유 파일6개와 부스트 상한100%는 OWNER_EXIT 후 복원됐다.
[마감 검증](final-validation.json), [복원 확인](restoration-confirmation.json),
[실제 lease](power-lease.jsonl). 전체 원본 run/raw는 로컬에 보존하고 Git에는 검증된
bounded review와 분석을 남긴다. 이는 외부 전체 백업을 뜻하지 않는다.
원본 tar 전체 byte를 확인한 무손실 압축과 해시 검증된 추출 중복 정리로 약5.15GB를
확보했다. [저장 정리](storage-closeout.json).

원래 HV 만료, 후반 native 누락 18건, 최고 90°C, 장기 안정성, native 인지 수용,
전체 장면·독립 품질, 각 Jetson 배포와 M10 전체는 OPEN이다.

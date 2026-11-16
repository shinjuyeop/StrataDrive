# M10 Host clock V1 — 첫30초 PASS, 후속 준비 FAIL

사용자가 실행한 제한된 관리자 helper로 Intel P-state 최대 요청만100→70%로
낮췄다. [프로토콜](../../perception-host-clock-v1-protocol.md)에 따라 실패 시 중단했고,
약496초 뒤 owner 종료에 따라100%로 자동 복원했다. 최소16%, turbo, governor,
냉각·IRQ 설정은 변경하지 않았다. 전체 장기 안정성·M10은 OPEN이다.

| 원래 실행 | 결과 |
| --- | --- |
| `normal-30s-01` | 물리6000구간, 정상5838/INIT162/보호0, native 누락·지연0; 원래 감사·정확 재생·동결 보관본 검사 PASS |
| `normal-30s-02` | native 시작 전 준비 단계 FAIL; 물리 구간0·영상0. 원래 실패를 보관본에서 재현 |
| `normal-300s-01` | 첫 실패 중단 규칙에 따라 NOT RUN |

첫 실행의 CPU 최고는76°C였고,50ms 관측에서16개 CPU 각각의 thermal counter
증가는0, 전체 코어가 동시에850MHz 이하로 보고된 샘플은0이었다. 감시 스레드
기상 지연 중앙값15.2µs, p95 20.7µs, 최대828µs다. 앞선99°C/저클럭 실패와
조건·열 이력이 같지 않으므로 부스트 제한이 문제를 해결했다고 확정하지 않는다.
[호스트 감사](normal-30s-01/host-clock-audit.json)와 [물리 감사](normal-30s-01/audit.json)를 따른다.

영상283장·추론279회, 실제 카메라 약9.30Hz다. 원래 물리 획득→결과 지연은
중앙값81.23ms / p95 88.43ms / 최대115.38ms이며100ms 초과1회다.
정상 이동701구간의 owner CPU 합 중앙값은1.247ms, 획득→게시58.2µs다.
이는 초반 가감속 후 정지 유지하는 유한 진단이며 연속 주행·인지 수용이 아니다.
[프로파일](normal-30s-01/profile-analysis.json), [같은 구간 비교](normal-30s-01/prefix-comparison.json).

두 번째 준비 호출은131.980ms로 기존100ms 기준을 넘었다. 전처리110.766ms 중
tensor 구간83.604ms, 추론20.825ms였다. 모델 준비가 관측 CPU0,8을 상속했고
OpenCV 설정도 영상 쪽의 선언값을 적용받지 않았다. wall 구간만으로 실제 계산과
스케줄 대기를 구분하지 않는다. [원래 실패 분석](normal-30s-02/preparation-failure-analysis.json).

실패 후 두 가지 정리 결함도 발견했다. 오류 메시지의 보관 위치 차이 때문에
같은 missing-file 실패를 다르게 비교했고, 이미 복원된 파일에 복원 명령을 다시
보내 엄격한 설치기가 거부했다. 원래 [sequence 결과](sequence-disposition.json)는
그대로 두었다. [사후 재현](normal-30s-02/posthoc-reproduction.json)은 경로 접두사만
정규화하여 원래 FAIL을 확인한다. [독립 복원 검사](restoration-confirmation.json)는
공유 실행 파일6개의 원래 SHA와 호스트16/100/0 복원을 확인한다.

사후 수정은 별도 소스 보관본으로 구분한다. 모델 생성·worker 생성에 선언된 영상
CPU를 적용하고 관측 호출 스레드는 복원하며, 기존 CV4/resize4 설정을 적용한다.
세 번의 실제 CUDA 준비 검사에서 기준 적용 호출은33.7–37.0ms로 통과했다.
이 검사는 원래100% cap·CARLA 없는 조건이며70% 동시 실행을 증명하지 않는다.
10초/3회/마지막2회<100ms 기준과 추론·제어 계산은 유지했다.
Python501 통과; 첫 회귀 실행의 mock fixture 오류도 별도 로그에 보존했다.
다음 별도 후보는 [Host clock V2](../m10_host_clock_v2/README.md)다.

실행 전 소스1452개, Python493, 동결77검사 PASS. 변경 없는 native의 기존207검사와
30/300초 allocation/start/stop 검사를 적용했다. 원본283장 전체 BGRA/RGB를 확인했고,
미래 품질 제외는16067개다. 원본 run/raw는 로컬에 유지하고 Git에는 소스·감사·
검토용 metadata와 SHA를 보관한다. 검증 후 압축·중복 제거 내역은
[storage-closeout](storage-closeout.json), 최종 무결성은 [final-validation](final-validation.json).

부하 없는5초 센서 진단에서 Dell fan 단일 조회는 약6.6–6.9ms였으나 감시 누락·지연은
재현되지 않았다. live 관측기는 Dell SMM을 호출하지 않는다. 이 진단은 부하 중 펌웨어
정지를 배제하지 않는다. 첫 실행 준비 중에는 짧은 보관 압축이 겹쳤으며 물리 시작
약100초 전에 종료됐다. [준비 겹침 기록](preparation-overlap.json)을 포함해 해석한다.

native 인지 수용0, 전체 장면·독립 품질·각 Jetson 배포·M10 종료는 OPEN이다.

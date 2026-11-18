# GC 이후 제어 피드백 진단

Recovery V3의 원래 실패를 같은 바이너리로 다시 재생했다. native CSV, 최초 오류,
원본 CAN/P05 proof,60000개 admission·36009개 ingress 판정이 모두 바이트 단위로
일치했다. [재생 검증](replay-verification.json), [독립 wire 해석](feedback-path.json).

첫 GC 뒤 새 wheel은 native에1ms 이내 도착했지만,10ms Actual/배분 경로에서 이전
wheel의 만료를 상속했다. 새 wheel을 담은 Actual이 공개된 때에도 명령은 GC 전
wheel+30ms+1ns에서 만료됐다. 남은1.116282ms로는 다음 물리5ms를 허용할 수 없다.
이는 원래 보호의 오동작이나 shared-memory 전달 누락을 뜻하지 않는다. 기한·시각·
제어 주기를 바꾸지 않고 GC 단축 후보를 조사했다.

별도 NullRHI 엔진에서3개 정적 actor와 원래 Town03_Opt를 사용했다. 원래61.1초 GC를
유지하고5ms SDK tick26000회를 빠르게 진행한 진단이다. ECU·renderer·모델을 동시에
돌린 실제시간 수용 시험이 아니다. 아래 수치는 **reachability 단계만**이며 memory
trim 등 전체 GC 시간과 다르다.

| 별도 진단 | 관측2회의 reachability(ms) | 결정 |
| --- | --- | --- |
| 기본3코어 | 13.230 /13.281 | 기준 |
| 4코어 | 12.709 /12.107 | 소폭 개선; 단독 해결 미확정 |
| 묶음1024 | 13.670 /13.661 | 채택하지 않음 |
| 묶음32 | 16.006 /15.582 | 채택하지 않음 |
| 새 모듈, 옵션 OFF | 13.304 /13.363 | 같은 바이너리 비교 기준 |
| 새 모듈, 영상 태그 생략 ON | 11.990 /12.434 | 실제 동시 시험 후보 |

영상 태그용 컴포넌트4373개와 dynamic material5058개의 생성이 생략됐다. 원래 의미
stencil은 그대로다. 환경 객체7795개, 경계 상자7799개, 동적 객체3개의 속성·라벨이
OFF/ON에서 정확히 일치했다. 원래 mesh/충돌 컴포넌트를 제거하지 않는다. 엔진의
`UPrimitiveComponent::GetBodySetup()` 기본값은 null이며 해당 태그 클래스는 이를
재정의하지 않아 자체 물리 body를 만들지 않는다. 이 검토와 SDK 비교를 실제 주행
수용으로 대신하지 않는다.

첫 진단은 자산 읽기 중180초를 초과해 측정0으로 중단됐다. 이후 진단은 별도600초
준비 후70%를 적용했다.05는 종료한 서버의 TIME_WAIT 때문에 측정 전에 거절됐으며
06부터 active listener는 거절하면서 TIME_WAIT를 허용하는 소켓 검사를 사용했다.
모든 실제 제한은 추가 인증 없이 적용되고100%로 복원됐다. 원래 실패도 보존했다.

[비교 결과](isolated-comparison.json), [원본 로그·source·SDK 상태 묶음](diagnostic-records.tar.gz),
[묶음 해시](diagnostic-records.json). 실제 새 시험은
[visual tags V1](../m10_visual_tags_v1/README.md)이다. M10은 아직 OPEN이다.

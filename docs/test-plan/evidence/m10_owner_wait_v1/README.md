# M10 owner wait V1 — 모델 준비 지연 재발

**첫30초 시험은 실제 제어 시작 전 모델 준비에서 FAIL**이다. 두 번째 준비 호출이
151.561ms로 기존100ms 기준을 넘었다. 그중 텐서 변환119.010ms, 추론21.156ms였다.
영상 CPU4–7,12–15와 CV4/resize4는 적용돼 있었다. 이전 배치 수정만으로 준비 지연이
해결되었다고 볼 수 없다. 물리 구간·영상0개이므로 HV 대기에 대한 새 결론은 없다.
[원래 결과](sequence-disposition.json), [실패 분석](normal-30s-01/preparation-failure-analysis.json).

별도 빌드한 owner 대기 계측 모듈과 Python504·동결88검사를 준비했지만 해당 계측은
이번 실행에서 실제 물리 구간에 도달하지 못했다. 이후30초·300초는 첫 실패 중단으로
NOT RUN이다. 원래 실패를 보관본에서 재현했고 모든 준비·오류 기록을 보존했다.
부스트 상한100%와 공유 파일6개 원본 복원도 확인했다.
[증거·복원 검증](final-validation.json), [복원](restoration-confirmation.json).

사후40회 고정 교대 비교는 CARLA 없이 원래100% 조건의 새 프로세스에서 수행했다.
기존 경로20/20·재사용 버퍼20/20 모두 준비 통과다. 마지막 두 호출의 최댓값은
37.993/34.908ms다. 실제 동시 실행의 긴 지연은 재현하지 못했으며 원인·수정 확정
근거로 해석하지 않는다. [선언과 모든 결과](preparation-study/declaration.json),
[요약](preparation-study/summary.json), [사후 코드](post-live-sources.json).

다음 [owner wait V2](../m10_owner_wait_v2/README.md)는 이미 입력값 일치 검증을 거친
텐서 재사용 버퍼를 명시적으로 적용하는 별도 후보다. 준비100ms·HV30ms는 유지한다.
기존 평균 성능 기준의 미채택 결정을 소급 변경하지 않는다. 이번 목적은 준비 지연
재발 여부와 원래 HV 대기 원인의 확인이다. 미래 제외16633개, M10 전체 OPEN이다.

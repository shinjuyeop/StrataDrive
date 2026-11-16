# M10 Host clock V2 — 수정 후보 준비

[V1](../m10_host_clock_v1/README.md)의 원래 후속 준비 실패를 보존한 별도 후보다.
모델 준비가 선언된 영상 CPU와 CV4/resize4를 사용하도록 고쳤다. 보관 위치에 따른
오류 비교와 중복 runtime 복원도 수정했다. 모델·계산·기한은 바꾸지 않는다.
[프로토콜](../../perception-host-clock-v2-protocol.md)과 [준비 결과](prepared.json)를 따른다.

Python501, 동결85검사와 세 번의 CUDA 합성 준비 검사를 확인한다. 변경 없는
native207검사·30/300초 allocation 점검은 이전 동일 바이너리 결과를 사용한다.
이는 동시 실행이나 물리 수용 결과가 아니다. 소스·runtime SHA를 동결하고,
공유 파일을 원본으로 복원한 뒤 별도 owner PID의 제한된70% lease를 기다린다.

순서는30초→30초→300초이고, 원래 감사·재생·보관본 검증이 모두 통과해야 다음으로
간다. 첫 실패에서 중단한다. V1 lease는 이미100%로 복원되어 재사용할 수 없다.
사용자의 새로운 helper 실행 전 live 상태는 **NOT STARTED**다.
native 인지·장기 안정성·각 Jetson 배포·M10은 OPEN이다.

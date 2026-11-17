# M10 Host lease 자동화 설치 확인

최초 설치 뒤 실제 사용자 권한에서 `sudo -n -k`를 사용하는 점검을 통과했다.
인증 캐시를 무시한 상태에서도 root 소유의 전용 helper를 비밀번호 없이 호출할 수 있다.
[설치 확인](installation-validation.json) · [실행 출력](installation-check.txt).

원래 helper 본문과 설치 사본의 내용·소유권·권한을 확인했다. 부스트는 점검 전후100%이며
실제70% 전환이나 물리 시험은 실행하지 않았다. 다음 시험의 안정성·GC 회복은 별도다.

[최초 준비 검증](validation.json)은 설치 전 상태의 기록으로 보존한다.15개 새 검사와
기존 lease/launcher10개 검사를 통과했다. [사용·제거 안내](../../m10-host-lease-automation.md).

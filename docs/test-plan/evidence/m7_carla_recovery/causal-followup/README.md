# 보호 요청 주입 순서 보완

2026-10-28. [앞선 실행 기록](../README.md)의 보호3회는 물리 응답 관측으로 보존하지만,
요청 인과 검증의 수용 근거에서는 제외한다. 당시 `PROTECT`를 index200의 physics receipt 뒤에
보내 native가 index199→200의 subjob을 처리할 때 소급 적용할 수 있었다.
C++ 보호 admission·M6 계약·물리 모델 결함을 이 fixture 문제와 혼동하지 않는다.

수정 후에는 index199에서 native/CARLA가 같은 frame인 상태로 `PROTECT`를 전송·flush하고,
그 뒤 physics advance를 요청한다. 요청에 pressure/torque를 넣지 않는다.
원래 request source/frame·wall 전송/advance/receipt 순서와 이후 native protection selection을
독립 검사했다. 보호 case는400구간/solver-work 모드로 제한한다.

실제 fresh server1회: **400receipt/400 EV정산,119정상·200보호·4empty INIT**, native exit0,
server SIGINT130. 마지막100구간 wheel exact0·Actual torque0/pressure1MPa와 감속을 확인했다.
`protection-audit-final.json`에 request-before-physics 검증과 시간 순서 손상4종/보호 proof 손상4종
거부가 있다. `previous-fixture-rejection.json`은 이전 fixture가 새 순서 검사에 실패함을 기록한다.
`physics-comparison.json`은 이전400구간과 generation 제외 physics가 정확히 같음을 확인한다.
그 동일성이 이전 요청 시점의 오류를 무효화하지는 않는다.

이번 변경은 Python 시험 요청/감사에 한정된다. 직전 C++ Normal/ASan 각73/73의 코드는 바뀌지 않았다.
정상 영상·종료 교착의 앞선 수용 근거도 유지한다. 새 CARLA/module 빌드는 하지 않았다.
전체 M7, wall2ms/4ms·wall fault 자동 보호 전환·차체 완전 정지 수용은 여전히 미완료다.

`suite.json`/`server-protection.json`에 실제 argv/hash/종료 결과가 있다. 실행 시 감사 source는
`sources`의 원래 이름, 이후 시간 순서 손상 시험을 추가한 감사는 `audit_m7_protection_final.py`와
`final-audit-source.json`으로 구분한다. trace/log는 원본 hash를 확인한 lossless gzip이다.
이 디렉터리의 SHA256SUMS는 후속 실행만 포함하며, 상위179개 동결 파일의 hash는 변경하지 않았다.

# 지연 권한 후보의 조건부 TSan 확인

2026-11-05, deferred-grant 후보의 native 시작 전 선언한다. 기본 기능12건과 서비스30건의
감사가 모두 통과할 때만 같은 source/binary·SDK I/O2·CPU 배치·기한으로 TSan60건을
추가 실행한다. 기본 cohort에 실패가 있으면 이 확인은 NOT RUN으로 남긴다.

Normal, ACK loss, Actual loss, StopRequest loss, Stop ACK loss, Normal+250ms signal IO를
각10회, 이 순서로10round 실행한다. 분모는60으로 고정하고 실패해도 나머지를 실행한다.
SDK 오류나 불완전 capture를 면제하지 않으며 성공할 때까지 반복하지 않는다.
실행 중 build·무거운 분석·다른 native를 겹치지 않고 감사는 전체 runtime 종료 뒤 수행한다.

원본 runtime/ordering/timing/response/DTC 감사, mutation, source/binary hash를 보존한다.
기본30건과 확인60건의 분모를 별도 보고한다. Host quiet fixture의 반복 확인이며 임의 부하,
native4ms·Target, CARLA 물리 subinterval, Clock/기동 전 incident 및 M9 전체 수용을 대신하지 않는다.

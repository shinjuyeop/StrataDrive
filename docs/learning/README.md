# 학습·실행 안내

공부할 주제와 실행 경로를 아래 네 문서로 모았다. 현재 기능·검증 수용 범위는
[프로젝트 상태](../project-status.md), CARLA 실행은 [별도 안내](../carla-guide.md)를 따른다.

| 순서 | 문서 | 이해할 핵심 |
| --- | --- | --- |
| 1 | [통신과 수신 검증](communication-guide.md) | 물리값 → bytes → P05 → receiver → SocketCAN, 세션·유효성 |
| 2 | [응답·전원·에너지 모델](vehicle-models-guide.md) | 명령/Actual·ECU/plant 분리, 보호 응답과 단일 EV 장부 |
| 3 | [주기 실행과 독립 감시](runtime-timing-guide.md) | release/deadline·누락 job·source time·CPU/FIFO·실제 관측 |
| 4 | [차량 시동·배분·종료](vehicle-lifecycle-guide.md) | Central/Zone/Leaf, 8-role INIT·권한·전원·정상 stop·재가입 |

정상 지연·rate 제한과 jam을 구분하는 [조향 응답 학습](steering-response.md)과
[인터랙티브 그래프](steering-response.html)도 유지한다. 그래프의 가상 계수를 calibration으로 채택하지 않는다.

개념 → 코드 → 실행 → 정상/고장 결과 → 한계 순서로 확인한다.
“왜 이 owner가 판단하는가”, “어떤 시각의 값인가”, “어떤 관측이면 실패인가”를 직접 설명한다.
자동 시험 통과와 학습자 이해 확인은 별도다. 작은 작업에 필요한 개념부터 공부한다.

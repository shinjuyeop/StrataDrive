# M10 owner GC V2 — 실행 직전 자산 준비

[GC V1](../m10_owner_gc_v1/README.md)은 영상 서버의 180초 기동 초과로 제어 전에 실패했다.
이번 후보는 같은 GC 모듈을 재사용하고, 시작 명령마다 별도 빈 영상 서버에서 자산을
준비한다. 준비는 최대 600초, 기존 100% 전원 설정에서 수행하며 제어 수용 시험에 포함하지
않는다. 차량·보행자·센서가 없는지 확인하고 정상 종료·공유 파일 복원 뒤 진행한다.

준비 검증 실행은 **104.676초**에 완료됐고 정상 종료·원본 파일 6개 복원을 통과했다.
[준비 결과](preparations/validation-1901827972216481/result.json).
이는 GC 성능이나 5분 안정성의 통과를 뜻하지 않는다.

준비 후 sudo 인증을 마치면 새 PID에 기존 70% 보조 도구를 연결한다. 인증 지연으로
준비가 5분보다 오래되면 실행기·부스트를 시작하지 않고 중단한다. 이후
30초→30초→5분의 원래 검사를 수행하며 첫 실패에 중단한다.

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc.py
```

[프로토콜](../../perception-owner-gc-v2-protocol.md)에 따라 Python 514개와 동결본 102개
검사가 통과했고 소스 1513개를 고정했다. [준비 결과](prepared.json),
[최종 파일 검증](readiness-validation.json). 실제 제어 시험은 NOT STARTED다. 이전 V1의 준비 동결본이나
실패 기록을 덮어쓰지 않는다.

모듈 SHA `8089cd0dda69eebd5c8799f3927f91e2c0b920e6a8ad8e6da8bcdbd702eb917b`와
물리 계산·native 바이너리는 그대로다. owner GC만 단일 스레드이며 주기 61.1초,
HV 30ms·물리 5ms/320 steps·native 2/4ms·원래 시각·2K/D-FINE-M960 설정을 유지한다.
본시험 기동 제한은 180초다. 미래 품질 제외는 19991개에서 이어간다.

원래 HV 만료, 후반 native 누락 18건, 최고 90°C, 장기 안정성, native 인지 수용,
전체 장면·독립 품질, 각 Jetson 배포와 M10 전체는 OPEN이다.

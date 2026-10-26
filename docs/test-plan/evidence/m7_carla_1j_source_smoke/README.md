# M7-1j 후속 — source 서버 실행 검증

2026-10-26 KST. **비렌더링 연결/ego/논리 tick만 한정 통과, 렌더링 경로 FAIL/OPEN**.
같은 source build의 기본 기능을 실행했다. 정상 CARLA 주행·NoDrive 서버 포트·RGB/GT·
native ECU 연동·energy fidelity 수용은 아니다. 기존 M6 코드·계약·수치·판정은 유지한다.

## 실제 실행 결과

| 실행 | 조건 | 관측/판정 |
| --- | --- | --- |
| Server01 | Town10HD_Opt, Low, RenderOffScreen | 첫1800s 준비 한도 초과. 연결/ego 시험 NOT RUN. 같은 프로세스 추가 관찰 중에도 캐시 생성 지속. SIGINT 요청 후에도 초기화가 진행돼 SIGKILL로 정리(exit−9), 총2901.166s. 정상 종료나 OOM으로 분류하지 않음 |
| Server02 | Town03_Opt, Low, RenderOffScreen, 공유 캐시 일부 재사용 | LoadMap920.019s 이후 렌더링 시작(frame2)에 SIGSEGV(exit−11). ego 시험 미완료. [크래시 스택](attempt02-crash.txt) |
| Server03 / Client03 | Town03_Opt, 시작 INI DisableRendering=True | world 조회 준비62.183s, Client/Server identity 일치. 시험 코드가 시작 INI와 Episode 읽기값을 동일하게 가정해 FAIL. ego 시험 NOT RUN. [실패](attempt03/result.json), [당시 코드](harness-attempt03.py) |
| Server03 / Client04 | 같은 서버, 수정한 harness가 Episode no_rendering_mode=True를 명시 적용 | 정상/주입 예외 lifecycle **2/2 PASS**, 본 tick 관측102개. [결과](attempt04/result.json), [원본 CSV](attempt04/ticks.csv) |
| 독립 CSV 검사 | 저장된 JSON/CSV 재검사 | [oracle](audit-attempt04.json)26개 조건 일치. 독립 runtime TC26개라는 뜻은 아님 |
| Server03 종료 | ego 제거·Episode 설정 복원 후 SIGINT | exit130, SDL/engine teardown 관측, 강제 종료 없이 포트2200/2201/2202 및 소유 process group 정리. **exit0으로 기록하지 않음**. [정리](cleanup.json) |

서버 실행의 서로 다른 실패와 Client 시험 결과를 합쳐 전체 PASS로 만들지 않았다.
Server03은 앞선 실행에서 만들어진 공유 캐시를 재사용했다. map/캐시/준비 방법이 달라
시작 시간의 맵별 성능 비교나 차가운 시작 시간 수용으로 사용하지 않는다.
첫30분은 이 실행의 관찰 한도이며 기존 ECU deadline/freshness를 바꾼 값이 아니다.

## 확인한 범위

- UE4.26.2/CARLA0.9.16 source commit·실행 파일·wheel·서버 모듈 hash가 이전 빌드와 일치했다.
  [preflight](preflight.json), [manifest](manifest.json)에 identity/원본 외부 로그 경로/hash를 둔다.
  Client/Server 실제 version은 모두 **294096e-dirty**다.0.9.16으로 재명명하지 않았다.
- mkz_2020 ego 두 개를 차례로 생성하고 physics disable을 요청했다. 정상/주입 예외 양쪽에서
  destroy 반환·현재 actor registry·snapshot의 부재를 확인했다. 남은 vehicle은0이다.
- 새로운 ego는 Traffic Manager에 등록하지 않는다. upstream0.9.16은
  `Vehicle::SetAutopilot(false)`도 TM 인스턴스를 만들 수 있으므로 그 API를 호출하지 않았다.
  기본 autopilot=false와 별도 전용 서버 조건을 사용한다. 외부 writer를 서버가 인증/봉쇄했다는 뜻은 아니다.
- 본 관측은 정상100+예외2샘플, 정리 tick2개는 별도다. frame/snapshot 일치·연속성과
  원래 simulation elapsed/delta를 검사했다. 증가량은0.009999999776482582s였다.
  float 표현 확인용 tolerance1µs를 사용했으며 source age30ms나 native2ms/4ms guard의 완화가 아니다.
- Episode API의 synchronous/fixed delta/substep/rendering 설정을 읽기값으로 확인하고 원래 값으로
  복원했다. 정상 본 관측의 최대 wall tick은12.990848ms이며 실제 ECU wall 수용 시험은 NOT RUN이다.
- 시작 `UCarlaSettings.DisableRendering`과 `FEpisodeSettings.no_rendering_mode`는0.9.16에서
  별도 값이다. 시작 로그는 Rendering=Disabled지만 초기 Episode 읽기값은false였다.
  이 차이를 이유로 실패한 Client03을 보존하고, Client04에서는 시험 중 모드를 명시 적용했다.
  수정 후 Episode는 false→true→false로 복원했다. 전체 renderer 내부 상태 복원이나 RGB 검증을 주장하지 않는다.

## 실패와 남은 제한

렌더링 실패 스택은 `FDistanceFieldVolumeTexture::IsValidDistanceFieldVolume` →
`FPrimitiveSceneShaderData` → GPUScene/DeferredShading 경로다. fault address는0x2c다.
원인은 아직 확정하지 않았다. 엔진 null 검사 추가나 distance field 설정 변경으로 실패를 감추지
않았고, engine/physics 소스도 수정하지 않았다. 비렌더링 시험의 성공은 이 FAIL을 닫지 않는다.

Server01에서 초기화 중 반복 TCP/Client 준비 조회가 listen backlog를 누적시킨 관측도 있었다.
추가 관찰의 시간은 순수한 cold/map 성능 값이 아니다. Server02부터는 LoadMap 완료 로그를
수동적으로 기다리고 하나의 persistent Client로 조회했다. 준비 worker의 서버 종료 감지 누락은
Server02에서 수동 정리한 뒤 Server03에서 양쪽 단계에 검사하도록 수정했다.

메모리 압박 중 시스템 가용 메모리 약2.8GiB를 관측했다(연속 peak 계측 아님).
Server01에만 OOM 우선순위500을 적용해 자원 부족 시 해당 전용 서버가 우선 대상이 되도록 했고,
그 프로세스 종료로 설정도 사라졌다([기록](containment.json)). 실제 exit−9는 수동 SIGKILL이다.
보행자 애니메이션 등 누락 asset 경고를 manifest에 보존한다. 보행자/전체 content 적합성은 미검증이다.
과거 package의 native reload/종료139 OPEN은 별도 build/조건이며 이번 결과로 해소하지 않는다.

## 재현과 다음 작업

[CarlaSettings-attempt03.ini](CarlaSettings-attempt03.ini)를 별도 파일로 지정한 source 서버를
[server-attempt03.json](server-attempt03.json)의 명령으로 실행한다. 파괴적 캐시 삭제는 재현 절차에 포함하지 않는다.

```bash
/d/shin/stratadrive-tools/m7-source/carla-build-venv/bin/python \
  tests/integration/carla/m7_1j_source_smoke.py \
  --port 2200 --expected-version 294096e-dirty --expected-map Town03_Opt \
  --no-rendering --output /tmp/m7-source-new-attempt
python3 tests/integration/carla/audit_m7_1j_source_smoke.py \
  docs/test-plan/evidence/m7_carla_1j_source_smoke/attempt04
```

출력 directory는 새 경로만 허용하며 이전 실패/CSV를 덮어쓰지 않는다.
파일 무결성은 SHA256SUMS, 코드/원본 log identity는 manifest에 둔다.
다음 작은 작업은 distance field 렌더링 crash의 원인·재현 조건 조사와 렌더링 가능한 baseline 확보다.
기본 기능 시험은 비렌더링 범위에서만 사용할 수 있다. 이후 NoDrive 단일 writer/frame 포트,
실제 geometry/brake calibration·raw wheel validity·interval work를 구현/검증해야 한다.

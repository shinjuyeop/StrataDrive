# 개발·검증·문서 관리 정책

현재 상태는 [프로젝트 상태](project-status.md), 단계·미결정 값은 [로드맵](roadmap.md),
실행 결과는 각 [evidence](test-plan/README.md)에 둔다. 이 문서에 실행 이력을 누적하지 않는다.

## 작업과 학습 순서

작은 단위로 개념 → 요구 → 설계 → 구현 → diff review → 실행 → fault/edge 검사 →
결과·한계 기록 → 수용 판단을 진행한다. **작성된 코드를 학습자가 설명할 수 없다면 학습 완료로 세지 않는다.**
기술 시험 통과와 개인 이해 review를 구분하고 선행 공부는 현재 작업에 필요한 범위로 좁힌다.

Requirement → component → interface → test → result를 연결한다.
미결정 값은 담당 분야·결정 시점을 가진 TBD로 남긴다. 수치를 바꾸면 이전/새 값·이유·
영향 requirement/ICD/profile/scenario·재검증 범위를 함께 기록한다. 결과를 본 뒤 허용 오차를 늘리지 않는다.

## 코드·도구·검증

- 재사용 기능은 해당 도메인 모듈, ECU 판단은 `vecu/`, 물리 모델은 `simulation/`에 둔다.
- 예제는 `actuator_demo` 하나와 `tools/demo/`로 모은다. 기존 모듈의 작은 변경은 기존 test case로 확장한다.
- Compiler warning, GoogleTest, clang-tidy/cppcheck, ASan/UBSan과 필요한 TSan 경계를 사용한다.
  일부 source/경계 통과를 전체 SDK·Target 수용으로 올리지 않는다.
- Command·Actual·권한·ACK·물리 완료, simulation time·wall time, 기능·성능·sanitizer 결과를 구분한다.
- Scenario/config/seed·source/binary/tool version·입출력·분모·실패/timeout·정리 결과를 보존한다.
  실패를 성공 분모에서 빼거나 과거 통과를 이번 재실행으로 표시하지 않는다.
- 부하·scheduler/priority·CPU 배치의 요청값과 실제값을 확인한다. 설정 실패는 gate를 열지 않는다.
  Missed job을 늦게 재생해서 완료 분모를 채우지 않는다.

기본 검사와 sanitizer 빌드는 저장소 루트에서 실행한다.

```sh
cmake -S . -B build/m1-angle -DCMAKE_BUILD_TYPE=Debug
cmake --build build/m1-angle --parallel 2
ctest --test-dir build/m1-angle --output-on-failure
cmake -S . -B build/m1-angle-sanitized -DCMAKE_BUILD_TYPE=Debug -DSTRATADRIVE_SANITIZERS=ON
cmake --build build/m1-angle-sanitized --parallel 2
ctest --test-dir build/m1-angle-sanitized --output-on-failure
```

정적 분석은 현재 compilation database의 include/define과 변경 production/demo source를 사용한다.
Dispatcher만 검사하고 도메인 구현 전체를 검사했다고 표시하지 않는다.
`BUILD_TESTING=OFF`는 library/예제만 빌드하고 단위·통합 TX/RX target을 제외한다.
세부 TC·모델 동등성·결과 형식은 [검증 전략](test-plan/verification-strategy.md)에 있다.

## 표준과 개발 방법의 적용 범위

| 활동 | 현재 방향과 후속 범위 |
| --- | --- |
| AUTOSAR Classic / Methodology | Leaf SWC/Port/Interface/Runnable/Event와 ECU/OS Task mapping을 Steering부터 학습. ECU/plant 분리·Host POSIX OS 파일럿은 구현했지만 전체 release/stack·RTE/BSW·Target 채택은 미결정 |
| Automotive SPICE 4.0 | 요구·설계·검증의 추적성/변경 영향/review에 참고. 전체 process 적용·평가 등급을 주장하지 않음 |
| ISO 26262 | [Item Definition/HARA 학습 초안](safety/concept-study.md)에서 가정·Goal 후보·열린 질문을 검토. ASIL/FTTI/safe state는 임의 확정하지 않음 |
| ISO 21448 / SOTIF | M10–M11 인식·판단 한계, triggering condition·scenario coverage·fallback 검토 계획 |
| MBD | M6 독립 Python/binary64 종방향 MIL 완료. M8 모델/C++ 공통 vector 동등성·차량 성능은 별도 판정. 자동 생성은 선택 후속 |

제한된 ODD에서 운전자 개입에 의존하지 않는 자동 주행 SIL을 학습한다.
운전자 인계를 fault 대응의 전제로 넣지 않는다. 이 방향과 component PASS는 Level4·
전체 AUTOSAR·표준 적합성·실차 안전 인증을 뜻하지 않는다.

Classic 도구 도입 전 release/schema·license·Host/Target 지원·생성/재생성·adapter·build·실행 I/O를
확인한다. 직접 작성한 코드·생성 코드·third-party를 구분한다. OS Task와 Runnable,
RTE와 BSW, AUTOSAR 생성과 제어 알고리즘 생성을 같은 것으로 취급하지 않는다.
호환 도구를 확보하지 못하면 보류 근거를 기록하고 기존 Linux vECU를 적용 완료로 표시하지 않는다.

## 문서 관리

| 정보 | 한 곳에서 관리할 위치 |
| --- | --- |
| 처음 읽을 안내·core build | 루트 README와 `docs/README.md` |
| 현재 구현·수용·OPEN·다음 작업 | `project-status.md` |
| 후속 milestone·TBD | `roadmap.md` |
| 규범 수치·메시지/모델 계약 | `requirements/`, `interfaces/` |
| 실행·해석하는 방법 | `carla-guide.md`, `learning/` |
| 실행 원본·당시 분모/실패·무결성 | `test-plan/evidence/` |
| 과거 결정·검토·프로토콜 | `archive/` |

중복 요약과 날짜별 경과를 여러 문서에 덧붙이지 않는다. 현재 안내에서 끝난 계획과
다음 단계 예고는 지우고, 결정 근거가 필요한 이력만 archive/evidence로 연결한다.
새 결정은 [ADR 보관 문서](archive/design-decisions.md)에 다음 ID로 추가하고 현재 계약에 반영한다.
이동·통합 시 상대 링크·앵커·runner가 읽는 protocol 경로를 함께 점검한다.
새 안내를 쓰기 위해 기존 raw evidence·source snapshot·기록된 timestamp/hash를 고쳐 쓰지 않는다.

## 문서 이름 규칙

- 폴더 안내는 `README.md`, 그 외 문서·학습 HTML·추적성 CSV는 소문자 영어 `kebab-case`로 쓴다.
- 이름은 주제와 용도를 드러낸다. 예: `project-status.md`, `carla-guide.md`, `steering-frame.md`.
- 실행·학습 안내는 `*-guide.md`, 요구사항은 `*-requirements.md`, 시험 프로토콜은 `*-protocol.md`를 사용한다.
- 폴더가 의미를 설명하면 파일명에서 반복하지 않는다. `interfaces/`에서는 `can.md`, `bms-frame.md`처럼 쓴다.
- `draft`, `final`, `latest`와 현재 milestone을 일반 문서명에 붙이지 않는다. 상태·버전은 본문에서 관리한다.
- 고정 시험 ID·버전이 필요한 보관 프로토콜과 원본 evidence 파일명·앵커는 기존 식별자를 유지한다.

# M9 이후 문서·진단 코드 정리

2026-11-06, 기준 commit `3d685f6`.
현재 안내와 과거 이력을 정리하고, 반복 구현을 공통화했다. 검출·보호·원래 source/expiry·
저장·qualified 복구·명시적 clear 규칙과 기존 raw evidence·고정 protocol은 유지한다.

## 정리한 구조

- 현재 상태는 `docs/project-status.md`, 후속 단계·TBD는 `docs/roadmap.md`에서 관리한다.
  M7–M9의 긴 진행 경과와 과거 실행 목차는 [구현·검증 이력](../../../archive/implementation-history.md)에
  모았다. README·진단 계약·추적성의 오래된 미실행 안내와 ADR104개 목차·누락 앵커를 갱신했다.
- `DiagnosticPublisher`가 공통 dictionary·context·이벤트 번호·유한 큐 발행·sticky 기록 상태와
  Clock 복구 발행을 소유한다. Control/Owner/Native/Startup은 각 감시기의 검출·보호·복구
  predicate와 세션 대조를 유지한다. 숫자 ID·예외 메시지·Control 고유의 번호 고갈 사유와
  원래 발행 순서를 보존한다. 공통 발행기에 파일 IO·actuator 변경·새 allocation을 넣지 않는다.
- Owner/Native/Startup의 Control adapter 간접 의존을 제거하고, 실제 Control 객체를 쓰는
  native 조합부에 직접 include했다. 쓰지 않는 native 인수와 include도 제거했다.
- Python 공통 decoder가 이미 읽던 전체 related ID를 반환한다. CARLA의 중복 재파싱 wrapper를
  지웠으며 서로 다른 발행자의 사건은 전체 ID와 occurrence로 계속 연결한다.

## 최종 검증

| 검사 | 실제 결과·범위 |
| --- | --- |
| Debug CTest | 1450/1450; unit1098·논리 통합347·전송5. Wall 성능 수용과 구분 |
| ASan·UBSan | 189/189, 관련15 targets |
| TSan | 189/189, 같은15 targets; `setarch x86_64 -R` |
| Python | CARLA evidence4/4·서비스 판정12/12 |
| 기존 trace 재현 | 4/4, native 관측24004개·기존 decoder 이벤트68개 정확히 동일 |
| Native 3-ECU | 3/3: 정상 성공1·예상 고장 거절2, 각4개 독립 감사·변조 검사 통과 |
| 정적 검사 | 변경4 TU의 clang-tidy와 cppcheck 통과; 최종 프로젝트 진단0 |
| 문서·추적성 | 13개 문서·788개 링크/앵커 오류0; CSV261개 고유 ID와 변경 함수 경로 확인 |

새 경계 테스트2개는 번호 고갈 시 Gap 기록 후 재발행/번호 순환 금지, Clock 기록 용량 초과 시
원래33개 고장과 Gap 보존 및 불완전 상태의 복구 발행 금지를 확인한다. 기존 물리 반응·
세션·clear·동시성 assertion을 약화하지 않는다.

Release replay는 기존 M9 CARLA 네 trace의 native 관측24004개를 전체 canonical JSON byte로
비교했다. Encoded 진단 byte도 포함하며, 원래 이벤트68개는 기존 decoder와 CARLA 전체 related-ID
wrapper의 조합과 정확히 같다. **과거 physics 입력의 재현이며 새 CARLA 서버 실행4회가 아니다.**
원래 physics/work·차량 응답·서버 종료 근거는 [M9 마감](../m9_followup/README.md)에 있다.

재빌드한 native 서비스는 동일한 명시적 owner/aux 분리·SDK FIFO1 profile로 정상1건과
진단 ACK 누락·Stop ACK 누락 각1건을 고정 실행한다. 정상 성공과 고장의 예상 거절을 구분하고
기존 독립 감사4개와 변조 검사를 적용한다. 실제 wall runtime 중 build·sanitizer·정적 분석·
replay·압축을 병행하지 않는다. 이전 부하7/7·서비스18/18을 이번 재실행 결과로 세지 않는다.
전체 wall/SDK sanitizer·Target·무제한 보존의 별도 경계는 유지한다.

## 중간 시도 보존

초기 기계적 치환이 `healthy_mask`와 인수 호출에 영향을 주어 컴파일러가 잡은 로그를 보존한다.
초기 wrapper의 불필요한 Event 복사는 cppcheck의 `passedByValue`3건으로 검출했다.
최종 wrapper는 const reference로 넘기고 공통 발행기에서 한 번 복사한다. 최초 정적 검사·
by-value header snapshot과 최종 결과를 분리한다. 최종 수정 전 sanitizer/replay 결과는
별도 보존하며 최종 통과 분모로 사용하지 않는다. 대기 중이던 native smoke는 실행 시작 전에
중단해 최종 sanitizer 재빌드·검증과 실제 wall runtime의 겹침을 피했다.

## 원본과 재현

- `acceptance.json`: 실제 검사 수·명령·결과·범위와 바이너리 ID.
- `sources.json`, `sources.tar.gz`: 변경 구현14개의 경로·SHA256와 snapshot.
- `validation.tar.gz`: 빌드·검사 XML/stdout·정적 검사·재현 script·소스/바이너리 ID와 중간 실패.
  `asan-final.json`/`tsan-final.json`이 최종 결과다. `sanitizers.json`은 수정 전의 중단된 시도다.
- `native-smoke.tar.gz`: 세 사례의 원본 runtime·journal·CSV·log와 독립 감사.
  내부 `native/protocol.json`과 `native/results.json`에 profile·argv·실제 결과가 있다.

원래 M9 LFS trace를 받은 뒤 보관 `replay.py`와 기록한 Release build로 동일성을 확인한다.
다른 검사는 manifest의 build 옵션·도구 버전과 각 결과의 명령을 따른다. 보관된 실행 당시 경로를
새 output directory로 바꾸고 원본을 덮어쓰지 않는다. PID 대기/중단이 들어간 초기 조정 script는
당시 실행 기록이며 일반 재실행 절차가 아니다. 무결성은 이 디렉터리에서 확인한다.

```sh
sha256sum -c SHA256SUMS
```

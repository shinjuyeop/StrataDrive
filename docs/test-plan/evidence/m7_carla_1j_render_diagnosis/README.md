# M7-1j 후속 — 렌더링 SIGSEGV 조사

2026-10-26 KST. **영상 수신은 한정 확인했으며 렌더링 crash는 OPEN이다.**
이전 source smoke와 같은 UE/CARLA 바이너리로 조사했다. 엔진 수정·재빌드·driver 변경·
캐시 삭제·distance field 비활성화는 하지 않았다. M6 코드/계약/수치/판정도 유지한다.

## 실제 실행

모두 Town03_Opt/Low/RenderOffScreen, 별도 Python 환경, Client/Server identity
`294096e-dirty`다. 공유 캐시는 실행마다 일부 누적됐고 동일한 cold 조건 비교가 아니다.

| 실행 | 관측 | 판정/한계 |
| --- | --- | --- |
| GDB01 | Vulkan 초기화 중 기존 vendor ensure의 SIGTRAP에 debugger 정지 | 원래 SIGSEGV가 아님. debugger quit으로 inferior 정리, ego/camera NOT RUN |
| GDB02 lifecycle | 렌더링 허용 상태에서 physics-disabled ego 정상/주입 예외2/2, 본 tick102개 | [결과](gdb-lifecycle/result.json). 이후 같은 서버의 camera 시험과 구분 |
| GDB02 camera | RGB/GT 부착 후 SceneCapture→GPUScene→Distance Field 경로 SIGSEGV | [Client FAIL](gdb-render-probe/result.json), [stack/register](gdb02-crash-stack.txt). RPC timeout·actor API 정리 실패 보존. debugger가 멈춘 서버는 quit으로 종료 |
| GDB03 camera | 150tick, RGB/GT30쌍·원래 frame/timestamp 일치, actor3개 제거·설정 복원 | [결과](gdb-render-probe02/result.json), [저장 metadata 검사](audit-gdb-render-probe02.json). SIGINT 후 inferior exit130, GDB exit0과 구분 |
| Native01 camera1 | debugger 없이150tick, RGB/GT30쌍·정리/복원 | [결과](native01-probe1/result.json), [검사](audit-native01-probe1.json) |
| Native01 camera2 | 같은 native 서버에서 다시150tick, RGB/GT30쌍·정리/복원 | [결과](native01-probe2/result.json), [검사](audit-native01-probe2.json). 별도 서버 반복은 아님 |

GDB02/03은 기존 handled ensure의 SIGTRAP만 debugger가 넘기고 SIGSEGV에는 정지하도록 했다.
GDB exit0을 서버 성공/정상 종료로 해석하지 않는다. Native01 supervisor tool session은
exit143으로 끝났고 원인은 미확정이다. 서버가 PID1에 재부모화된 채 살아 있음을 확인한 뒤
camera2를 직접 실행했다. 마지막 SIGINT 후 engine 로그는 종료 코드130을 요청했으나
wait status는 확보하지 못했다. 이를 서버 exit130/0 PASS로 기록하지 않는다.
[정리 관측](cleanup.json): 서버·ShaderCompileWorker·포트2200/2201/2202 모두 남지 않았다.

## 확인한 충돌 지점과 미확정 원인

[GDB02 관측](crash-observation.json)에서 texture `this=0x7ffe64861350`의 내부
`VolumeData` 참조 값은 **0x0100000400000000**이었다. CPU가 이 주소를 통해 Size를 읽다가
정지했다. 이전 native smoke의 fault address0x2c와 주소는 다르지만 같은 Distance Field 경로다.
참조가 유효하지 않다는 관측과, 그 참조가 왜 잘못됐는지는 구분한다.

고정한 UE fork의 local source를 확인했다. static mesh proxy는 LOD0 DistanceFieldData
포인터를 캐시하며, HasDistanceFieldRepresentation에는 이미 null 검사가 있다.
async distance field 교체에는 render-state 재생성·기존 자원 deferred cleanup이 있고,
재생성 context에는 detach 명령 FlushRenderingCommands도 이미 있다.
따라서 단순 null 검사나 무조건 flush 추가를 근거 있는 수정으로 확정할 수 없다.

**객체 수명/use-after-free 또는 다른 메모리 손상은 가설이다.** 실패 시 cached pointer와
live LOD pointer, 해당 mesh, 할당/해제 stack을 동시에 확보하지 못했다. 소유권 비교를
추가한 GDB03에서는 crash가 재현되지 않았다. 캐시 준비나 debugger 타이밍이 원인/해결책이라는
인과도 입증하지 않았다. GPU driver 결함으로 확정할 근거 역시 없다.

동일 stack의 [공식 CARLA issue #9522](https://github.com/carla-simulator/carla/issues/9522)가
열려 있었고 조회 시 채택된 수정은 없었다. 같은 root cause라는 증거는 아니다.
외부 원본 log 경로/hash와 local commit·실행 파일 identity는 [manifest](manifest.json)에 둔다.
비공개 엔진 source 본문과 전체 debugger log는 repository에 복사하지 않았다.

## 영상 수신 결과의 범위

probe는 world10ms·camera50ms 요청, RGB/학습·평가용 GT320×240/FOV90°, physics-disabled ego다.
정상 주행/AI/Traffic Manager/native ECU·Actual actuation은 연결하지 않았다.
각 성공 실행의150tick에서30쌍을 관측했고 source timestamp를 snapshot과 직접 비교했다.
첫 간격은6frame(60ms), 이후5frame(50ms)이다. timestamp를 바꾸지 않았다.
이는 최소10쌍 수신 진단이며 **완전한20Hz delivery/startup 수용이나 기존 freshness 완화가 아니다**.
저장 metadata의 별도 검사는 각16조건을 확인하며 독립 runtime TC16개라는 뜻은 아니다.

[RGB 예시](native01-probe1/first-rgb.png)는 도로 영상을 담지만 건물에 체크무늬 재질이 보인다.
server log에도 shader compile/async distance field 작업이 계속된다. 전체 재질·content 준비,
영상 품질·학습 dataset 적합성은 미검증이다. GT 원본은 진단 전용으로 분리했다.
현재 결과를 렌더러 안정성·pause/reset·정상 주행·native wall deadline 수용으로 확대하지 않는다.

## 다음 작은 작업

1. 실패 시 proxy cached/live LOD 주소·mesh identity와 자원 할당/해제 순서를 함께 남기는
   제한된 debugger 계측으로 수명 문제 가설을 검증한다. 유효하지 않은 주소를 건너뛰는 guard는 넣지 않는다.
2. asset/shader/distance field 준비 완료를 확인한 조건을 별도로 만들고 새 native 서버에서
   RGB/GT를 반복 수집한다. 준비 전 실패와 분리하며 완성된 재질과 원래 timestamp/delivery를 확인한다.
3. 원인이 입증되면 최소 engine 수정·binary hash를 별도로 남겨 native 회귀 검증한다.
   source 안정화 후 NoDrive 단일 writer/frame 포트·brake calibration·Actual receipt로 진행한다.

재현 시 [gdb03-process.json](gdb03-process.json)의 server_argv로 전용 서버를 실행하고 다음을 사용한다.
출력 directory는 새 경로여야 한다. 서버가 렌더링·map 준비 중에도 RPC가 열릴 수 있으므로
반복 연결 대신 LoadMap 로그를 수동적으로 관찰한다. 이것만으로 asset 준비 완료를 뜻하지 않는다.

```bash
/d/shin/stratadrive-tools/m7-source/carla-build-venv/bin/python \
  tests/integration/carla/m7_1j_render_probe.py \
  --expected-version 294096e-dirty --output /tmp/m7-render-new-attempt
python3 tests/integration/carla/audit_m7_1j_render_probe.py /tmp/m7-render-new-attempt
```

SHA256SUMS는 이 묶음의 파일 무결성용이다. 과거 evidence/FAIL을 수정하거나 합산하지 않았다.

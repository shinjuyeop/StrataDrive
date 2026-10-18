# ADR-0041: ARM64 RTOS 교차 빌드와 Host RT 사전 점검

Date: 2026-10-18. Status: **빌드·점검 도구 구현 / Target 실행·RT timing 수용 후속**.

## 결정

[ADR-0040](ADR-0040-steering-rtos-pilot-and-delay-observation.md)의 Steering 파일럿을 다른 Leaf로 확대하기 전에
ARM64 Linux 빌드 가능성과 Host의 RT 시험 권한을 확인한다. Central/Zone/Leaf 배포 계획과 기존 M3 시한은 유지한다.

`tools/build_rtos_pilot.py --architecture aarch64`가 GNU Linux 교차 toolchain으로 기존 C++ library·외부 plant,
Trampoline POSIX OS·ViPer를 빌드한다. GOIL은 생성 작업을 수행하는 **Host 도구**, 나머지 세 실행 파일은
**대상 CPU용 코드**다. OIL의 compiler/assembler/linker를 같은 대상으로 지정한다. Native와 ARM64의 CMake
directory 및 ViPer object/output directory를 분리하고 upstream source는 수정하지 않는다.

일반 build의 다운로드·RTOS 옵션 정책은 유지한다. Toolchain을 자동 설치하지 않는다. 고정 upstream revision,
compiler target/sysroot·source/도구/실행 파일 hash·ELF machine·동적 loader/필요 library/symbol version을 `build.json`에 남긴다.
빌드 실패 후 이전 성공 manifest가 남지 않게 한다. 기존 CMake compiler 또는 output architecture가 다른 directory의
재사용을 거부한다. 실행기는 세 실행 파일의 실제 ELF architecture와 hash를 먼저 확인한 뒤 output/vCAN을 만든다.
다른 CPU용 파일을 실행 실패나 에뮬레이터 실행으로 우회해 native timing 표본에 넣지 않는다.

## 빌드와 실행의 구분

ARM64 ELF가 만들어져도 Jetson 지원 판정은 아니다. 현재 toolchain은 일반 GNU/Linux 환경이며 보드별 JetPack/BSP의
sysroot로 확정한 것이 아니다. 실제 loader·glibc/libstdc++ version, POSIX signal/별도 stack 전환,
ViPer fork/IPC, SocketCAN/vCAN와 권한을 선택한 보드에서 검사해야 한다. CAN transceiver/driver와 물리 CAN FD
시험은 별도다. QEMU 실행도 실제 보드의 지연 근거로 사용하지 않는다.

파일럿의 10 ms relative timer, 49152-byte task/32768-byte ISR stack, hosted C의 fortify 예외는 유지한다.
교차 컴파일은 stack 여유·실시간성·AUTOSAR 적합성을 검증하지 않는다. 새 보드에서 fortified longjmp 및 stack/ABI
호환성을 다시 확인한다. RTE/BSW와 session coordinator도 후속이다.

## RT 사전 점검

새 실행 파일 대신 기존 `tools/runtime_diagnostics.py`에 `--probe-only`를 추가한다.
M3 workload/vCAN/부하 worker 없이 kernel config, CPU mask, RT priority limit, RT throttling, trace/perf 접근 결과를 기록한다.
FIFO 요청은 별도 자식에서만 잠깐 적용하고 관측·복원한 뒤 종료한다. 부모의 scheduler는 유지한다.
기본 요청 priority는 1이다. `--fifo-priority`는 **권한 확인용**이며 runtime owner별 priority 설정이 아니다.
Probe timeout은 3초이며 syscall errno와 원래 오류를 보존한다. 시스템 설정/권한을 자동 변경하지 않는다.

`PREEMPT_DYNAMIC`과 `PREEMPT_RT`, FIFO 적용 가능 여부, trace 접근 가능 여부를 별도 항목으로 기록한다.
Config를 못 읽으면 RT 여부는 unknown이다. FIFO가 AVAILABLE이어도 M3 workload를 RT로 실행한 결과나 deadline
충족을 뜻하지 않는다. 권한 거부는 BLOCKED로 기록하고 SCHED_OTHER 표본을 RT 결과로 대체하지 않는다.
사전 점검 명령의 exit 0은 **보고서 수집 성공**이며 RT 사용 가능 판정이 아니다.

## 다음 수용 조건

1. 선택한 ARM64 보드의 OS/BSP·compiler/sysroot를 고정하고 동일한 기능 4조건과 IPC 정리를 재현한다.
2. RT 시험이 가능한 환경에서 native M3 owner별 policy/priority를 명시하고 실제 적용값을 검사하는 실행 경로를 구현한다.
3. 같은 workload·CPU map·부하·원래 시한으로 일반/RT 조건을 비교한다. Timer→wakeup→switch는 커널 trace로 별도 관측한다.
4. 위 결과와 stack·driver 경계를 검토한 뒤 다른 Leaf 확대 및 M3 수용을 진행한다.

실행 방법은 [학습 안내](../learning/m3_rtos_pilot.md), 결과는 [품질 기록](../quality_policy.md)에 둔다.
공식 근거: [Trampoline POSIX platform](https://github.com/TrampolineRTOS/trampoline),
[Linux scheduling 권한과 정책](https://man7.org/linux/man-pages/man7/sched.7.html),
[PREEMPT_RT](https://www.kernel.org/doc/html/latest/core-api/real-time/index.html).

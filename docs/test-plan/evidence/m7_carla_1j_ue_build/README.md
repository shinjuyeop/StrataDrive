# M7-1j 후속 — Unreal Engine 빌드

2026-10-23 KST. **UE4.26.2 전체 make exit0**. CARLA 서버 빌드/실행과 직접 effort 확장은 NOT RUN이다.

Epic–GitHub 연결 후 `CarlaUnreal/UnrealEngine` private 저장소 및 `carla` branch 접근에
성공했다. 엔진은 `/d/shin/stratadrive-tools/UnrealEngine_4.26`에 준비했다.
commit은 `e9d9e60c85f643e10eeb03f42f61554d18dcb30f`, Build.version은4.26.2다.
기본 branch가 UE5 계열이어도 이 작업은 명시적으로 `carla` branch를 사용했다.

| 확인 | 결과 |
| --- | --- |
| clone / Setup.sh / GenerateProjectFiles.sh | 완료, Setup 및 프로젝트 생성 exit0 |
| make01 | 접근 확인 당시 명시적으로 중단(exit130). compiler failure로 분류하지 않음 |
| make02 | 기존 생성물 재사용, 전체 exit0. 2026-10-23 22:03:25 KST 종료 |
| UE4Editor | 본체2,779개 작업 완료, 실행 파일 생성 |
| 부속 도구 | UnrealHeaderTool / ShaderCompileWorker / UnrealInsights 생성 |
| ldd UE4Editor | exit0, `not found`0. 실행 검증을 대체하지 않음 |
| engine tracked source diff | 없음. 제공 clang10.0.1 toolchain 사용 |
| editor runtime / CARLA server/client source build | NOT RUN |
| M6 코드·계약·기존 수용 | 변경 없음. 기존 시험을 새로 PASS 처리하지 않음 |

[result.json](result.json)은 버전·commit·실행 파일 hash·종료 코드·가용 공간과 원본 로그의
외부 경로/hash를 기록한다. [ldd](ldd.txt), [마지막 build 출력](make-tail.txt),
[SHA256SUMS](SHA256SUMS)를 함께 둔다. 엔진 소스·바이너리를 프로젝트에 복사하지 않았다.
이전1j의 fork404·UE4_ROOT 누락 실패는 당시 evidence로 유지하며 현재 접근 blocker는 해소됐다.

엔진 빌드 재개 명령은 해당 engine root에서 `make`이며 `-j`를 추가하지 않았다.
CARLA 작업 프로세스에는 다음 경로를 전달한다:

```bash
export UE4_ROOT=/d/shin/stratadrive-tools/UnrealEngine_4.26
```

현재 Host에 `g++-12`가 없어 다음 CARLA 기본 빌드의 의존성 준비가 남는다.
관리자 설치는 암호가 필요한 상태다. Ubuntu22.04 의존성은
[CARLA 공식 빌드 안내](https://carla.readthedocs.io/en/0.9.16/build_linux/)를 따른다.
그 뒤 별도 Python 환경·0.9.16 asset·기본 서버/client를 준비하고 smoke를 검증한다.
NoDrive 서버 포트·calibration·full Actual 경로·interval work 검증은 후속 작업이다.

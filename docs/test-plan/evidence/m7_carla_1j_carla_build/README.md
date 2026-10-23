# M7-1j 후속 — CARLA 기본 빌드

2026-10-23 KST. 사용자 설치 후 시스템 의존성을 확인하고 별도 source/venv에서 기본 빌드를
진행했다. **Python Client와 CARLA Editor 서버 모듈 build exit0**. 서버 실행/연결·ego·센서·
직접 effort 확장은 NOT RUN이다. 기존 M6 수용·기록과1j 독립 SDK 시험 분모는 그대로다.

| 항목 | 실제 결과 |
| --- | --- |
| 시스템 의존성 | g++-12 12.3.0, libstdc++-12-dev, ninja-build, python3-venv, libtiff5-dev 설치 확인. [원본](system-dependencies.txt) |
| CARLA source | 0.9.16 tag commit294096eb1c38eabf246e4f3a9cdab704e33a7f4c, `/d/shin/stratadrive-tools/m7-source/carla-0.9.16` |
| UE |4.26.2 commit e9d9e60c85f643e10eeb03f42f61554d18dcb30f, 이전 전체 엔진 build 사용 |
| Python | 전용 `carla-build-venv`, Python3.10. [freeze](pip-freeze.txt), [import/버전](client-import.json) |
| 도구 | 기존 사용자 CMake4.x 대신 이 빌드 프로세스 PATH에서 `/usr/bin/cmake`3.22.1 사용 |
| Content | Update.sh exit0, ID20250912_2171890. [결과](carla-content-attempt01.json) |
| Python build01 | exit2, libpng1.6.37 URL404 |
| Python build02 | exit2, PROJ7.2.1의 `<cstdint>` 누락으로 std::int64_t compile 실패 |
| Python build03 | exit2, PROJ C parser가 PIC 없이 빌드되어 Python shared extension link 실패 |
| Python build04 | exit0, wheel 생성·전용 venv 설치/import 성공 |
| 서버 build01 | LibCarla.server.release/osm2odr/plugins와 BuildCarlaUE4 모두 exit0 |
| 서버 모듈 ldd | UE Binaries/Linux를 LD_LIBRARY_PATH로 지정, exit0/missing0. [출력](carla-module-ldd.txt) |

시도별 명령/종료 코드는 `carla-python-build-attempt0{1,2,3,4}.json`과
`carla-server-build-attempt01.json`에 있다. 경고를 제거하거나 실패를 PASS로 덮어쓰지 않았다.
전체 build 로그는 [manifest](manifest.json)의 외부 경로와 SHA256으로 보존한다.
UE 소스·바이너리·대용량 content를 프로젝트에 복사하지 않는다.

## 빌드 호환성 변경

[Setup.sh patch](carla-build-compat.patch)는 외부 CARLA checkout에 적용했다.

- libpng1.6.37은 [공식 older-releases 경로](https://sourceforge.net/projects/libpng/files/libpng16/older-releases/1.6.37/)로만 변경했다. 버전은 유지했다.
- PROJ7.2.1 헤더에 `<cstdint>`를 추가했다. 계산 식 변경은 없다.
- PROJ C/C++ static library를 shared module에 링크할 수 있도록 CMake PIC 옵션을 켰다.

부분 설치 폴더는 `Build/proj-*.attempt02-partial` 및 `*.attempt03-nonpic`로 이동해
잘못된 완료 감지/기존 파일 덮어쓰기를 피했다. 이후 PROJ 양쪽 ABI를 다시 만들었다.
서버는 공식 `--no-simready`로 빌드했다. [생성된 설정 diff](simready-generated.patch)는
MDL/SimReady 제외이며 custom actuation 구현이 아니다. default stock physics는 그대로다.

Python wheel 배포 버전은0.9.16, API `get_client_version()`은 `294096e-dirty`다.
이 값은 source checkout/빌드 수정의 identity이며 수신값을0.9.16으로 바꾸지 않는다.
실제 서버 handshake는 NOT RUN이므로 버전 일치 PASS를 주장하지 않는다.

## 실행 재현과 다음 단계

빌드 프로세스에 다음 환경을 사용했다. 기존 실행 package/venv는 교체하지 않았다.

```bash
export UE4_ROOT=/d/shin/stratadrive-tools/UnrealEngine_4.26
export PATH=/d/shin/stratadrive-tools/m7-source/carla-build-venv/bin:/usr/bin:/bin
cd /d/shin/stratadrive-tools/m7-source/carla-0.9.16
make PythonAPI ARGS=--python-version=3.10
make LibCarla.server.release osm2odr downloadplugins
bash Util/BuildTools/BuildUE4Plugins.sh --build
bash Util/BuildTools/BuildCarlaUE4.sh --build --no-simready
```

빌드 성공은 정상 주행 수용이 아니다. 다음은 새 source 서버를 별도 port/venv로 실행해
서버·클라이언트 identity/연결·ego 생성/종료를 smoke 검증하는 일이다. 이후 NoDrive 서버
포트·Actual single writer·calibration·raw wheel validity·interval work를 각각 구현/검증한다.
소스 patch와 실제 wheel·서버 module hash는 manifest에 있고, evidence hash는 SHA256SUMS다.

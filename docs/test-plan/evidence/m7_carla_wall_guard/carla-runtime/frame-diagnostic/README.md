# CARLA 기본 경로·영상·통합 경로 지연 비교

2026-10-29, 기준 commit `b2b23e5`. 실제 Host에서 수행한 **유한 진단**이며 실시간 주행 수용 시험이 아니다.
M6 코드·계약, M7 기능 수용, 기존 wall FAIL, Drive30ms와 owner2ms/4ms는 변경하지 않았다.
현재 판정은 [프로젝트 상태](../../../../../project-status.md)에 둔다.

## 판단

1. **CARLA가 차량 상태를100Hz에 가까운 실제 속도로 제공할 수 없다는 가설은 이 조건에서 맞지 않는다.**
   동일 source 서버에서 확장을 비활성화하고10ms 간격으로 tick을 요청하자1000구간의 서버 상태 생성
   간격은 최대10.830ms였다. 공식 패키지에서도 최대10.826ms를 관측했다. 둘 다30ms 초과0이다.
   정지 차량·짧은 구간의 관측이며 worst-case 상한이나 주행 수용 증거가 아니다.
2. **현재 영상 구성이 프레임 지연에 기여한다는 대조 증거가 있다.** Source 서버에서 화면 렌더링만
   켜면 최대16.662ms였지만, RGB+GT를20Hz로 생성하면30ms 초과가1000구간 중200번 발생했다.
   영상 포함10ms 요청 시험에서도 같은200번이 재현됐으며 특정 frame modulo5에 모였다.
   공식 패키지의 같은 영상 조건도17/1000번 초과했다. 카메라가 있어도 Python은 영상 도착을
   기다리지 않고 tick하므로 client의 센서 join 대기를 측정한 것이 아니다.
3. **비영상 통합 경로에도 별도 비용·지연 변동이 남는다.** 기존 Actual/NoDrive320/work/단일 EV를
   그대로 연결한 compact 시험은 가상9s를 실제8.695s에 완료했지만, 의도한 pause를 제외해도
   취득→다음 native 완료 최대47.016ms였다. 기본 경로의 결과를 이 통합 경로 수용으로 전용하지 않는다.

우선순위는 비영상 wall 경로의 간헐 지연을 분해하고, 영상의 capture/render/readback 완료가 차량
상태 진행을 막는 경로를 별도로 계측·최적화하는 것이다. 주기적 cached 재발행이나30ms 확대를
해결책으로 채택하지 않는다. 이번 대조만으로 특정 UE 함수·GPU 부족·NoDrive320 하나를
근본 원인으로 확정하거나, 분리 구현이 반드시 기존 deadline을 만족한다고 약속하지 않는다.

## 비교 조건과 실제 분모

Host Ubuntu22.04/kernel6.8, i7-11700/16 logical CPU, RTX3090/24GiB,
NVIDIA580.178.04. [Host](host.json), [저장장치](storage.json)를 보존했다.
동일 Town03_Opt/첫 spawn/mkz_2020/ClearNoon/traffic0, world synchronous10ms,
world substep 최대10/최대dt10ms, 단일 tick client다. OpenDRIVE SHA는 모든 정상 측정에서
`abf177bcd9b66cfefb7ac4919f6456815f1384f4229f1343c8a6a90bbb7713c9`로 일치한다.

기본 경로에는 actuation 호출·StrataDrive binding·V1·solver observer가 없다.
Source의 `describe`가 disabled/unlocked인 것을 확인했다. 클래스 확장은 설치돼 있으나
비활성 상태에서는 원래 vehicle 구현을 호출한다. 따라서 이를 무수정 source build라고 부르지 않는다.
Official은 배포된 Shipping 실행 파일/client0.9.16, source는 UE4Editor game 모드/
client294096e-dirty다. 빌드·asset/render 설정 차이도 있어 두 binary의 차이를 확장 코드만의 비용으로
단정하지 않는다. Binary/module SHA와 실제 인수는 각 `server.json`에 있다.

각 기본 case는150tick 예열 후1000tick을 측정했다. 원본 frame·simulation time·server
`platform_timestamp`와 client monotonic bracket을 RAM에 기록하고 측정 후 저장했다.
아래는 **server platform timestamp의 연속 차이**이며 통신 latency나 제어 source-age 자체는 아니다.
원래 서로 다른 clock의 절대값을 빼지 않았다. `pace10`은 요청 사이 최소 약10ms를 기다리는
진단 정책이며 늦은 tick을 몰아서 따라잡지 않는다. Source/패키지의 두 camera는320×240/FOV90°,
sensor_tick50ms, `(1.6,0,1.7)m`/pitch−8°다. Pixel 복사·hash·파일 쓰기 없이 metadata만 수집했다.

| Case | 요청/영상 | 평균 간격ms | p99 ms | 최대ms | >30ms /1000 | 실행·정리 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| source-state-b | 최대 속도, rendering off | 0.824 | 1.694 | 2.954 | 0 | 정상 진단 종료 |
| source-render-a | 최대 속도, rendering on·camera0 | 6.762 | 10.462 | 16.662 | 0 | 정상 진단 종료 |
| source-paced-a | pace10, rendering off | 10.077 | 10.493 | 10.830 | 0 | 정상 진단 종료 |
| source-camera-a | 최대 속도, RGB+GT | 13.865 | 51.204 | 71.160 | 200 | 정상 진단 종료 |
| source-camera-paced-a | pace10, RGB+GT | 14.441 | 49.747 | 65.078 | 200 | 정상 진단 종료 |
| package-paced-b | pace10, rendering off | 10.076 | 10.558 | 10.826 | 0 | 측정 완료, server exit−11 |
| package-camera-paced-b | pace10, RGB+GT | 10.958 | 33.053 | 44.259 | 17 | 측정 완료, server exit−11 |

영상 네 측정은 각각 RGB200/GT200이며 측정 frame 내 원본 sensor timestamp 일치를 검사했다.
Source 영상 두 실행은 동일5frame 반복의 다른 phase에서 capture와 긴 공백이 관측됐다.
이는 영상 pipeline과의 연관 증거이며 정확한 blocking call stack을 얻은 것은 아니다.
독립 재계산은 [comparison.json](comparison.json)에 있다. 패키지의−11은 별도 실패로 보존하고
측정값만 `VERIFIED_SAMPLES_WITH_SERVER_FAILURE`로 분류했다. 패키지 lifecycle PASS는 아니다.

### 기존 통합 경로 재실행

수정 없는 `m7_integrated_run.py --cases normal-a camera-a --compact-work --held-steer-sleep`를
같은 Host에서 순차 실행했다. 원래900 physics/work/EV 정산과 wire·work·energy·scenario·sensor·clock
감사를 모두 통과했다. 두 case의 PASS는 **기능 범위**이며 새 wall runtime PASS가 아니다.

| Case | 가상/실제 loop 시간 | advance→receipt 평균/최대 | 의도한 pause 제외 취득→다음 native 완료 최대 / >30ms |
| --- | --- | --- | --- |
| normal-a | 9s /8.694567s | 6.997/46.510ms | 47.016ms /86 of899 |
| camera-a | 9s /19.205365s | 17.702/178.529ms | 178.158ms /287 of899 |

각 loop에는 기존 writer/tick 거부 검사·250ms pause가 있다. 위 마지막 열은 원래 auditor의
`excluding_intentional_pause`다. 서버 platform 간격과 이 통합 취득/처리 구간은 서로 다른
측정이므로 표끼리 빼서 특정 함수의 실행시간을 계산하지 않는다. 카메라는 RGB180/GT180이었다.
기존 비compact60s의213.88/244.37s와도 workload·기록 방식·시나리오 길이가 달라 순수 engine
성능 향상률로 비교하지 않는다. 원본은 [통합 suite](integrated/suite.json)에 있다.

## 실패·관측 한계

- 초기 `source-state-a`는 포트 준비 대기 없이 client를 시작한 뒤 준비 단계에 머물러 소유 client를
  중단했다. 측정0이며 성능 분모에서 제외했다. 포트 준비 후 client를 시작하도록 진단 runner를 수정했다.
- `package-state-a`, `package-camera-a`는 실행 인수의 지도 선택이 적용되지 않고 Town10HD_Opt로
  시작해 map 검사를 거부했다. 종료 코드−11도 보존했다. 성공으로 재기록하지 않았다.
  후속 두 package case는 actor/sensor 생성 전에 명시적 `load_world('Town03_Opt')`와 새 client를 사용했다.
- 기본 경로 전체10시도 중5개는 측정·정상 server 종료,2개는1000구간 측정 후 확인한 server exit−11,
  3개는 준비/map 단계 실패다.−11의 정확한 발생 지점과 원인은 이번에 확정하지 않았다.
- Source 기동 중 HDD(`/d`, rotational1)의 읽기 대기가 관측됐다. `startup-io.txt`의 연속1초 표본은
  sda util94.9/95.4%, read await7.71/6.53ms다. 예열 후 측정과 구분한다. 실제 측정 중 server
  read_bytes 증가는 source-paced0, source-render8192, source-camera-paced184320bytes였다.
  기동 I/O를 영상의 반복 지연 원인으로 단정하지 않는다.
- Desktop background process를 강제 종료하지 않았고 CPU/GPU 독점·RT scheduling을 새로 설정하지 않았다.
  정지 차량·고정 map·1000frame 표본이며 이동·충돌·장시간·모든 scene의 상한을 보장하지 않는다.
- 신규 M6/ASan/TSan 회귀는 실행하지 않았다. 기존 C++/엔진/계약을 바꾸지 않았다.
  새 Python runner의 실제 실행, frame/sensor/clock 독립 감사와6개 손상 거부를 수행했다.
  [손상 검사](audit-corruptions.json)는 frame 중복·simulation restamp·host bracket 역전·server gap 변조·
  보고 max 변조·sensor restamp를 모두 거부했다.

## 재현·보관

새 경로를 사용하며 다른 CARLA와 부하를 겹치지 않는다. 기본 진단의 port는2300/2301/2302다.
패키지는 최초 지도 로딩이 필요할 수 있다. Source/패키지를 다시 설치하거나 빌드하지 않는다.

```sh
python3 tests/integration/carla/m7_frame_baseline.py --backend source \
  --pace-ms 10 --output /tmp/m7-frame-source-new
python3 tests/integration/carla/m7_frame_baseline.py --backend source \
  --pace-ms 10 --cameras --output /tmp/m7-frame-source-camera-new
# --backend package: 공식 패키지 비교. --render: camera 없이 rendering on.
python3 tests/integration/carla/analyze_m7_frame_baseline.py \
  /path/to/diagnostic-root --output /tmp/m7-frame-comparison-new.json
```

최종 source는 `sources/`, 초기 runner는 `baseline-original.py`/`baseline-port-ready.py`,
후속 비교용 고정 source는 `baseline-final.py`에 있다. 초기 source-camera-a는 runner의 진단 필드
추가 도중 실행돼 parent hash를 child 전체 source 동일성으로 해석하지 않는다. 최종 source hash가
일치하는 source-render/pace/camera-pace와 후속 package 측정을 최종 비교 기준으로 삼았다.
새 actor 삭제·world 설정 복원과 server 종료는 별도 기록한다. 모호한 tick 재시도는 없다.

`artifact-manifest.json`에 원본/저장본 SHA와 경로가 있다. Log/CSV/JSONL만 무손실 gzip으로
보관했고 ELF는 원래 실행 metadata의 SHA로 식별한다. 기본 비교는 보관된 JSON으로 그대로 재검사할 수
있고 기존 통합 auditor는 `trace.jsonl.gz`를 읽는다. `SHA256SUMS`로 전체 보관물 무결성을 확인한다.

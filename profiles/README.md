# Profile과 실제 실행 설정

YAML은 **설계/fixture 기록**이며 runtime loader·자동 inheritance는 없다.
`null`은 미결정이며 무제한/비활성화/default가 아니다. 현재 상태는
[현재 상태](../docs/project-status.md), milestone/TBD는 [roadmap](../docs/roadmap.md)을 따른다.

| 파일/설정 | 역할과 실제 적용 경로 |
| --- | --- |
| `reference.yaml` | Reference ODD·논리 rate·과거 M1–M6 fixture 기록. C++/Python 코드와 runner 옵션이 실제 값을 정한다. YAML 자체가 프로세스를 설정하지 않음 |
| `thor_premium.yaml`, `orin_mainstream.yaml` | 별도 보드별 후보 override. 자동 상속/배포/benchmark 결과가 아님; 같은 reference의 독립 측정 후 비교 |
| `m6_sil_response_v1.json` | 예외적으로 **실제 읽는 M6 설정**. `front_run.py`/`physical_response.py`가 energy normal/command-loss의 완료 threshold·budget을 공유하고 compiled model readback을 대조. 모델 rate·명령 권한을 바꾸지 않음 |
| `perception-host-v1.json` | **M10 실행 계약과 모델 provenance**. Python adapter가 모델/hash·shape·camera·threshold·budget과 코드의 일치를 검사한다. 고정 CPU fixture이며 Reference 전체 workload·Target 수용을 대신하지 않음 |
| `perception-cuda-host-v1.json` | 같은 M10 semantic/model에 대한 **명시적 CUDA 실행 descriptor**. `--execution cuda`에서만 검증·사용하며 자동 상속/자동 provider 선택은 없음. TF32와 CPU node fallback 금지 |
| `perception-startup-host-v1.json` | 선택형 준비3회·전체10s/뒤2회100ms exclusive·실패 latch. Startup 비용과 sensor 분모를 모두 보존; driving readiness 아님 |
| `perception-carla-rgb-host-v1.json` | Low/ClearNoon·RGB postprocess enabled·원본 frame5 취득의 명시적 live fixture. 모델/threshold/geometry 동일; 전체 renderer/ODD 수용 아님 |
| `perception-quality-plan-v1.json` | 실제 quality capture가 읽는 development/holdout 각81배치·6종 객체·3기상·거리/가림/중첩 계획. Epic·매 tick 센서 수집이며 live20Hz 프로파일과 구분 |
| `perception-quality-protocol-v1.json` | Offline 비교의 잠정 절대/상대 gate와 후보2종·지명 순서. 추론 전 hash 고정; 보류 평가로 재조정하거나 runtime을 자동 교체하지 않음. [프로토콜과 정답 한계](../docs/test-plan/perception-quality-protocol.md) 참고 |
| `perception-quality-plan-v2.json`, `perception-quality-protocol-v2.json` | Rider-aware 새 평가의 배치·후보·coverage. 실제 settling 후 pose 대조, 같은 class NMS와 base를 보존하는 VRU 확대, 기존 숫자 gate 유지. [V2 프로토콜](../docs/test-plan/perception-quality-v2-protocol.md) 참고 |
| `perception-quality-v1-exclusion.json` | 이미 사용한 v1 개발/보류 RGB162개 hash. 새 v2 데이터에 이전 영상을 재사용하지 않도록 prepare/score에서 검사 |
| `perception-quality-preparation-v3.json` | 별도 camera spawn4의 자산/가시성 준비180장. 가림 없는 참조36장과 비교하며 모델 점수 없이 모든 계획 객체의 최소 지원을 요구 |
| `perception-quality-plan-v3.json`, `perception-quality-protocol-v3.json` | S/M/M 확대 후보와 새 개발/보류 각81개 계획. 준비·독립 수치 검사 PASS 뒤 freeze, 기존 정확도 gate 유지. [V3 기준](../docs/test-plan/perception-quality-v3-protocol.md) 참고 |
| `perception-quality-exclusion-v3.json` | V1/V2·실패한 첫 준비·수정 준비에서 사용한 RGB648개 hash. 새 평가의 영상 재사용을 거절 |
| `perception-road-evaluation-v4.json` | V4 실제14/24번 site의 도로 맞춤 평가 pose162개. 새 실제 coverage PASS·모델 품질 FAIL을 보존하며 held walker far는26m로 한정 |
| `perception-road-preparation-v4.json`, `perception-road-protocol-v4.json` | 실제 두 camera site의 준비198개와 엄격한 geometry/가시성 기준. 경로 전체 junction 제외·부분 가림 참조·모든 Rider13 지원을 요구. [기준](../docs/test-plan/perception-road-preparation-v4-protocol.md) 참고 |
| `perception-road-exclusion-v4.json` | 준비 단계에서 검사한 이전 RGB891개 hash. [준비 묶음](../docs/test-plan/evidence/m10_road_preparation_v4/README.md)의 미래 제외1387개와 이후 거절/진단324개를 새 평가 제외 목록1711개에 연결 |
| `perception-quality-protocol-v4.json`, `perception-quality-exclusion-v4.json` | V4 도로 평가의 기존 S/M/M 확대·엄격한 품질/coverage gate와1711개 prior RGB 제외. Metadata v4b는 capture hash 연결 회귀 뒤 새 freeze·재수집. [결과](../docs/test-plan/evidence/m10_quality_v4/README.md)의 다음 제외 목록1873개는 별도 미래 입력 |

실제 Host profile은 [SOME/IP Rear ICD](../docs/interfaces/someip-rear-adapter.md),
M6 모델/energy/물리 응답은 [vehicle-energy ICD](../docs/interfaces/vehicle-energy.md),
독립 Python MIL은 [simple-vehicle ICD](../docs/interfaces/simple-vehicle-model.md)를 따른다.
Host10-v1과 M6 quiet/기존 M5 부하·각 관측 구간을 같은 profile로 합치지 않는다.

M1–M4 fixture의 설명·개발 당시 적용 범위는 [학습 인덱스](../docs/learning/README.md)와
각 ICD/ADR에 있다. YAML에 남은 과거 fixed speed·ideal-HV·standalone model 설정을
현재3-vECU vehicle/EV 통합의 실제 설정으로 해석하지 않는다.
Target 보드/AI workload·engine/checksum·power/thermal·clock은 별도 TBD-09/07 범위다.

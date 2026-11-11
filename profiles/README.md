# Profile과 실제 실행 설정

YAML은 **설계/fixture 기록**이며 runtime loader·자동 inheritance는 없다.
`null`은 미결정이며 무제한/비활성화/default가 아니다. 현재 상태는
[현재 상태](../docs/project-status.md), milestone/TBD는 [roadmap](../docs/roadmap.md)을 따른다.

| 파일/설정 | 역할과 실제 적용 경로 |
| --- | --- |
| `perception-model-screen-v1.json` | 공개 사전학습 S/M/L·RT-DETRv2-R18·NanoDet의 별도 offline identity/tensor·출처. 같은 개발324장 비교용이며 live/Target profile이나 자동 runtime 교체가 아님. 보드 최적화는 후속 |
| `perception-model-screen-v2.json` | S/L·RT-DETRv2-R18에 D-FINE-M·RT-DETRv4-S·공식 ModelScope DAMO legacy를 추가한 offline identity. 개발324장 calibration·선택 봉인 뒤 Town04 개발81장 확인. 기본 runtime0.35·기존 보류·Jetson 미실행 경계 유지 |
| `perception-class-calibration-grid-v1.json` | D-FINE/RT-DETRv4의 클래스별5점×6class 사전 검색 규칙과 기존 절대/상대 gate 우선순위.0.35 하한 유지·Town04는 이미 소비한 개발 regression |
| `perception-class-calibration-candidates-v1.json` | 고정 가중치/전처리/selection SHA와 파생 confidence vector. 다음 새 품질 평가 후보는 D-FINE-M이며 최종 Reference/runtime profile이 아님. 과거/현재 FAIL과 기본 S 유지 |
| `reference.yaml` | Reference ODD·논리 rate·과거 M1–M6 fixture 기록. C++/Python 코드와 runner 옵션이 실제 값을 정한다. YAML 자체가 프로세스를 설정하지 않음 |
| `thor_premium.yaml`, `orin_mainstream.yaml` | 별도 보드별 후보 override. 자동 상속/배포/benchmark 결과가 아님; 같은 reference의 독립 측정 후 비교 |
| `m6_sil_response_v1.json` | 예외적으로 **실제 읽는 M6 설정**. `front_run.py`/`physical_response.py`가 energy normal/command-loss의 완료 threshold·budget을 공유하고 compiled model readback을 대조. 모델 rate·명령 권한을 바꾸지 않음 |
| `perception-host-v1.json` | **M10 실행 계약과 모델 provenance**. Python adapter가 모델/hash·shape·camera·threshold·budget과 코드의 일치를 검사한다. 고정 CPU fixture이며 Reference 전체 workload·Target 수용을 대신하지 않음 |
| `perception-async-native-v1.json`, `perception-async-native-fault-v2.json` | opt-in native4K/960 비동기 owner와 독립 state/camera/관측 consumer 재생 조건. 원래 즉시 예외 overlap FAIL·별도25ms 오류 응답 fixture를 보존. 실제 차량 제어/live camera/ROS/Target 연결·20Hz 수용 아님 |
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
| `perception-road-preparation-v5.json`, `perception-road-evaluation-v5.json` | 다음 미사용31/35번 road의 모델 없는 준비198개·새 평가162개. 최종 도로 pose/거리와 actor/rider gate 유지; 임시 spawn staging-v5b만 수정 |
| `perception-quality-exclusion-v5.json`, `perception-quality-evaluation-exclusion-v5.json` | 준비용 과거1873개와 평가용 과거+모든 준비2195개 RGB 제외. [결과](../docs/test-plan/evidence/m10_quality_v5/README.md)의 다음 평가용2357개는 별도 artifact |
| `perception-quality-protocol-v5.json` | 고정 M 원본/중앙 VRU·양방향 약한 지지·body 충돌 억제 정책과 기존 절대/상대 gate. 개발 PASS·보류 FAIL로 미채택; [V5 기준](../docs/test-plan/perception-quality-v5-protocol.md) 참고 |
| `perception-road-preparation-v6.json`, `perception-road-evaluation-v6.json` | 다음 미사용74/80번 도로의 준비198개·평가162개. 기존 road/pose/가시성 gate와 V5b staging 유지 |
| `perception-quality-exclusion-v6.json`, `perception-quality-evaluation-exclusion-v6.json` | 준비용 과거2357개·평가용 과거+준비2555개 RGB 제외. 다음2717개 제외는 [결과 묶음](../docs/test-plan/evidence/m10_quality_v6/README.md)의 별도 artifact |
| `perception-quality-protocol-v6.json` | 고정 L 원본/전체 클래스 중앙 확대·약한 raw 지지·확대 시야 body 판단. 기존 숫자 gate·개발 지명·새 보류 순서 유지; [V6 기준](../docs/test-plan/perception-quality-v6-protocol.md) 참고 |
| `perception-domain-preflight-v1.json`, `perception-domain-collection-v1.json` | 모델 없는22자산/176장 검사와4도로의1020개 개발 수집. Train/validation의 road·가능한4class blueprint 분리;127번 보류 미수집 |
| `perception-domain-extension-v1.json`, `perception-domain-exclusion-v1.json` | person 가림48장 추가와 과거2717+사전176개 제외2893개 RGB. 원래 FAIL/작은 양성을 유지하고 사전 split 단위 coverage로 검사 |
| `perception-domain-support-v1.json` | 작은 walker/WetCloudyNoon의 가림차 위치6단계와 참조. Descriptor의4site 중 train31만12장 추가 수집; 모델/예측 없이 원래 split FAIL 보존 |
| `perception-training-v1.json` | 고정813/267장의 첫 L6·24epoch FP32 학습과 모든 visible 양성·epoch0 포함 macro F1 선택·새11채널 출력. Validation은 개발 자료; 새 quality holdout/기본 S 승격과 별도 |
| `perception-road-preparation-v7.json`, `perception-road-evaluation-v7.json` | 지도만으로 고정한215/127번·준비198장/평가162장. 기존 road/Rider/pose·held person26m·staging 유지 |
| `perception-quality-exclusion-v7.json`, `perception-quality-evaluation-exclusion-v7.json` | 과거3973개와 모든 준비를 제외. 미래 소비 RGB는 V7 evidence에 별도 보존 |
| `perception-quality-protocol-v7.json`, `perception-trained-model-v1.json` | 고정 epoch17 L6·새11채널/native mapping·S와 unchanged strict absolute/relative gate. 기존 runtime 자동 교체0 |
| `perception-quality-template-v8.json`, `perception-road-*-v8.json` | 새 Town04 map-only7/25의 원래 준비/평가 recipe. 최초 보류 person 가림 FAIL을 보존하며 평가에 사용하지 않은 초기 계획 |
| `perception-quality-template-v8b.json`, `perception-road-*-v8b.json` | 모델 추론 전 holdout person occluder만20cm 이동한 별도 revision. actor 거리/기준/두 site 유지; 새 준비 뒤 최종162장 평가에 사용 |
| `perception-quality-protocol-v8.json`, `perception-quality-exclusion-v8.json`, `perception-quality-evaluation-exclusion-v8.json` | 공식 pretrained L raw full view와 S·기존 quality gate. 과거4333+모든 준비495개를 제외하고 지명 후 보류 취득; 다음 제외4990개는 V8 evidence에 보존 |

실제 Host profile은 [SOME/IP Rear ICD](../docs/interfaces/someip-rear-adapter.md),
M6 모델/energy/물리 응답은 [vehicle-energy ICD](../docs/interfaces/vehicle-energy.md),
독립 Python MIL은 [simple-vehicle ICD](../docs/interfaces/simple-vehicle-model.md)를 따른다.
Host10-v1과 M6 quiet/기존 M5 부하·각 관측 구간을 같은 profile로 합치지 않는다.

M1–M4 fixture의 설명·개발 당시 적용 범위는 [학습 인덱스](../docs/learning/README.md)와
각 ICD/ADR에 있다. YAML에 남은 과거 fixed speed·ideal-HV·standalone model 설정을
현재3-vECU vehicle/EV 통합의 실제 설정으로 해석하지 않는다.
Target 보드/AI workload·engine/checksum·power/thermal·clock은 별도 TBD-09/07 범위다.

[전처리 V1](perception-native-preprocess-v1.json)과 [실제4K 관측 V1](perception-carla-native-async-v1.json)은 opt-in 실험이다. [근거](../docs/test-plan/evidence/m10_native_preprocess_v1/README.md)의 재생 PASS와 live fresh-output FAIL을 구분하며 기본 runtime을 승격하지 않는다.

[Native kernel V1](perception-native-kernel-v1.json)은 정확히 고정한 CPU library와 입력 동등성·clock별 admission trace를 사용하는 opt-in profile이다. [실제 관측 결과](../docs/test-plan/evidence/m10_native_kernel_v1/README.md)의27개 fresh와 초기4개 late를 함께 유지한다.

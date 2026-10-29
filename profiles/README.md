# Profile과 실제 실행 설정

YAML은 **설계/fixture 기록**이며 runtime loader·자동 inheritance는 없다.
`null`은 미결정이며 무제한/비활성화/default가 아니다. 현재 상태는
[현재 상태](../docs/project-status.md), milestone/TBD는 [roadmap](../docs/roadmap.md)을 따른다.

| 파일/설정 | 역할과 실제 적용 경로 |
| --- | --- |
| `reference.yaml` | Reference ODD·논리 rate·과거 M1–M6 fixture 기록. C++/Python 코드와 runner 옵션이 실제 값을 정한다. YAML 자체가 프로세스를 설정하지 않음 |
| `thor_premium.yaml`, `orin_mainstream.yaml` | 별도 보드별 후보 override. 자동 상속/배포/benchmark 결과가 아님; 같은 reference의 독립 측정 후 비교 |
| `m6_sil_response_v1.json` | 예외적으로 **실제 읽는 M6 설정**. `front_run.py`/`physical_response.py`가 energy normal/command-loss의 완료 threshold·budget을 공유하고 compiled model readback을 대조. 모델 rate·명령 권한을 바꾸지 않음 |

실제 Host profile은 [SOME/IP Rear ICD](../docs/interfaces/someip-rear-adapter.md),
M6 모델/energy/물리 응답은 [vehicle-energy ICD](../docs/interfaces/vehicle-energy.md),
독립 Python MIL은 [simple-vehicle ICD](../docs/interfaces/simple-vehicle-model.md)를 따른다.
Host10-v1과 M6 quiet/기존 M5 부하·각 관측 구간을 같은 profile로 합치지 않는다.

M1–M4 fixture의 설명·개발 당시 적용 범위는 [학습 인덱스](../docs/learning/README.md)와
각 ICD/ADR에 있다. YAML에 남은 과거 fixed speed·ideal-HV·standalone model 설정을
현재3-vECU vehicle/EV 통합의 실제 설정으로 해석하지 않는다.
Target 보드/AI workload·engine/checksum·power/thermal·clock은 별도 TBD-09/07 범위다.

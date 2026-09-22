# Model artifact policy

Status: M0 정책이며, 포함하거나 다운로드한 model은 없다.

대용량 dataset, weight, export한 ONNX 파일, device별 TensorRT engine은 Git 외부에서
관리한다. 향후 artifact manifest에 출처/license, checksum, model version, export 설정,
calibration 출처와 호환 runtime/hardware를 기록한다. 한 보드에서 만든 engine이
다른 보드에서도 동작한다고 가정하지 않는다.

`.gitignore`는 기본적으로 `models/*`, `*.pt`, `*.pth`, `*.onnx`, `*.engine`, `*.plan`을
제외한다. 이는 검토 후 조정할 수 있는 기본 정책이며 작은 예제를 영구 금지하는 것은
아니다. 검토를 거쳤고 재배포할 수 있는 작은 fixture는 `.gitignore`의 **마지막에**
정확한 경로의 예외를 추가한다. 예시는 다음과 같다.

```gitignore
!models/samples/
models/samples/*
!models/samples/tiny-reviewed.onnx
```

추가 전에 크기, license, 출처, checksum, 해당 test에서 필요한 이유를 문서화한다.
크기 기준과 외부 저장소/Git LFS 정책은 TBD다. Model directory 전체의 제외를 해제하거나
`git add -f`를 관행적으로 사용하지 않는다. 제외된 dataset directory에 나중에 README를
추적하려면 상위 directory에도 명시적인 예외가 필요하다.

미결정 size/license/storage policy의 owner는 project owner이며 TBD-11(M10 첫 model
fixture 전)이다. 보류 이유와 gate는 [TBD register](../docs/roadmap.md#open-m0-decisions)에 있다.

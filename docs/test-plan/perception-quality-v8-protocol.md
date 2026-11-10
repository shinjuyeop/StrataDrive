# M10 V8: 사전학습 L 고정 후보의 새 Town04 평가

2026-11-10. 사전학습5종의 개발324장 비교 뒤 공식 YOLOX-L 원본을 단일 후속 후보로
고정한다. SHA256 `7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411`,
216746733byte·FP32·input[1,3,640,640]·output[1,8400,85]다. 기존 S와 같은 RGB0–255/
top-left letterbox114·score.35·classwise NMS.5를 사용한다. 추가 학습·crop/ensemble·
threshold 변경·보드 최적화는 없다. Thor/Orin NX의 별도 배포는 고려하되 실제 engine/보드 검증은 후속이다.

## 새 지도와 순서

Town03의 원래265개 조사에서 적격 미사용 도로가 소진되었다. 설치된 **Town04_Opt**를
영상/모델 점수 없이 새로 조사한다. 모든 spawn의0–42m 도로 노드를 기록하고 기존 route
규칙(모든 구간 nonjunction·폭≥3.2m·heading 변화≤15°·카메라 frustum·index≥7)을 유지한다.
번호순 첫 적격 site와, 다른 road ID·거리≥50m인 다음 적격 site를 각각 development/holdout으로
고정한다. Town03의 road ID와 Town04의 ID는 서로 다른 지도 namespace다. Town04 데이터는
이번 단계 전에는 모델 설계/학습/평가에 사용하지 않았다. 같은 actor asset을 포함한 정지 합성
fixture이므로 실제 ODD·새 자산·동적 주행 전체 일반화를 주장하지 않는다.

지도 조사 source와 본 기준을 먼저 봉인한다. 조사 결과에서 위 규칙으로 두 site를 재생하고,
기존6class×3weather·거리/가림/중첩/negative recipe를 새 도로 pose로 변환한다. 카메라
640×384/FOV90/Epic/postprocess, world10ms·settle40/capture10/선택tick5를 유지한다.
Held person far26m/준비27m, physics-off·tick 전50m staging, route/clearance 규칙도 같다.

## 모델 없는 준비와 고정

실제 두 camera site에서 준비99장씩 수집해 모든 계획 actor/Rider의25pixel/side4,
pose2cm/0.1°·road projection2m/clearance15cm와18개 occlusion/reference를 검사한다.
준비는 거리+1m·camera높이+.05m이며 평가81장과 RGB/episode가 다르다. 준비의 정답/가시성만
검사하며 모델 점수로 site나 장면을 교체하지 않는다. 실패/부분 수집과 변경이 필요하면 원래
자료를 보존하고 모델 추론 전 명시적인 새 준비 revision으로 처리한다.

과거4333개 RGB와 이번 모든 준비/거절 RGB를 평가에서 제외한다. 준비 개발의 고정3장으로
S/L CPU/CUDA/OpenCV raw(atol1e-3/rtol1e-4)·완성 검출(count/class 동일·box.01pixel/
score1e-4)을 확인한다. source/plan/model/protocol/exclusion을 고정한 뒤 development81장을
새로 수집·평가하고 점수/단일 지명을 봉인한 다음에만 holdout81장을 수집한다.

Startup180s/capture900s/shutdown30s와 정상 exit130을 유지한다.0frame readiness/RPC 시작
실패만 같은 source/plan/budget으로1회 자동 재시도할 수 있다. 실패는 PASS로 바꾸지 않는다.
대용량 archive 읽기/압축과 UE 시작은 동시에 실행하지 않는다. 이 순서가 시작 안정성의 근본
원인을 해결했다는 뜻은 아니다. 모든 실제 시도와 cold/init·error·late를 원래 분모로 남긴다.

## 그대로 유지하는 판단 기준

Visible tight box IoU≥.5·Rider→person·primary-ignore=false를 유지한다. 기존 절대 gate는
P≥.85/R≥.8·모든 class R≥.7·near person R≥.9·negative FP/frame≤1/3이다. 상대 gate는
S 대비 P+.03·전체/class/far/occluded recall 무하락·near person TP 무하락·negative FP
무증가다. 작은 객체 ignore/covered miss 진단은 TP/gate를 바꾸지 않는다.

후보는 baseline S와 단일 `large-v8`뿐이다. 개발 FAIL이어도 사전 고정 후보의 descriptive
holdout을 남길 수 있으나 실패를 상쇄하지 않는다. 보류에서 후보 재탐색·계획/기준 조정은 없다.
두 partition 모두 절대/상대 조건을 통과해야 새 runtime profile/interface 검토가 가능하다.
과거 V6 L/V7 L6 실패는 그대로 보존하며, 이번 결과로 기존 runtime을 자동 교체하지 않는다.

원본 RGB/instance→GT/pose/visibility·점수·nomination·취득 순서를 재구성하고 새 경로에서
압축 재감사를 한다. 이번 offline replay는 전체wall20Hz·차량 통합·Jetson 검증과 구분한다.
[모델 선정 순서](../perception-model-selection.md)와 기존 M10 경계를 유지한다.

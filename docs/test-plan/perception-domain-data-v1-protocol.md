# M10 전용 개발·학습 데이터 v1 사전 기준

2026-11-09. 모델 없는 데이터 수집·정답/분리/내보내기 단계다. 모델 학습·새 정확도/보류 평가나
runtime 승격은 포함하지 않는다. V1–V6 원본·소스·점수·숫자 gate와 기본 S를 유지한다.
과거 RGB2717개와 모든 이번 asset-preflight/거절 영상을 최종 collection에서 제외한다.

Train은 road site14/31/74의 새 영상, validation은 다른 road의 새104번 영상이다. Map-only
기존265개 경로 기록·nonjunction42m·차로폭3.2m·heading15° 규칙을 유지한다. 다음 미사용
127번은 향후 quality holdout 후보로 예약하고 이번에 영상을 수집하지 않는다. Validation은
개발 자료이며 미래 quality holdout이 아니다. RGB/hash·site·road·scene family/episode lineage로
split을 봉인하고 무작위 frame 분할을 금지한다. 같은 Town이므로 지리적/전체 ODD 독립성은 아니다.

Person/bicycle/car/motorcycle은 train/validation의 blueprint 집합을 분리한다. Bus는 현재 호환
목록의 한 blueprint를 공유한다. Truck은 두 호환 blueprint를 공유해 새로운 시야/도로 전이를
측정할 자료를 만든다. 이 예외를 숨기거나 bus/truck 자산 독립 일반화를 주장하지 않는다.
22개 blueprint의8m·24m·4방향, 총176개 asset-preflight를 모델 없이 수집한다. 모든 blueprint는
8m의4방향에서 해당 semantic class와 이륜차 Rider13의25pixel/side4 지원이 있어야 한다.
24m의 지원 부족도 그대로 보고하며 그 자체를8m asset 호환성 실패로 세지 않는다.

각 실제 collection site는6class×3기상×4방향×3거리216장·부분 가림18장·같은 pose의 가림 없는
참조18장·negative3장,255장이다. 전체1020장(train765/validation255)을 계획한다.
기상은 ClearNoon/WetCloudyNoon/CloudySunset, 방향0/90/180/270°, 거리8/16/24m다.
Camera yaw±7°/0·높이15cm·pitch2°와 actor lateral/색을 결정적으로 바꾼다. Occluded/reference
쌍은 같은 camera/target pose를 유지한다. 모든 case/정답·실제 가시성은 그대로 보고하고
어려운 장면을 삭제하거나 모델 점수로 다시 고르지 않는다. 각 split의 class×기상×방향과
class×기상×거리에서25pixel/side4 target가 적어도1개 있어야 한다. Occlusion은 참조 대비
0초과/.95미만을 보고하고 class×기상마다 적어도1개를 요구한다. 계획 객체의 미지원/작은
fragment·rider 지원·negative의 실제 라벨도 전부 기록한다.

기존 RGB/instance640×384/FOV90/Epic/postprocess·world10ms·settle40/capture10/선택tick5,
physics-off·tick 전 staging과 실제 pose2cm/0.1°·road projection2m·clearance15cm를 유지한다.
Schema·plan/source hash를 RPC 전에 확인하며 startup180s·capture900s·shutdown30s와
exit130을 유지한다. 실패/부분 수집·시작/종료 판정은 원래 source/probe·raw/로그와 보존한다.

정답은 instance semantic12/13→person,19→bicycle,14→car,18→motorcycle,16→bus,15→truck이다.
기존 visible25pixel/side4 기준의 지원 여부를 별도로 기록한다. 학습용 export에는 작은 visible
fragment도 양성 라벨로 보존하고 quality_eligible=false로 표시한다. 작은 객체를 숨긴 채 배경
음성으로 만들지 않는다. 이를 기존 strict 품질 GT/점수 확장이나 수용 근거로 사용하지 않는다.
PNG는 원래 RGB byte를 손실 없이 복원해야 한다. COCO6개 category(1/2/3/4/6/8), visible xywh·
visible area·uncompressed RLE mask와 iscrowd=0을 내보낸다. 실제 crowd가 아닌 객체를 ignore를
위해 crowd로 바꾸지 않는다. 소비자는 명시한 category→native class 매핑과 작은 fragment 정책을
대조해야 하며 기존80-class 모델 학습/출력 계약이 자동 연결되는 것은 아니다.

모든 raw→RGB/instance/pose/정답·mask/COCO/PNG·지원 coverage·split/중복을 재구성한다.
고정 패널과 모든 RGB 건전성을 검수하고 새 경로 압축 해제로 재감사한다. 수집/정답 PASS와
모델 정확도·wall20Hz·M11/Target·차량 수용은 구분한다.

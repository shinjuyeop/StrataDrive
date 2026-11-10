# V8b 모델 없는 준비 revision

2026-11-10. 최초 Town04 준비는 개발99장 PASS, 보류99장의 보행자 가림3기상에서
visible ratio1.0으로 FAIL이다. 모든 계획 actor/Rider와 class×stratum support는 PASS였지만
가림 차량의 box가 보행자 왼쪽에서 끝나 실제 가림이 없었다. 모델 추론·새 평가·후보 점수는
아직 실행하지 않았다. 원래 source18개·계획·raw198쌍·정답·FAIL과 준비 실행기의 사전 경로
오류를 그대로 보존한다. 대기 중이던 품질 실행기는 준비 승인 flag 없이 종료한다.

모델 없는 geometry 수정으로 **holdout/occluded/person의 occluder right_m만 -0.6→-0.4m**
로 바꾼다. 보행자와 다른 actor의 위치·거리·종류·yaw·camera·기상·25pixel/side4·가림비율
<.95와 정확도 gate는 유지한다. 동일 새 template를 준비와 최종 평가에 사용한다.

별도 `quality_road_v8b.py`와 `*-v8b.json`을 추가한다. 기존 v8 source/profile은 수정하지 않는다.
양쪽99장씩을 새 source freeze 뒤 재수집하고 모두 다시 검사한다. 최초198개와 모든 추가
준비/거절 RGB를 최종 평가에서 제외한다. 새 준비도 실패하면 원래 FAIL을 유지한다.
지도/두 site·모델·학습/threshold·보드 최적화에는 변경이 없다.

이 revision은 [원래 V8 기준](perception-quality-v8-protocol.md)의 모델 추론 전 준비 수정
절차다. 모델 성능을 보고 보류를 조정하거나 실패를 PASS로 다시 표시하는 절차가 아니다.

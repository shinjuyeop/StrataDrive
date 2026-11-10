# V8 보류 준비의 별도 종료 실패 복구

2026-11-10. V8b holdout 준비 run02는99 RGB/instance pair·probe exit0·cleanup error0을
기록했으나 UE가 SIGINT 뒤30초 안에 종료되지 않아 forced-stop/exit-9로 **FAIL**이다.
로그에 exit130 요청이 있어도 실제 process 종료 결과를 성공으로 바꾸지 않는다. 해당99장은
정상 준비로 채택하지 않고 최종 평가 제외 목록에는 포함한다.

원래 자동 재시도 규칙은0frame 시작 실패만 허용하므로 이번 시도는 그 규칙에 포함하지 않는다.
실행 전에 별도 기록을 남기고 **동일 source20개·동일 V8b plan·startup180/capture900/
shutdown30s로 holdout 준비 run03을 한 번 추가**한다. 코드·모델·threshold·가시성/정확도
gate·지도/site·배치 변경은 없다. 정상 종료와 기존 준비 gate가 모두 PASS여야 채택한다.

원래 FAIL·raw99쌍·로그/clock·freeze를 그대로 보존한다. 이 복구가 성공하더라도 서버 종료
안정성 문제나 근본 원인 해결로 표시하지 않는다. 아직 새 모델 정확도 추론/평가는 실행하지 않았다.

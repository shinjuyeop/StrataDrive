# Power lifecycle 차량 SIL 후속

사전 범위는 PrechargeTimeout/RequestLost/ShutdownCurrentBlocked/StartupEnergized/
DischargeTimeout의 실제8-role logical Host10ms·공통 물리 모델 연결이다. 각 조건을 입력
복원만 하는15s와20s 명시적 새 INIT/Release 후24s까지 관측하는 두 경로로 실행한다.
신규 GTest5개×2경로이며 executable watchdog600s, Debug/ASan·UBSan/TSan 분리 판정이다.

기동 고장은 초기 Power runnable의 센서 사본에만 주입한다. PrechargeStall은 bus0을3s까지,
StartupEnergized는 positive 접점 true를200ms까지 유지한다. 실제 전기 모델과 source/sequence는
바꾸지 않는다. 주행 고장은9.9s의 정상 armed·DTC0을 선행 조건으로 한다. RequestLost는
기존 mailbox의 실제 Zone→Power 요청을10s부터200ms drop하며 ACK를 합성하지 않는다.
Shutdown 두 조건은10s 실제 Central protection 요청 뒤 Power 입력의 current20A를11.5s까지,
Discharging phase의 bus100V를12.5s까지 유지한다. 정지 요청이 고장 검출보다 먼저다.

기대 검출은 기존 Power state/phase origin과 원래 timeout을 따른다. 다른 detector가 먼저
보호를 선택하면 원래 순서를 보존하고, 도달하지 않은 고장 원인을 만들어내지 않는다.
물리 정지/HV-off와 durable DTC·복원만으로 Failed 유지·새 실제 HV Ready 뒤 Passed·자동
clear 없음까지 확인한다. 정상 시나리오의 generic result.passed를 고장 판정에 재사용하지 않고
각 조건의 native snapshot·canonical journal·물리/owner trace를 독립 감사한다.

센서 소비 사본/요청 전달의 고장 시험이며 실제 전기 부품의 모든 복합 고장·wall timing·CARLA
수용으로 확대하지 않는다. 원본 실패·source/binary·watchdog를 보존한다.

실행에서 RequestLost 조건은 상위 transaction/command expiry가 Power 자체 watchdog보다
먼저 보호한다. 원본 Front/Rear CommandLoss 두 DTC를 기록하며 Power에 존재하지 않는
자체 RequestLost/Passed를 만들지 않는다. 네 나머지 조건의 실제 Power reason/phase origin은
StartupEnergized0, Precharge4, CurrentBlocked8, Discharging10에서 확인한다. 원래 timeout은
각각 즉시 검사·2s·300ms·1s다. 독립 auditor는 실제 packet drop과 이 선행 순서를 검사한다.

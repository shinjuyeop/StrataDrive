# M10 Host 전원 제한의 최초 한 번 인증

반복 시험의 sudo 인증을 없애기 위한 별도 설치다. 새 물리 시험을 시작하거나 GC 문제를
해결하는 변경은 아니다. 원래 owner4 동결본·기한·물리 판정과 기존 수동 launcher는 유지한다.
추가 시험 전에 GC 내부 대기와 피드백 회복 경로를 더 좁히는 작업을 우선한다.

## 설치할 권한

사용자 `alswoghd`에게 아래 **단일 명령만** 비밀번호 없이 허용한다.

```sudoers
alswoghd ALL=(root) NOPASSWD: NOSETENV: /usr/local/sbin/stratadrive-m10-boost-lease
```

- `/usr/local/sbin/stratadrive-m10-boost-lease`: root:root0755인 고정 사본.
- `/etc/sudoers.d/stratadrive-m10-boost`: root:root0440인 전용 규칙.
- 기존 `m10_boost_lease.py`와 실행 본문이 동일하고 첫 줄만 `/usr/bin/python3 -I`로 바꾼다.
  작업 디렉터리·PYTHONPATH·사용자 site package를 root import 경로로 사용하지 않는다.
- 일반 Python·셸·작업 폴더의 변경 가능한 스크립트에 NOPASSWD를 부여하지 않는다.
  기존 전체 sudo 정책이나 인증 캐시 만료 시간은 변경하지 않는다.
- 이 명령은 원래 active Intel P-state/max100/turbo 조건을 확인하고 `max_perf_pct`만
  100→70으로 바꾼다. 호출 사용자 소유 PID와 시작 시각을 묶고 중복 lease를 금지한다.
  실행기 종료·SIGINT/SIGTERM/SIGHUP·최대1800초에 원래100으로 복원한다.
  다른 전원 값이 외부에서 바뀌면 덮어쓰지 않고 오류를 남기는 원래 동작도 유지한다.

인자는 PID와1–1800초 기간뿐이며 argparse가 다른 인자를 거절한다. PID는 호출 사용자
소유여야 한다. `--help`는 전원 값을 바꾸지 않는 권한 확인용이다. 설치 코드는 검토한
helper SHA256을 고정하고, root 소유가 아니거나 변경 가능한 경로·symlink·다른 기존 파일을
거절한다. `visudo` 문법 검증과 실제 사용자 UID의 `sudo -n -k ... --help` 검사를 수행한다.
`-k`는 이 명령에서 인증 캐시를 무시하므로 최초 설치 때 입력한 비밀번호에 기대지 않는다.
실패하면 이번 설치가 새로 만든 규칙·도구를 제거한다.

## 사용자 최초 설치

설치 내용을 읽기만 하는 명령:

```bash
python3 -I /d/shin/StrataDrive/tools/m10_install_host_lease.py --plan
```

실제 설치는 사용자 터미널에서 한 번 인증한다:

```bash
sudo /usr/bin/python3 -I /d/shin/StrataDrive/tools/m10_install_host_lease.py --install
```

`INSTALLED: passwordless helper verified; no trial started.`가 나오면 설치 완료다.
설치 자체는 전원 값을 바꾸거나 시험을 실행하지 않는다. 설치 이후 에이전트가 아래 점검과
승인된 시험을 비밀번호 입력 없이 수행한다. helper의 기능·권한 범위를 나중에 변경하면
다시 검토·설치 인증이 필요할 수 있다.

## 에이전트 실행

```bash
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc_unattended.py --check
python3 /d/shin/StrataDrive/tools/m10_start_owner_gc_unattended.py
```

`--check`는 기존 동결본과 설치된 helper의 권한·내용·NOPASSWD 사용 가능 여부만 확인한다.
실행 시에는 자산 준비 전과 후에 권한을 확인하고, 대화형 인증은 요청하지 않는다.
기존 수동 launcher와 같은 잠금을 잡고, 새 PID와 원래30초→30초→5분 sequence를 사용한다.
첫 실패 중단·원본 판정·runtime 복원은 기존 동결 실행기가 담당한다.
호출 코드·helper의 실제 바이트와 SHA256, 실행 결과는 해당 evidence series의
`automation-launches/launch-*/`에 별도 보존한다. 기존 동결 archive는 재작성하지 않는다.
기존 수동 `m10_start_owner_gc.py`는 이전 경로를 그대로 유지한다.

제거할 때는 실행 중인 lease가 없는 상태에서:

```bash
sudo /usr/bin/python3 -I /d/shin/StrataDrive/tools/m10_install_host_lease.py --remove
```

검토한 두 파일만 확인한 뒤 규칙부터 제거한다. 다른 sudo 권한은 바꾸지 않는다.

## 확인 범위

[준비 검증](evidence/m10_host_lease_automation_v1/validation.json)과
[검사 기록](evidence/m10_host_lease_automation_v1/tests.txt)을 따른다.
고정 helper·실제 visudo 문법·Python 격리·경로/소유권 거절·설치 실패 복구·제거 순서,
실제 일반 사용자 자식 PID·권한 취소·lease 실패 시 자식 정리 및 기존 lease 복원을 검사했다.
Root 설치·비밀번호 없는 실제 sudo 실행은 사용자의 최초 설치 뒤 확인한다.

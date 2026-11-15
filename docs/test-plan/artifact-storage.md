# 실험 산출물 보관·복원

GitHub에는 소스·실험 조건·판정 근거를 보관하고, 원본 카메라와 반복 생성되는 대형 실험 묶음은
로컬/외부 보관 대상으로 분리한다. 포트폴리오에서 결과와 한계를 읽을 수 있게 유지하되,
전체 raw 재감사에는 별도 원본이 필요하다는 점을 명시한다.

## 2026-11-15 추적 정리 범위

기준 커밋은 `b7623d273ba5bb79895162749468e6e7b212607b`다. 아래 수치는 현재 커밋의
LFS pointer에 기록된 논리적 payload 크기이며, 계정의 실제 청구 사용량을 측정한 값은 아니다.
GB는 1,000,000,000byte다.

| Git 추적 해제 대상 | 파일 수 | Payload GB |
| --- | ---: | ---: |
| M10 raw 카메라·tensor 압축 묶음 (`raw-*.tar`, `raw-*.tar.gz`) | 226 | 75.407 |
| M10 실험 전체 묶음 (`experiment*.tar.gz`) | 18 | 11.305 |
| M10 반복 실행 묶음 (`run.tar.gz`) | 30 | 0.398 |
| 초기 capture/exploratory/live/renderer 묶음 | 4 | 0.287 |
| 합계 | 278 | 87.397 |

이 중 LFS 파일은 266개/87,309,888,130byte이고, 일반 Git 파일은 12개/87,439,476byte다.
현재 커밋의 LFS 참조는 301개/90,791,123,366byte에서 35개/3,481,235,236byte로 줄어든다.
약 96.17%의 LFS payload가 이후 기본 checkout에서 빠진다. 같은 종류의 새 파일과 수정본을
추가할 때 발생할 LFS 업로드·다운로드 증가를 예방하는 효과다.

모든 대상은 `git rm --cached`로 인덱스에서만 제거한다. 로컬 파일·LFS object cache를 삭제하거나,
기존 커밋·tag·branch를 다시 쓰거나, 강제 푸시하지 않는다. 로컬 디스크 공간을 회수하는 작업도 아니다.

[제외 파일 목록](artifact-inventory.csv)은 경로·종류·이전 저장 방식·원본 크기·SHA256·로컬 상태를
기록한다. 정리 당시 212개는 payload가 있었고, 66개는 이전부터 LFS pointer만 있었다.
Pointer는 원본 백업이 아니다. 실제 원본이 없는 66개는 전체 raw 재현 전에 별도로 확보해야 한다.

## 유지한 자료

- 소스 코드·시험 runner·protocol·profile·설정과 고정 source snapshot (`sources*.tar.gz` 등).
- 결과 요약·PASS/FAIL·실패/timeout 기록·audit·manifest·원래 `SHA256SUMS`와 원본 식별자.
- 기존 텍스트/CSV/JSON·journal·핵심 제어 trace, 대표 PNG/JPEG와 학습 곡선.
- M8/M9 등 핵심 `trace.jsonl.gz` LFS 33개와 DXC 진단의 `libdxcompiler.so`,
  `build-reproduction.tar.gz` LFS 2개. 기존 M4–M9 source/검증/log 압축본도 유지한다.
- 제외할 압축본 안에만 있던 작은 설정·결과·기동/실패 로그·보조 script는 해당 evidence의
  `retained-metadata.tar.gz` 44개(총 15,363,671byte, 텍스트 2,063개)로 별도 보존한다.
  [보존 목록](retained-metadata.csv)의 크기·SHA로
  확인할 수 있다. 각 압축의 `MANIFEST.json`은 원본 archive/member·논리 경로·개별 SHA를 기록한다.
  이미지/모델/tensor payload와 중복 frozen-source/third-party 사본은 포함하지 않는다.

기존 증거의 bytes·timestamp·hash와 당시 판정은 수정하지 않는다. 새 metadata 묶음은 읽기·검토를
위한 부분 보존본이며, 원래 archive를 대체하거나 전체 replay 통과를 증명하지 않는다.

## 새 산출물과 재현 방법

새 실행은 기존처럼 무시되는 `build/`, `datasets/`, `data/` 또는 별도 로컬 저장소에 기록한다.
원본 BGRA/RGB, evidence의 raw/experiment/run 압축과 dataset camera 디렉터리는 `.gitignore`로 막고,
해당 생성 파일의 LFS 지정은 `.gitattributes`에서 제거한다. `git add -f`로 이 규칙을 우회하지 않는다.
새 결과를 공개할 때는 설정·명령·seed·환경·요약·실패 기록·대표 패널과 원본 해시를 선별한다.

1. 일반 코드 재실행은 루트 README와 CARLA/인지 실행 안내를 따른다. 환경·모델·CARLA는 별도 준비한다.
2. 새 clone에서 유지된 LFS 로그는 `git lfs pull`로 받는다. 이 명령은 이번에 제외한 원본을 복원하지 않는다.
3. 작은 metadata 묶음은 먼저 `tar -tzf <evidence>/retained-metadata.tar.gz`로 확인하고,
   별도 작업 디렉터리에 풀어 읽는다. 안의 `MANIFEST.json`으로 개별 파일을 검증한다.
4. 전체 원본 재감사는 로컬/외부 백업에서 제외 목록과 원래 manifest의 크기·SHA를 대조해,
   원래 evidence 상대 경로에 원본을 복원한 뒤 수행한다. 기존 검사기는 이 경로를 사용한다.
5. 필요한 원본이 모두 있는 경우에만 해당 디렉터리의 `sha256sum -c SHA256SUMS`와 원래
   `check-archive.py`/raw replay를 실행한다. 빠진 파일을 무시하고 전체 검사를 PASS로 표시하지 않는다.

현재 변경은 외부 보관 서비스를 만들거나 업로드하지 않는다. 외부 원본의 위치·접근권한·백업 검증은
별도로 정해야 하며, 로컬 원본을 지우기 전에 독립 백업과 복원 검사를 완료해야 한다.

## 기존 GitHub LFS 사용량의 후속 조치

이번 커밋의 **기존 서버 저장량 절감은 0GB**다. 과거 커밋의 pointer와 서버 LFS 객체는 남는다.
GitHub는 추적을 제거한 LFS 객체도 저장량에 계속 포함한다고 안내한다.
([GitHub LFS 제거 안내](https://docs.github.com/en/repositories/working-with-files/managing-large-files/removing-files-from-git-large-file-storage))

계정 Billing에서 실제 storage/bandwidth와 예산을 확인하고, 제외 목록·SHA와 원본 백업 현황을 준비해
GitHub Support에 객체 정리 가능 여부와 과거 커밋 재현에 미치는 영향을 문의한다. 지원 요청은 별도 작업이다.
Repository 삭제/재생성, history rewrite, force push는 이번 작업에 포함하지 않는다.
로컬 `git lfs prune`은 GitHub 저장량을 줄이지 않으며 원본 보존 요구 때문에 실행하지 않는다.
LFS 저장량·대역폭의 과금 방식은 [GitHub billing 안내](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)를 따른다.

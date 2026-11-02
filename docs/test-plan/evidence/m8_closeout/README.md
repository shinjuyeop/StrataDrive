# M8 제어기 기능 SIL 마감 기록

2026-11-02. **PASS_M8_CLOSEOUT_PROVENANCE**.
[종료 검토표](../../../archive/milestone-reviews.md#m8)와
[ADR-0076](../../../archive/design-decisions.md#adr-0076)에 따라 제어기·고정 fixture 기능 SIL을
마감한다. 전체 Reference/system TC·wall/Target 판정은 유지한다.

구현·원본 증거 commit `457260e9925c9df20140dbaaf2c1ceffc202756a`를 `origin/main`에
먼저 push한 뒤 문서를 정리했다. 이번 마감에서 production/test/config 변경이나
새 CARLA/CTest/Python runtime 시험은 하지 않았다.

| 검토 | 결과 |
| --- | --- |
| 기존 M8 원본 증거9묶음 | SHA256SUMS의1436파일 모두 일치 |
| 최종 검증 source 대조 | code/config/test553파일이 m8_stop30 최종 snapshot과 동일 |
| component 추적성 | C-M8-L/Y/R/A/T/U/V36행 유지·중복 없음 |
| 보존된 최종 실행 결과 | C++1217·Python237·영향 ASan/UBSan33 통과; 이번 재실행 아님 |
| 저장 형식 | trace18개 Git LFS 업로드 완료·로컬 LFS fsck OK; 원본 해시 유지 |
| Git index 사전 검토 | 원본1436파일의 byte hash 또는 LFS oid가 원본 SHA256과 일치 |
| 새 물리 실행 | 0회 |

[검증 결과](verification.json), [Git 전송 확인](publication.txt),
[문서 링크 검사](documentation-links.json)를 보존한다. 원본 S03 v1 성능 FAIL,
UE 종료 실패, 개발 build/test 실패, stop30의 첫 감사 집계 오류도 과거 그대로다.
정식32개 요구/29개 system TC는 NOT RUN이며 requirement/profile 수치는 바꾸지 않았다.

다음 작업은 [M9 시작 범위](../../../roadmap.md#m9-시작-범위)의 진단 계약·기존 fault 연결·
30km/h 고장별 통합이다. 마감 범위와 후속 이관을 명시했으며 미실행 고장 시험을
통과했다고 표시하지 않는다. 학습자의 설명 review는 기술 시험과 구분한다.

## 재현

원본 trace를 받기 위해 Git LFS를 설치한 뒤 저장소 root에서 실행한다.

```bash
git lfs pull
git lfs fsck
python3 docs/test-plan/evidence/m8_closeout/verify.py
```

`verify.py`는 이전9묶음의 SHA256, 최종 source와 현재 code/config/test, component ID,
기준 구현 commit의 ancestry를 읽기 전용으로 대조한다. 향후 코드를 바꾸면 마지막
검증 snapshot과의 차이를 거절하므로 변경된 범위의 새 검증 근거를 사용해야 한다.
이 디렉터리의 `SHA256SUMS`는 마감 기록 자체의 무결성 목록이다.

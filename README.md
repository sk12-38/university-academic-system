# Python Academic Information System

파이썬으로 구현한 CLI 기반 학사정보시스템 프로젝트입니다.

## Included

- `src/project.py`: 메인 실행 코드
- `data/academic_data.json`: 학생, 교수, 과목, 수강 데이터
- `scripts/adjust.py`: 개설교과목 데이터 보정 스크립트
- `notebooks/project.ipynb`: 작업용 노트북
- `docs/final-report.pdf`: 기말 프로젝트 보고서
- `docs/proposal.pdf`: 제안서
- `assets/`: GPA/성적 통계 예시 이미지

## Features

- 학생, 교수, 관리자 역할 분리
- 수강신청 및 수강취소
- 성적 입력 및 조회
- GPA 추이 시각화
- 성적 분포 시각화
- JSON 기반 데이터 저장/불러오기
- 정규표현식 검증, 예외처리, 데코레이터 기반 권한 제어

## Run

```bash
pip install -r requirements.txt
python src/project.py
```

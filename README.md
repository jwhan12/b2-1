# 나만의 용돈 기입장 프로그램 만들기

## 실행 방법

개발 환경 : Python 3.12.13  
제약 사항 : 표준 라이브러리만 사용, 외부 라이브러리 사용 금지

```bash
python3 --version
python3 -m budget_app <command> [options]
python3 -m budget_app --help
python3 -m budget_app add --help
```

## 저장 파일 위치·형식

기본 저장 위치는 실행 디렉터리의 `./data`입니다. 다른 위치를 사용하려면 각 명령 뒤에 `--data-dir 경로`를 지정합니다.   
저장 형식은 UTF-8 JSONL이며, 한 줄마다 JSON 객체 하나를 저장합니다.

| 파일 | 저장 내용 |
|---|---|
| `data/transactions.jsonl` | 거래 내역 |
| `data/categories.jsonl` | 카테고리 |
| `data/budgets.jsonl` | 월별 예산 |


## 파일 구조

```text
.
├── README.md                  # 실행 방법, 저장 형식, 명령 사용법
├── .gitignore                 # Git에서 제외할 파일 설정
├── budget_app/                # 용돈 기입장 애플리케이션
│   ├── __init__.py            # Python 패키지 선언
│   ├── __main__.py            # `python3 -m budget_app` 실행 진입점
│   ├── cli.py                 # 명령 인자 처리와 사용자 입출력
│   ├── decorators.py          # CLI 오류 처리 데코레이터
│   ├── errors.py              # 애플리케이션 오류 정의
│   ├── models.py              # 거래 및 요약 데이터 모델
│   ├── repositories.py        # JSONL 파일 읽기·쓰기와 저장소 관리
│   ├── services.py            # 거래, 카테고리, 예산 관련 비즈니스 로직
│   └── validators.py          # 날짜, 금액, 카테고리 등 입력값 검증
├── data/                      # 기본 데이터 저장 디렉터리
│   ├── transactions.jsonl     # 거래 내역
│   ├── categories.jsonl       # 카테고리 목록
│   └── budgets.jsonl          # 월별 예산
└── examples/
    └── sample_import.csv      # CSV 가져오기용 예시 파일
```


## 주요 명령 예시

```bash
# add: 거래 추가: 날짜, 타입, 카테고리, 금액, 메모, 태그를 순서대로 입력
python3 -m budget_app add

# list & search: 목록 및 검색
python3 -m budget_app list --limit 3
python3 -m budget_app search --from 2024-01-01 --to 2026-10-07 --category food --type expense --q 커피

# update & delete: 거래 수정 및 삭제
python3 -m budget_app update --id TX-cb3ae208ce4c4fa4b4705d4dcfae790b --amount 1500 --tags coffee
python3 -m budget_app delete --id TX-거래ID

# summary: 월별 요약 및 예산 관리
python3 -m budget_app summary --month 2026-10 --top 3
python3 -m budget_app budget set --month 2026-10 --amount 100000
python3 -m budget_app budget show --month 2026-10

# category: 카테고리 관리(add와 remove는 이름을 대화형으로 입력)
python3 -m budget_app category add
python3 -m budget_app category list
python3 -m budget_app category remove

# CSV 가져오기 및 내보내기
python3 -m budget_app import --from examples/sample_import.csv
python3 -m budget_app export --out examples/sample_import.csv --month 2024-01
python3 -m budget_app export --out examples/sample_import.csv --from 2026-10-03 --to 2026-10-04
```

## import/export CSV 스키마

CSV는 UTF-8 인코딩과 헤더를 사용합니다. 열 순서는 `date,type,category,amount,memo,tags`입니다. 가져오기에서는 처음 네 열이 필수이고 `memo`, `tags`는 선택입니다. 내보내기는 여섯 열을 모두 기록합니다.

| 열 | 필수 | 형식 |
|---|---|---|
| `date` | 예 | `YYYY-MM-DD` |
| `type` | 예 | `income` 또는 `expense` |
| `category` | 예 | 등록된 카테고리 이름 |
| `amount` | 예 | 양수 정수 |
| `memo` | 아니요 | 문자열 |
| `tags` | 아니요 | 쉼표로 구분한 태그 문자열 |

메모나 다른 필드에 쉼표, 따옴표, 줄바꿈이 있으면 CSV 규칙에 맞게 필드를 큰따옴표로 감쌉니다. 따옴표 자체는 두 번 써서 표시합니다.

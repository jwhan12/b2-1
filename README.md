# B2-1 콘솔 가계부

## 실행 방법

Python 3.10 이상이 필요합니다. `b2-1` 폴더로 이동한 뒤 실행하세요. 별도 라이브러리 설치는 필요하지 않습니다.

```bash
python --version
python -m budget_app <command> [options]
python -m budget_app --help
python -m budget_app add --help
```

## 저장 파일 위치·형식

기본 저장 위치는 실행 디렉터리의 `./data`입니다. 다른 위치를 사용하려면 각 명령 뒤에 `--data-dir 경로`를 지정하세요. 저장 형식은 UTF-8 JSONL이며, 한 줄마다 JSON 객체 하나를 저장합니다.

| 파일 | 저장 내용 |
|---|---|
| `data/transactions.jsonl` | 거래 내역 |
| `data/categories.jsonl` | 카테고리 |
| `data/budgets.jsonl` | 월별 예산 |

## 주요 명령 예시

```bash
# 거래 추가: 날짜, 타입, 카테고리, 금액, 메모, 태그를 순서대로 입력
python -m budget_app add

# 목록 및 검색
python -m budget_app list --limit 10
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal

# 거래 수정 및 삭제
python -m budget_app update --id TX-거래ID --amount 16000 --memo 새메모 --tags meal,work
python -m budget_app delete --id TX-거래ID

# 월별 요약 및 예산 관리
python -m budget_app summary --month 2024-01 --top 3
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app budget show --month 2024-01

# 카테고리 관리: add와 remove는 이름을 대화형으로 입력
python -m budget_app category add
python -m budget_app category list
python -m budget_app category remove

# CSV 가져오기 및 내보내기
python -m budget_app import --from examples/sample_import.csv
python -m budget_app export --out january.csv --month 2024-01
python -m budget_app export --out range.csv --from 2024-01-01 --to 2024-01-31
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

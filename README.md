# energinno-DB

신재생에너지·건물에너지 사업의 **경제성 분석에 쓰는 단가를 한 곳에서 관리**하는 저장소입니다.
전기·가스 요금, 신재생에너지 장비 단가, 기타 단가를 담습니다.

## 어떻게 굴러가나요

```
원본 자료(PDF·CSV)  →  JSON 데이터  →  Supabase(DB)  →  다른 앱에서 조회
  sources/             data/           supabase/        제안서·경제성분석 등
```

- **`data/` 안의 JSON이 원본(정답)** 입니다. 값이 바뀌면 여기부터 고칩니다.
- Git에 기록이 남으므로 **"언제 누가 어떤 단가를 왜 바꿨는지"가 그대로 요금 개정 이력**이 됩니다.
- Supabase는 다른 앱이 가져다 쓰기 편하라고 두는 **사본**입니다.

## 폴더 설명

| 폴더 | 내용 |
|---|---|
| `data/` | 단가 데이터 (JSON) — **여기가 원본** |
| `sources/` | 근거가 되는 원본 PDF·CSV. 파일명은 `시행일_종류` 형식 |
| `docs/` | 데이터 구조 설명서와 갱신 방법 |
| `scripts/` | 변환·검증·SQL 생성 도구 |
| `supabase/` | DB 테이블 정의(`migrations/`)와 데이터 적재용 SQL(`seed/`) |

## 지금 들어있는 데이터

| 항목 | 범위 | 상태 |
|---|---|---|
| 전기요금 (한전) | 종합요금표 **8개 시행일** (2023-05-16 ~ 2026-04-16), 각 16개 계약종별 | ✅ 5개는 원본 PDF와 숫자 전량 대조, 3개는 페이지 이미지 육안 대조 |
| 가스 도매요금 (가스공사) | 2026-09-01 기준 용도별 11건 | ✅ 원본 CSV 전량 변환 |
| 발전용 천연가스요금 | 2008-01 ~ 2022-12 월별 180건 | ✅ 원본 CSV 전량 변환 |
| 신재생에너지 장비 단가 | — | ⬜ 빈 템플릿 (자료 입력 대기) |
| 기타 단가 | — | ⬜ 빈 템플릿 (자료 입력 대기) |

위 데이터는 Supabase 프로젝트 **`jlaw80_DB`** (`qhnyrkbmkzhsgthcxoiw`, 도쿄 리전) 의
`pricing` 스키마에 그대로 올라가 있습니다. JSON 원본과 DB 내용이 한 칸도 다르지 않다는 것을
체크섬으로 확인했습니다 (`scripts/checksum.py`).

| 테이블 | 행수 |
|---|---:|
| `pricing.electricity_rate` | 2,587 (요금표 8부) |
| `pricing.gas_power_generation_monthly` | 180 |
| `pricing.gas_wholesale_price` | 11 |

나머지 요금표는 `sources/electricity/` 에 원본 그대로 보관돼 있습니다.
그중 **4부(2022-04-01, 2022-07-01, 2023-01-01, 2023-11-09)는 글자가 없는 이미지 PDF**라
사람이 옮겨 적어야 합니다. 현황은 `python3 scripts/read_kepco_tables.py --survey` 또는
[docs/HOW-TO-UPDATE.md](docs/HOW-TO-UPDATE.md) 의 체크리스트를 보세요.

## 자주 쓰는 명령

```bash
python3 scripts/validate.py              # 데이터 형식 점검 (고친 뒤 꼭 실행)
python3 scripts/verify_electricity.py    # 전기요금 숫자를 원본 PDF와 대조
python3 scripts/export_sql.py            # Supabase 에 넣을 SQL 다시 만들기
python3 scripts/convert_gas_csv.py       # 가스 CSV → JSON 다시 변환
python3 scripts/checksum.py              # DB 와 대조할 기대 체크섬 출력
python3 scripts/checksum.py --sql        # DB 에서 돌릴 대조 SQL 출력
python3 scripts/read_kepco_tables.py --survey   # 요금표 PDF 현황과 추출 가능 여부
```

## API 키 관리

API 키는 **절대 이 저장소에 커밋하지 않습니다.**
`.env.example` 을 복사해 `.env` 를 만들고 거기에만 넣으세요. `.env` 는 `.gitignore` 에 등록돼 있습니다.

```bash
cp .env.example .env
```

## 더 읽을 것

- [docs/DATA-MODEL.md](docs/DATA-MODEL.md) — 각 단가를 어떤 항목으로 저장하는지
- [docs/HOW-TO-UPDATE.md](docs/HOW-TO-UPDATE.md) — 요금이 바뀌었을 때 갱신하는 방법

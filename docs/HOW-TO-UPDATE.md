# 단가 갱신하는 방법

## 공통 순서

```
1. sources/ 에 근거 자료를 넣는다       (파일명: 시행일_종류)
2. data/ 의 JSON을 고친다
3. python3 scripts/validate.py          ← 형식 점검
4. python3 scripts/export_sql.py        ← Supabase용 SQL 다시 만들기
5. 커밋 & 푸시                           ← 변경 이력이 남는다
```

---

## 1. 전기요금이 개정됐을 때

한전은 보통 1년에 2~4회 요금표를 바꿉니다.

1. 한전 홈페이지에서 새 **전기요금표(종합)** PDF를 받습니다.
2. `sources/electricity/YYYY-MM-DD_종합.pdf` 로 이름을 바꿔 넣습니다. (시행일 기준)
3. 직전 연도 JSON을 복사해 `data/electricity/kepco_YYYY-MM-DD.json` 을 만듭니다.
4. 바뀐 숫자를 고칩니다.
5. 아래 두 가지를 **반드시** 돌립니다.

```bash
python3 scripts/validate.py
python3 scripts/verify_electricity.py
```

`verify_electricity.py` 가 "PDF에서 찾지 못한 값"을 알려주면 오타가 난 자리입니다.

> 💡 **요금표 PDF는 글자가 그림으로 박혀 있어서** 자동 추출만으로는 종별 이름을 알 수 없습니다.
> 숫자는 자동으로 뽑되, 어느 표가 어느 종별인지는 사람이 확인해야 합니다.
> Claude Code에게 "새 요금표 PDF 넣었으니 JSON 만들어줘"라고 하면 이 절차대로 처리합니다.

### 아직 데이터로 만들지 않은 요금표

`sources/electricity/` 에 원본은 있지만 JSON으로 옮기지 않은 요금표입니다.
과거 시점 경제성 재계산이 필요해지면 그때 추가하면 됩니다.

| 시행일 | 종합 | 주택용 고압 | 주택용 저압 |
|---|:--:|:--:|:--:|
| 2021-01-01 | ⬜ | ⬜ | ⬜ |
| 2022-04-01 | ⬜ | ⬜ | ⬜ |
| 2022-07-01 | ⬜ | ⬜ | ⬜ |
| 2022-10-01 | — | ⬜ | ⬜ |
| 2023-01-01 | ⬜ | ⬜ | ⬜ |
| 2023-05-16 | ⬜ | ⬜ | ⬜ |
| 2023-11-09 | ⬜ | ⬜ | ⬜ |
| 2024-01-01 | ⬜ | ⬜ | ⬜ |
| 2024-04-01 | ⬜ | — | — |
| 2024-07-01 | ⬜ | — | — |
| 2024-10-24 | ⬜ | — | — |
| 2025-01-01 | ⬜ | — | — |
| 2025-04-01 | ⬜ | — | — |
| **2026-04-16** | ✅ | — | — |

2026-04-16 요금표도 **3페이지(전기자동차 충전전력요금, 분산에너지 부족전력요금)는 아직 미포함**입니다.
3페이지 항목 중 일부는 "무기한 시행 유예 중"으로 표시돼 있어 적용 여부를 확인한 뒤 넣는 게 안전합니다.

---

## 2. 가스요금이 개정됐을 때

### 수동 (지금 방식)

1. 공공데이터포털에서 CSV를 받아 `sources/gas/` 에 넣습니다.
2. `scripts/convert_gas_csv.py` 안의 파일명을 새 파일로 바꿉니다.
3. 실행하면 `data/gas/` 에 JSON이 다시 만들어집니다.

```bash
python3 scripts/convert_gas_csv.py
python3 scripts/validate.py
```

> 원본 CSV가 **EUC-KR 인코딩**이라 그냥 열면 글자가 깨집니다.
> 변환 스크립트가 알아서 처리하므로 직접 고치지 마세요.

### 자동 수집 (API) — ⚠️ 아직 검증 전

`scripts/fetch_odcloud.py` 가 공공데이터포털 API로 최신 자료를 받아옵니다.
**다만 이 스크립트는 아직 실제 호출로 확인하지 못했습니다.** 작성 당시 개발 환경에서
`api.odcloud.kr` 접속이 막혀 있었기 때문입니다.

처음 쓸 때 준비할 것:

1. `.env` 에 `ODCLOUD_SERVICE_KEY_ENC` 를 채웁니다. (공공데이터포털 마이페이지 → 인증키)
2. data.go.kr 의 해당 데이터 페이지에서 **[오픈API] 탭 → 요청주소**를 확인합니다.
   `https://api.odcloud.kr/api/15129722/v1/uddi:abcd-1234` 라면
   `.env` 에 넣을 값은 `15129722/v1/uddi:abcd-1234` 입니다.
3. 먼저 요청 주소만 확인합니다.

```bash
python3 scripts/fetch_odcloud.py --dry-run
python3 scripts/fetch_odcloud.py
```

---

## 3. 신재생 장비·기타 단가를 추가할 때

`data/renewable-equipment/장비단가_YYYY.json` 의 `items` 배열에 추가합니다.
항목 설명은 [DATA-MODEL.md](DATA-MODEL.md) 3번 참고.

가장 흔한 실수 두 가지:

- **`cost_type` 을 빼먹는 것** — 자재비인지 설치비 포함인지 안 적으면 나중에 못 씁니다.
- **`slug` 를 매번 새로 만드는 것** — 같은 품목이면 `slug` 는 그대로 두고 `base_date` 만 바꿔야 연도별 추이가 쌓입니다.

엑셀로 정리된 단가표가 있으면 그대로 주시면 JSON으로 변환해 드립니다.

---

## 4. Supabase 에 반영하기

```bash
python3 scripts/export_sql.py
```

1. 처음 한 번만: Supabase 대시보드 → SQL Editor 에 `supabase/migrations/0001_init.sql` 붙여넣고 Run
2. 그 다음: `supabase/seed/` 안의 SQL 파일을 붙여넣고 Run

같은 SQL을 여러 번 실행해도 중복으로 쌓이지 않습니다(덮어쓰기 방식).

> 현재 계정의 Supabase 프로젝트 4개가 모두 **일시정지(INACTIVE)** 상태입니다.
> 대시보드에서 프로젝트를 되살리거나 새로 만든 뒤 적용하세요.

---

## 5. API 키를 다룰 때 지킬 것

- 키는 `.env` 에만 넣습니다. `.env` 는 `.gitignore` 에 있어 Git에 올라가지 않습니다.
- **채팅창·이슈·커밋 메시지에 키를 붙여넣지 않습니다.** 한 번 올라가면 기록에서 지우기 어렵습니다.
- 실수로 노출했다면 공공데이터포털 마이페이지에서 **인증키를 재발급**하세요.

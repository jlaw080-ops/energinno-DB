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
`python3 scripts/read_kepco_tables.py --survey` 로 현황을 볼 수 있습니다.

| 시행일 | 종합 | 주택용 고압 | 주택용 저압 | 비고 |
|---|:--:|:--:|:--:|---|
| 2021-01-01 | ⬜ | ⬜ | ⬜ | |
| 2022-04-01 | 🔴 | ⬜ | ⬜ | **이미지 PDF** |
| 2022-07-01 | 🔴 | ⬜ | ⬜ | **이미지 PDF** |
| 2022-10-01 | — | ⬜ | ⬜ | |
| 2023-01-01 | 🔴 | ⬜ | ⬜ | **이미지 PDF** |
| 2023-05-16 | ⬜ | ⬜ | ⬜ | |
| 2023-11-09 | 🔴 | ⬜ | ⬜ | **이미지 PDF** |
| 2024-01-01 | ⬜ | ⬜ | ⬜ | |
| 2024-04-01 | ⬜ | — | — | |
| 2024-07-01 | ⬜ | — | — | 교육용(을)·일반용(갑)Ⅱ·산업용 전부 다름 — 개별 추출 필요 |
| **2024-10-24** | ✅ | — | — | 농사용 외 2025-01-01 과 동일 |
| **2025-01-01** | ✅ | — | — | 농사용 외 2025-04-01 과 동일 |
| **2025-04-01** | ✅ | — | — | 산업용(을) 외 종별은 2026 요금표와 동일 |
| **2026-04-16** | ✅ | — | — | |

🔴 표시한 **4부는 글자가 하나도 없는 순수 이미지 PDF** 입니다.
숫자를 프로그램으로 뽑을 수 없어 페이지를 이미지로 띄워 사람이 옮겨 적어야 합니다.
한전 홈페이지에서 글자가 살아있는 판본을 다시 받을 수 있으면 그게 훨씬 빠르고 안전합니다.

2026-04-16·2025-04-01 요금표도 **3페이지(전기자동차 충전전력요금, 분산에너지 부족전력요금)는 미포함**입니다.
3페이지 항목 중 일부는 "무기한 시행 유예 중"으로 표시돼 있어 적용 여부를 확인한 뒤 넣는 게 안전합니다.

### ⚠️ 직전 연도 JSON을 복사할 때 반드시 확인할 것

요율 숫자만 보고 복사하면 틀립니다. 실제로 2025-04-01 을 만들 때 아래 두 가지가 달랐습니다.

| 항목 | 2025-04-01 | 2026-04-16 |
|---|---|---|
| 산업용(을) 봄·가을철 주말 할인 | **없음** | 신설 (토·일·공휴일 11~14시 50% 할인) |
| 여름철·봄가을철 중간부하 | 08~11, 12~13, 18~22시 | 08~15, 21~22시 |
| 여름철·봄가을철 최대부하 | 11~12, 13~18시 | 15~21시 |

그래서 복사한 뒤에는 **요율 숫자뿐 아니라 `definitions.time_zones` 와 `discounts` 도
해당 연도 요금표에서 다시 확인**해야 합니다.

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

쓰는 프로젝트는 **`jlaw80_DB`** 입니다.
<https://supabase.com/dashboard/project/qhnyrkbmkzhsgthcxoiw>

스키마(`pricing` 스키마와 표 6개)는 이미 적용돼 있고 데이터도 올라가 있습니다.
**단가를 고친 뒤** 아래 순서로 반영하면 됩니다.

```bash
python3 scripts/export_sql.py    # supabase/seed/ 의 SQL 다시 생성
```

1. Supabase 대시보드 → SQL Editor 를 엽니다.
2. `supabase/seed/` 에서 바뀐 데이터의 SQL 파일을 붙여넣고 Run 합니다.
   같은 SQL 을 여러 번 실행해도 중복으로 쌓이지 않습니다(덮어쓰기 방식).
3. 제대로 들어갔는지 대조합니다.

```bash
python3 scripts/checksum.py       # 기대 행수와 체크섬
python3 scripts/checksum.py --sql # 이 SQL 을 SQL Editor 에서 실행
```

두 결과의 **행수와 체크섬이 같으면** 값이 한 칸도 어긋나지 않고 들어간 것입니다.
다르면 그 데이터셋만 다시 넣으세요.

> 💡 SQL 이 너무 길어 한 번에 안 들어가면(특히 전기요금은 320행) 파일을 나눠서 실행해도 됩니다.
> `insert ... values` 한 덩어리를 중간에서 자르지만 않으면 됩니다.

### 다른 앱에서 REST API 로 읽으려면

`pricing` 스키마는 기본적으로 REST API 에 공개돼 있지 않습니다.
Project Settings → API → **Exposed schemas** 에 `pricing` 을 추가해야
다른 앱에서 `supabase.schema('pricing').from('electricity_rate')` 로 읽을 수 있습니다.

현재 권한은 **읽기는 누구나, 쓰기는 service_role 만** 으로 잡혀 있습니다.
단가는 공개 고시 자료라 읽기를 막을 이유가 없고, 쓰기는 서버에서만 하도록 한 것입니다.
service_role 키는 **브라우저에 노출하면 안 됩니다** (서버·빌드 환경변수로만 사용).

### 전기요금 계산에 쓰기 전에

`electricity_tariff_version.climate_charge_per_kwh` 와 `fuel_adjustment_per_kwh` 가
`null` 입니다. 요금표 PDF 에 단가가 없어서 비워둔 값입니다.
한전 공지에서 확인해 채워야 실제 요금이 계산됩니다.

```sql
update pricing.electricity_tariff_version
set climate_charge_per_kwh = 9.0,     -- 실제 공지 단가로 바꾸세요
    fuel_adjustment_per_kwh = 5.0     -- 분기마다 달라집니다
where effective_from = '2026-04-16';
```

## 5. API 키를 다룰 때 지킬 것

- 키는 `.env` 에만 넣습니다. `.env` 는 `.gitignore` 에 있어 Git에 올라가지 않습니다.
- **채팅창·이슈·커밋 메시지에 키를 붙여넣지 않습니다.** 한 번 올라가면 기록에서 지우기 어렵습니다.
- 실수로 노출했다면 공공데이터포털 마이페이지에서 **인증키를 재발급**하세요.

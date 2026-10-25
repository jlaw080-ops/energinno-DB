# 단가 꺼내 쓰는 방법

Supabase SQL Editor 에 붙여넣고 쓰는 예시입니다.
프로젝트는 `jlaw80_DB` (<https://supabase.com/dashboard/project/qhnyrkbmkzhsgthcxoiw>),
표는 모두 `pricing` 스키마 안에 있습니다.

---

## 1. 지금 적용되는 전기요금 보기

```sql
select contract_type as 종별, voltage as 전압, rate_option as 선택,
       basic_charge as 기본요금, season as 계절, time_zone as 시간대,
       energy_charge as "전력량요금(원/kWh)"
from pricing.electricity_rate_current
where contract_type = '일반용전력(을)'
order by voltage, rate_option, season, time_zone;
```

`electricity_rate_current` 뷰는 **오늘 기준 가장 최근 요금표**만 보여줍니다.
과거 시점으로 보려면 `electricity_rate` 를 `electricity_tariff_version` 과 조인해
`effective_from` 을 직접 고르세요.

## 2. 기후환경요금·연료비조정단가

```sql
select * from pricing.electricity_surcharge_current;
```

이 두 단가는 요금표와 따로 움직여서 별도 표에 있습니다.
**`source_type` 을 꼭 확인하세요.** `보도` 면 한전 공식 고시로 확인되지 않은 값입니다.

## 3. 전기요금 계산 (실제로 써먹는 예시)

일반용전력(을) 고압A 선택Ⅱ, 계약전력 300kW, 2026년 10월(봄·가을철),
경부하 20,000 / 중간부하 30,000 / 최대부하 15,000 kWh 를 쓴 경우입니다.
**조건 부분만 바꿔서 쓰면 됩니다.**

```sql
with 조건 as (
  select '2026-10-01'::date as 청구월, '일반용전력(을)' as 종별, '고압A' as 전압,
         '선택Ⅱ' as 선택, '봄·가을철' as 계절, 300 as 계약전력
), 사용량(time_zone, kwh) as (
  values ('경부하',20000),('중간부하',30000),('최대부하',15000)
), 버전 as (
  select v.* from pricing.electricity_tariff_version v, 조건 c
  where v.effective_from <= c.청구월
  order by v.effective_from desc limit 1
), 요율 as (
  select r.time_zone, r.energy_charge, r.basic_charge
  from pricing.electricity_rate r, 버전 v, 조건 c
  where r.version_id = v.id and r.contract_type = c.종별
    and r.voltage = c.전압 and r.rate_option = c.선택 and r.season = c.계절
), 단가 as (
  select max(case when kind='기후환경요금' then won_per_kwh end) as 기후환경,
         max(case when kind='연료비조정단가' then won_per_kwh end) as 연료비조정
  from pricing.electricity_surcharge_current
)
select (select published_label from 버전) as 적용요금표,
       (select max(basic_charge) from 요율) * (select 계약전력 from 조건) as 기본요금,
       (select sum(u.kwh * y.energy_charge) from 사용량 u join 요율 y using (time_zone)) as 전력량요금,
       (select sum(kwh) from 사용량) * (select 기후환경 from 단가) as 기후환경요금,
       (select sum(kwh) from 사용량) * (select 연료비조정 from 단가) as 연료비조정요금;
```

위 조건의 결과는 기본요금 2,496,000원 + 전력량요금 7,147,500원 +
기후환경요금 585,000원 + 연료비조정 325,000원 = **전기요금 10,553,500원** 입니다.

### ⚠️ 청구금액 반올림 — 파이썬 `round()` 를 쓰면 틀립니다

| 항목 | 규칙 |
|---|---|
| 부가가치세 | 전기요금 × 10%, **원 미만 4사5입** |
| 전력산업기반기금 | 전기요금 × 요율, **10원 미만 절사** |
| 청구금액 | 세 가지 합계에서 **10원 미만 절사** |

단순히 `× 1.127` 로 곱하면 실제 고지서와 몇 원 차이가 납니다.
그리고 **파이썬의 `round()` 는 4사5입이 아닙니다.** 은행가 반올림이라
`.5` 를 짝수 쪽으로 보냅니다.

```python
round(9588.5)                      # 9588  ← 틀림
from decimal import Decimal, ROUND_HALF_UP
int(Decimal('9588.5').quantize(Decimal('1'), rounding=ROUND_HALF_UP))   # 9589  ← 맞음
```

실제로 한전 요금표의 계산 예시(450kWh, 전기요금 95,885원)에서 부가가치세가
정확히 9,588.5원이라, 이 차이가 그대로 드러납니다. 한전 값은 **9,589원** 입니다.
SQL 에서는 `round()` 가 4사5입이라 그대로 쓰면 됩니다.

## 4. 주택용 복지할인

```sql
select target as 대상, discount_type as 구분,
       percent as "할인율(%)", monthly_cap as "월 한도(원)", summer_cap as "여름철 한도(원)"
from pricing.residential_welfare_discount
where effective_from = '2024-01-01'
order by discount_type, monthly_cap nulls last;
```

여름철은 6월 1일~8월 31일입니다.
기초생활수급자·차상위계층 장애할인은 정률할인(30%)과 **중복 적용**할 수 있습니다.

공동주택에서 계량기 하나를 여러 가구가 쓸 때의 산정 방법(1주택수가구)은
`data/electricity/주택용_복지할인.json` 의 `multi_household_single_meter` 에 있습니다.
가구별 평균사용량으로 누진단계를 적용해 누진 부담을 덜어주는 방식입니다.

## 5. ⚠️ 불완전한 시행일 — 빈 결과를 "요금 없음" 으로 읽지 마세요

종합요금표가 글자 없는 이미지 PDF 라서 **주택용만 확보한 시행일**이 3개 있습니다.

| 시행일 | 수록 종별 |
|---|---|
| 2022-04-01 | 주택용전력만 |
| 2022-10-01 | 주택용전력만 |
| 2023-11-09 | 주택용전력만 |

이 시점에 일반용·산업용을 조회하면 **빈 결과**가 나옵니다.
"그 종별 요금이 0원" 이 아니라 **"아직 데이터를 넣지 못함"** 입니다.
조회 전에 확인하세요.

```sql
select * from pricing.electricity_tariff_coverage;
```

```sql
-- 쓰려는 시점이 불완전한지 먼저 보기
select effective_from, published_label, is_partial, covered_contract_types
from pricing.electricity_tariff_version
where effective_from <= '2022-06-01'
order by effective_from desc limit 1;
```

## 6. 과거 시점 요금 계산 — ⚠️ 빠진 데이터 주의

요금표와 부가요금 모두 시계열이라 **과거 시점 요금도 계산됩니다.**
같은 건물·같은 사용량으로 연도를 바꿔 보면 인상 폭이 바로 보입니다.

| 청구월 | 적용 요금표 | 전력량요금 | 기후환경 | 연료비조정 | 전기요금 |
|---|---|---:|---:|---:|---:|
| 2021-06 | 2021-01-01 | 4,794,500 | 344,500 | (없음) | — |
| 2023-06 | 2023-05-16 | 7,147,500 | 585,000 | 325,000 | 10,553,500 |
| 2026-10 | 2026-04-16 | 7,147,500 | 585,000 | 325,000 | 10,553,500 |

> ⚠️ **`coalesce(..., 0)` 을 쓰지 마세요.**
> 부가요금은 확보하지 못한 구간이 있습니다(연료비조정단가 2022년 1분기 이전,
> 2024년 2분기 ~ 2025년 3분기, 2026년 2분기). 그 시점을 조회하면 값이 없는데,
> `coalesce` 로 0을 넣으면 **"0원이었다" 와 "모른다" 가 구별되지 않습니다.**
> 위 표의 2021-06 연료비조정이 바로 그 경우입니다. 실제로 2021년 연료비조정단가는
> 0원이 아니었습니다.
>
> 값이 없으면 `null` 이 나오게 두고, 아래처럼 **빠진 항목을 드러내세요.**

```sql
-- 특정 시점의 부가요금. 값이 없으면 '데이터 없음' 으로 표시한다.
with 시점 as (select '2021-06-01'::date as 청구월)
select k.kind as 구분,
       coalesce(x.effective_from::text, '— 데이터 없음 —') as 적용시행일,
       x.won_per_kwh as "원/kWh",
       x.source_type as 출처
from (values ('기후환경요금'),('연료비조정단가')) k(kind)
left join lateral (
  select * from pricing.electricity_surcharge s, 시점 t
  where s.kind = k.kind and s.effective_from <= t.청구월
  order by s.effective_from desc limit 1
) x on true;
```

## 7. 연도별 요금 추이 보기

```sql
select v.effective_from as 시행일, r.energy_charge as "전력량요금(원/kWh)"
from pricing.electricity_rate r
join pricing.electricity_tariff_version v on v.id = r.version_id
where r.contract_type = '일반용전력(을)' and r.voltage = '고압A'
  and r.rate_option = '선택Ⅱ' and r.season = '여름철' and r.time_zone = '최대부하'
order by v.effective_from;
```

농사용처럼 종별 하나만 계속 오른 경우도 이렇게 바로 보입니다.

```sql
select v.effective_from as 시행일, r.energy_charge as "원/kWh"
from pricing.electricity_rate r
join pricing.electricity_tariff_version v on v.id = r.version_id
where r.contract_type = '농사용전력' and r.voltage = '갑'
order by v.effective_from;
```

## 8. 가스요금

```sql
-- 용도별 도매요금 (원/MJ)
select sector as 구분, use_type as 용도, season as 계절, wholesale_price as 도매요금
from pricing.gas_wholesale_price
where effective_from = '2026-09-01' order by sector, use_type;

-- 발전용 천연가스요금 추이
select month as 연월, total_per_nm3 as "원/Nm3", total_per_gj as "원/GJ"
from pricing.gas_power_generation_monthly
where month >= '2020-01-01' order by month;
```

---

## 다른 앱에서 REST API 로 읽으려면

`pricing` 스키마는 기본적으로 API 에 공개돼 있지 않습니다.
Supabase 대시보드 → Project Settings → API → **Exposed schemas** 에 `pricing` 을 추가하세요.

```js
const { data } = await supabase
  .schema('pricing')
  .from('electricity_rate_current')
  .select('*')
  .eq('contract_type', '일반용전력(을)')
```

읽기는 누구나, 쓰기는 `service_role` 만 가능합니다.
`service_role` 키는 **브라우저에 노출하면 안 됩니다** (서버·빌드 환경변수로만 사용).

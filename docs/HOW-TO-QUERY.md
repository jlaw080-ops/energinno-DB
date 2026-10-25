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

> ⚠️ 청구금액을 낼 때 부가가치세는 **원 미만 4사5입**, 전력산업기반기금은
> **10원 미만 절사** 입니다. 단순히 `× 1.127` 로 곱하면 실제 고지서와 몇 원 차이가 납니다.
> 개략 추정에는 문제없지만, 실제 금액을 맞춰야 할 때는 각각 따로 반올림/절사하세요.

## 4. 연도별 요금 추이 보기

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

## 5. 가스요금

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

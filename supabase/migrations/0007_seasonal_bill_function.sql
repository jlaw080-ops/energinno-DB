-- 계절별 요금 계산 함수
--
-- 왜 필요한가
--   0005·0006 의 두 함수로는 15개 계약종별 중 다음을 계산할 수 없었다.
--
--     일반용전력(갑)Ⅰ   계절별   ← 중소규모 건물이 쓰는 가장 흔한 종별
--     산업용전력(갑)Ⅰ   계절별
--     교육용전력(갑)     계절별
--     심야전력(갑)       계절별   ← 축열식 난방
--     심야전력(을)Ⅰ     계절별   ← 축열식 난방
--
--   calc_demand_bill 에 넣으면 '시간대 요율이 3개가 아니라 0개' 예외가 난다.
--   (그렇게 설계한 것이다. 조용히 0원을 돌려주는 쪽이 훨씬 나쁘다)
--
-- 종별마다 계절 이름이 다르다
--   일반용·산업용·교육용 : 여름철 / 봄·가을철 / 겨울철
--   심야전력             : 겨울철 / 기타계절
--   그래서 계절을 명시하지 않으면 두 체계를 차례로 시도한다.
--   둘 다 없으면 '이 조합에 있는 계절' 목록을 담아 예외를 던진다.
--
-- 기본요금이 없는 종별
--   심야전력(갑)·(을)Ⅰ 은 기본요금 단가가 없고 전력량요금만 부과한다.
--   이때는 계약전력도 넘기지 않아야 한다(null). 한쪽만 주면 예외다.
--   '단가가 없으니 0원' 과 '자료가 빠져서 0원' 을 구별할 수 없으므로,
--   호출하는 쪽이 의도를 분명히 밝히게 만든 것이다.
--
-- 검증
--   한전이 인쇄해 둔 계산 예시가 이 종별에는 없다. 그래서 두 가지로 확인했다.
--
--   1) 손계산 대조
--      일반용(갑)Ⅰ 저압 100kW 10,000kWh 2026-07
--        기본 6,160 × 100        = 616,000
--        전력량 10,000 × 132.4   = 1,324,000
--        기후 9 × 10,000         = 90,000
--        연료 5 × 10,000         = 50,000
--        전기요금                = 2,080,000
--        부가세 10%              = 208,000
--        기금 2.7% (10원절사)    = 56,160
--        청구금액                = 2,344,160   ← 함수 결과와 일치
--
--   2) 선택Ⅰ/선택Ⅱ 손익분기점 (대수적 항등식 대조)
--      고압A 여름철은 선택Ⅰ(기본 7,170 / 전력량 142.6)과
--             선택Ⅱ(기본 8,230 / 전력량 138.6)이다.
--      기본요금 차 1,060원/kW ÷ 전력량요금 차 4.0원/kWh = 265kWh/kW 에서 교차해야 한다.
--      계약 100kW 로 확인한 결과 정확히 26,500kWh 에서 두 선택이 같아지고,
--      기울기도 100kWh 당 400원(=4.0원/kWh)으로 단가 차이와 맞았다.
--      요금표 숫자에서 유도한 값과 함수 결과가 일치하므로 산식이 맞다.
--
-- 적용 방법
--   create or replace 뿐이라 몇 번 실행해도 안전하다.
--   Supabase 대시보드 > SQL Editor 에 붙여넣고 Run 하면 된다.

create or replace function pricing.calc_seasonal_bill(
    contract_type   text,
    voltage         text,
    rate_option     text,     -- 저압·심야전력은 null
    contract_kw     numeric,  -- 기본요금이 없는 종별은 null
    billing_month   date,
    usage_kwh       numeric,
    season          text default null
) returns pricing.bill_breakdown
language plpgsql stable as $$
declare
    tv      record;
    cand1   text := case when extract(month from billing_month) between 6 and 8 then '여름철'
                         when extract(month from billing_month) in (11,12,1,2)   then '겨울철'
                         else '봄·가을철' end;
    cand2   text := case when extract(month from billing_month) in (11,12,1,2) then '겨울철'
                         else '기타계절' end;
    ssn     text;
    rate    record;
    avail   text;
    basic numeric; energy numeric; climate numeric; fuel numeric;
    elec numeric; vat numeric; fund numeric;
    warn text := null;
    out   pricing.bill_breakdown;
begin
    select * into tv
      from pricing.electricity_tariff_version tv2
     where tv2.effective_from <= billing_month
       and exists (select 1 from pricing.electricity_rate r
                    where r.version_id = tv2.id
                      and r.contract_type = calc_seasonal_bill.contract_type)
     order by tv2.effective_from desc limit 1;
    if tv is null then
        raise exception '% 시점에 적용할 % 요금표가 없습니다',
            billing_month, calc_seasonal_bill.contract_type;
    end if;

    -- 계절 이름이 종별마다 다르다. 명시하지 않으면 두 체계를 차례로 시도한다.
    ssn := coalesce(calc_seasonal_bill.season, cand1);
    select * into rate from pricing.electricity_rate r
     where r.version_id = tv.id
       and r.contract_type = calc_seasonal_bill.contract_type
       and r.voltage     is not distinct from calc_seasonal_bill.voltage
       and r.rate_option is not distinct from calc_seasonal_bill.rate_option
       and r.season = ssn and r.time_zone is null and r.tier is null;

    if rate is null and calc_seasonal_bill.season is null then
        ssn := cand2;
        select * into rate from pricing.electricity_rate r
         where r.version_id = tv.id
           and r.contract_type = calc_seasonal_bill.contract_type
           and r.voltage     is not distinct from calc_seasonal_bill.voltage
           and r.rate_option is not distinct from calc_seasonal_bill.rate_option
           and r.season = ssn and r.time_zone is null and r.tier is null;
    end if;

    if rate is null then
        select string_agg(distinct coalesce(r.season,'(없음)'), ', ') into avail
          from pricing.electricity_rate r
         where r.version_id = tv.id
           and r.contract_type = calc_seasonal_bill.contract_type
           and r.voltage     is not distinct from calc_seasonal_bill.voltage
           and r.rate_option is not distinct from calc_seasonal_bill.rate_option;
        raise exception '% / % / % 에 계절 % 요율이 없습니다. 이 조합에 있는 계절: %',
            calc_seasonal_bill.contract_type, calc_seasonal_bill.voltage,
            calc_seasonal_bill.rate_option, ssn, coalesce(avail, '(해당 조합 자체가 없음)');
    end if;

    -- 기본요금 단가가 없는 종별(심야전력(갑) 등)은 계약전력도 null 이어야 한다.
    -- 한쪽만 주어지면 조용히 0 원으로 넘기지 말고 예외를 던진다.
    if rate.basic_charge is null and contract_kw is null then
        basic := 0;
        warn := '이 종별은 기본요금 단가가 없다 (전력량요금만 부과)';
    elsif rate.basic_charge is null then
        raise exception '% 에는 기본요금 단가가 없는데 계약전력 % kW 를 주셨습니다. 계약전력을 비워 두세요',
            calc_seasonal_bill.contract_type, contract_kw;
    elsif contract_kw is null then
        raise exception '% 의 기본요금 단가는 % (단위 %) 입니다. 계약전력을 주셔야 계산됩니다',
            calc_seasonal_bill.contract_type, rate.basic_charge,
            coalesce(rate.basic_charge_unit, '없음');
    else
        basic := rate.basic_charge * contract_kw;
        if rate.basic_charge_unit is distinct from '원/kW' then
            warn := format('기본요금 단위가 %s 다. 계약전력을 곱하는 이 계산이 맞는지 확인이 필요하다',
                           rate.basic_charge_unit);
        end if;
    end if;

    energy := trunc(coalesce(usage_kwh,0) * rate.energy_charge);

    select s.won_per_kwh into climate from pricing.electricity_surcharge s
     where s.kind = '기후환경요금' and s.effective_from <= billing_month
     order by s.effective_from desc limit 1;
    select s.won_per_kwh into fuel from pricing.electricity_surcharge s
     where s.kind = '연료비조정단가' and s.effective_from <= billing_month
     order by s.effective_from desc limit 1;
    if climate is null then
        climate := 0;
        warn := concat_ws(' / ', warn, '기후환경요금 단가를 찾지 못해 0 으로 계산했다');
    end if;
    if fuel is null then
        fuel := 0;
        warn := concat_ws(' / ', warn, '연료비조정단가를 찾지 못해 0 으로 계산했다');
    end if;

    climate := trunc(climate * coalesce(usage_kwh,0));
    fuel    := trunc(fuel * coalesce(usage_kwh,0));
    elec    := basic + energy + climate + fuel;

    if tv.vat_rate is null then
        raise exception '% 요금표에 부가가치세율이 없습니다', tv.effective_from;
    end if;
    vat := round(elec * tv.vat_rate);                  -- 원미만 4사5입
    if tv.power_fund_rate is null then
        fund := 0;
        warn := concat_ws(' / ', warn,
            format('%s 요금표에 전력산업기반기금율이 없어 기금을 0원으로 뒀다. 청구금액이 실제보다 적다',
                   tv.effective_from));
    else
        fund := trunc(elec * tv.power_fund_rate / 10) * 10;   -- 10원미만 절사
    end if;

    warn := concat_ws(' / ', warn, '역률요금·수요관리 할인 등 부가 정산은 포함하지 않는다');

    out := (tv.published_label, tv.effective_from, ssn,
            basic, energy, climate, fuel, elec, vat, fund,
            trunc((elec + vat + fund) / 10) * 10, warn);
    return out;
end $$;


comment on function pricing.calc_seasonal_bill is
    '계절별 요금(일반용(갑)Ⅰ·산업용(갑)Ⅰ·교육용(갑)·심야전력) 계산. '
    '선택Ⅰ/Ⅱ 손익분기점(265kWh/kW)과 손계산으로 검증했다. '
    '역률요금과 각종 할인은 반영하지 않는다.';

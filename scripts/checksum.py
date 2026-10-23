#!/usr/bin/env python3
"""JSON 원본과 Supabase 에 적재된 내용이 같은지 체크섬으로 대조한다.

사용법:
    python3 scripts/checksum.py          # 기대값 출력
    python3 scripts/checksum.py --sql    # DB 에서 돌릴 SQL 출력

--sql 로 나온 SQL 을 Supabase SQL Editor 에서 실행한 뒤,
행수와 체크섬이 이 스크립트 출력과 같으면 값이 한 칸도 어긋나지 않고 들어간 것이다.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def pg(value) -> str:
    """Postgres 의 numeric::float8::text 와 같은 문자열로 맞춘다.

    format(v, 'g') 는 유효숫자 6자리에서 반올림해 36852.07 을 36852.1 로 만든다.
    repr() 은 왕복 가능한 최단 표기를 주므로 Postgres 출력과 일치한다.
    """
    if value is None:
        return ""
    text = repr(float(value))
    return text[:-2] if text.endswith(".0") else text


def digest(lines: list[str]) -> str:
    return hashlib.md5("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def electricity_lines(doc: dict) -> list[str]:
    lines = []
    for t in doc["tariffs"]:
        ct, rs = t["contract_type"], t["rate_structure"]
        for r in t["rates"]:
            volt = r.get("voltage") or r.get("class") or ""
            opt = r.get("option") or ""
            bc = r.get("basic_charge")
            for e in r.get("energy") or []:
                lines.append("|".join([ct, rs, volt, opt, e.get("season") or "",
                                       e.get("time_zone") or "", "", pg(bc), pg(e["charge"])]))
            for tier in r.get("tiers") or []:
                lines.append("|".join([ct, rs, volt, opt, r.get("season") or "", "",
                                       str(tier["tier"]), pg(tier["basic_charge"]),
                                       pg(tier["energy_charge"])]))
            if not (r.get("energy") or r.get("tiers")):
                lines.append("|".join([ct, rs, volt, opt, "", "", "", pg(bc), ""]))
    return lines


def gas_monthly_lines(doc: dict) -> list[str]:
    return ["|".join([s["month"], pg(s["feedstock_cost_won_per_nm3"]),
                      pg(s["supply_cost_won_per_nm3"]), pg(s["feedstock_cost_won_per_gj"]),
                      pg(s["supply_cost_won_per_gj"])]) for s in doc["series"]]


def gas_wholesale_lines(doc: dict) -> list[str]:
    return ["|".join([i["sector"], i["use"], i["season"], pg(i["feedstock_cost_won_per_mj"]),
                      pg(i["supply_cost_won_per_mj"]), pg(i["wholesale_price_won_per_mj"])])
            for i in doc["items"]]


SQL = """\
-- 전기요금
with canon as (
  select coalesce(contract_type,'')||'|'||coalesce(rate_structure,'')||'|'||
         coalesce(voltage,'')||'|'||coalesce(rate_option,'')||'|'||
         coalesce(season,'')||'|'||coalesce(time_zone,'')||'|'||
         coalesce(tier::text,'')||'|'||coalesce(basic_charge::float8::text,'')||'|'||
         coalesce(energy_charge::float8::text,'') as line
  from pricing.electricity_rate
)
select '전기요금' as 구분, count(*) as 행수, md5(string_agg(line, E'\\n' order by line)) as 체크섬
from canon
union all
-- 발전용 가스요금 월별
select '가스 월별', count(*), md5(string_agg(line, E'\\n' order by line)) from (
  select to_char(month,'YYYY-MM')||'|'||feedstock_cost_per_nm3::float8::text||'|'||
         supply_cost_per_nm3::float8::text||'|'||feedstock_cost_per_gj::float8::text||'|'||
         supply_cost_per_gj::float8::text as line
  from pricing.gas_power_generation_monthly) m
union all
-- 가스 도매요금
select '가스 도매요금', count(*), md5(string_agg(line, E'\\n' order by line)) from (
  select sector||'|'||use_type||'|'||season||'|'||feedstock_cost::float8::text||'|'||
         supply_cost::float8::text||'|'||wholesale_price::float8::text as line
  from pricing.gas_wholesale_price) w;"""

BUILDERS = {
    "kepco_electricity_tariff": ("전기요금", electricity_lines),
    "kogas_power_generation_monthly": ("가스 월별", gas_monthly_lines),
    "kogas_wholesale": ("가스 도매요금", gas_wholesale_lines),
}


def main() -> None:
    if "--sql" in sys.argv:
        print(SQL)
        return
    print(f"{'구분':<16} {'행수':>6}  체크섬")
    print("-" * 56)
    for path in sorted(DATA.rglob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        spec = BUILDERS.get(doc.get("meta", {}).get("dataset", ""))
        if not spec:
            continue
        label, build = spec
        lines = build(doc)
        print(f"{label:<16} {len(lines):>6}  {digest(lines)}")
    print("\nDB 쪽 값은 `python3 scripts/checksum.py --sql` 의 SQL 로 확인하세요.")


if __name__ == "__main__":
    main()

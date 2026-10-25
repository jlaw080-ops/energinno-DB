#!/usr/bin/env python3
"""data/ 의 JSON 단가를 Supabase 에 넣을 SQL(INSERT 문)로 변환한다.

사용법:
    python3 scripts/export_sql.py

supabase/seed/ 에 SQL 파일이 생긴다. Supabase 대시보드 > SQL Editor 에
0001_init.sql 을 먼저 실행한 뒤, 생성된 seed 파일을 붙여넣고 실행하면 된다.
같은 데이터를 다시 넣어도 중복되지 않도록 모두 덮어쓰기(upsert) 방식이다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "supabase" / "seed"


def q(value) -> str:
    """SQL 리터럴로 변환. 작은따옴표는 두 번 써서 escape 한다."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def row(values) -> str:
    return "  (" + ", ".join(q(v) for v in values) + ")"


def covered(doc: dict) -> str:
    """이 요금표가 담고 있는 계약종별 목록을 Postgres 배열 리터럴로."""
    kinds = sorted({t["contract_type"] for t in doc["tariffs"]})
    inner = ",".join('"' + k.replace('"', '\\"') + '"' for k in kinds)
    return "{" + inner + "}"


def rate_note(tariff: dict, rate: dict) -> str | None:
    """요율 한 줄에 함께 남겨둘 단서(월 최저요금, 슈퍼유저요금, 할인 등)."""
    parts: list[str] = []
    minimum = rate.get("minimum_monthly_charge")
    if minimum is not None:
        unit = rate.get("minimum_monthly_charge_unit") or ""
        parts.append(f"월 최저요금 {minimum:,.0f}{unit}")
    if tariff.get("minimum_monthly_charge_note"):
        parts.append(tariff["minimum_monthly_charge_note"])
    super_user = rate.get("super_user") or tariff.get("super_user")
    if super_user:
        parts.append(
            f"슈퍼유저요금: {super_user['condition']} {super_user['energy_charge']}원/kWh"
        )
    for discount in tariff.get("discounts") or []:
        parts.append(f"{discount['name']}: {discount['condition']} {discount['effect']}")
    return " / ".join(parts) or None


def electricity_sql(doc: dict) -> str:
    meta, tax, sur = doc["meta"], doc["taxes"], doc["surcharges"]
    eff = min(t["effective_from"] for t in doc["tariffs"])

    lines = [
        "-- 전기요금: " + meta["title"] + " (" + meta["published_label"] + ")",
        "-- 원본: " + meta["source_file"],
        "",
        "insert into pricing.electricity_tariff_version",
        "  (effective_from, published_label, provider, source_file,",
        "   vat_rate, power_fund_rate, climate_charge_per_kwh, fuel_adjustment_per_kwh,",
        "   is_partial, covered_contract_types, note)",
        "values",
        row([eff, meta["published_label"], meta["provider"], meta["source_file"],
             tax["vat_rate"], tax["power_industry_fund_rate"],
             sur["climate_charge_won_per_kwh"], sur["fuel_adjustment_won_per_kwh"],
             bool(meta.get("is_partial")), covered(doc),
             " ".join(x for x in (meta.get("effective_note"),
                                  meta.get("coverage_note"),
                                  meta.get("derivation_note")) if x) or None]),
        "on conflict (effective_from, source_file) do update set",
        "  published_label = excluded.published_label,",
        "  vat_rate = excluded.vat_rate,",
        "  power_fund_rate = excluded.power_fund_rate,",
        "  is_partial = excluded.is_partial,",
        "  covered_contract_types = excluded.covered_contract_types,",
        "  note = excluded.note;",
        "",
        "-- 같은 버전의 기존 요율을 지우고 다시 넣는다 (부분 수정 시 꼬이지 않도록)",
        "delete from pricing.electricity_rate where version_id in (",
        f"  select id from pricing.electricity_tariff_version",
        f"  where effective_from = {q(eff)} and source_file = {q(meta['source_file'])});",
        "",
        "insert into pricing.electricity_rate",
        "  (version_id, contract_type, rate_structure, contract_power, voltage, rate_option,",
        "   basic_charge, basic_charge_unit, basic_charge_formula,",
        "   season, time_zone, tier, usage_range, energy_label, energy_charge, note)",
        "select v.id, x.* from pricing.electricity_tariff_version v,",
        "(values",
    ]

    records = []
    for t in doc["tariffs"]:
        ct, rs, cp = t["contract_type"], t["rate_structure"], t.get("contract_power")
        for r in t["rates"]:
            volt = r.get("voltage") or r.get("class")
            opt = r.get("option")
            bc, bcu = r.get("basic_charge"), r.get("basic_charge_unit")
            bcf = r.get("basic_charge_formula")
            note = rate_note(t, r)
            for e in r.get("energy") or []:
                records.append([ct, rs, cp, volt, opt, bc, bcu, bcf,
                                e.get("season"), e.get("time_zone"), None, None, None,
                                e.get("charge"), note])
            for tier in r.get("tiers") or []:
                records.append([ct, rs, cp, volt, opt, tier.get("basic_charge"),
                                r.get("basic_charge_unit"), bcf,
                                r.get("season"), None, tier.get("tier"),
                                tier.get("usage_range"), tier.get("energy_label"),
                                tier.get("energy_charge"), note])
            if not (r.get("energy") or r.get("tiers")):
                records.append([ct, rs, cp, volt, opt, bc, bcu, bcf,
                                None, None, None, None, None, None, note])

    lines.append(",\n".join(row(rec) for rec in records))
    lines += [
        ") as x(contract_type, rate_structure, contract_power, voltage, rate_option,",
        "       basic_charge, basic_charge_unit, basic_charge_formula,",
        "       season, time_zone, tier, usage_range, energy_label, energy_charge, note)",
        f"where v.effective_from = {q(eff)} and v.source_file = {q(meta['source_file'])};",
        "",
    ]
    return "\n".join(lines), len(records)


def gas_wholesale_sql(doc: dict) -> tuple[str, int]:
    meta = doc["meta"]
    eff = meta["effective_from"]
    records = [[eff, i["sector"], i["use"], i["season"],
                i["feedstock_cost_won_per_mj"], i["supply_cost_won_per_mj"],
                i["wholesale_price_won_per_mj"], meta["source_file"]]
               for i in doc["items"]]
    sql = "\n".join([
        "-- 가스 도매요금: " + meta["title"] + f" ({eff} 기준)",
        "insert into pricing.gas_wholesale_price",
        "  (effective_from, sector, use_type, season,",
        "   feedstock_cost, supply_cost, wholesale_price, source_file)",
        "values",
        ",\n".join(row(r) for r in records),
        "on conflict (effective_from, sector, use_type, season) do update set",
        "  feedstock_cost = excluded.feedstock_cost,",
        "  supply_cost = excluded.supply_cost,",
        "  wholesale_price = excluded.wholesale_price;",
        "",
    ])
    return sql, len(records)


def gas_monthly_sql(doc: dict) -> tuple[str, int]:
    meta = doc["meta"]
    records = [[s["month"] + "-01",
                s["feedstock_cost_won_per_nm3"], s["supply_cost_won_per_nm3"],
                s["feedstock_cost_won_per_gj"], s["supply_cost_won_per_gj"],
                meta["source_file"]]
               for s in doc["series"]]
    sql = "\n".join([
        "-- 발전용 천연가스요금 월별: " + meta["period_start"] + " ~ " + meta["period_end"],
        "insert into pricing.gas_power_generation_monthly",
        "  (month, feedstock_cost_per_nm3, supply_cost_per_nm3,",
        "   feedstock_cost_per_gj, supply_cost_per_gj, source_file)",
        "values",
        ",\n".join(row(r) for r in records),
        "on conflict (month) do update set",
        "  feedstock_cost_per_nm3 = excluded.feedstock_cost_per_nm3,",
        "  supply_cost_per_nm3 = excluded.supply_cost_per_nm3,",
        "  feedstock_cost_per_gj = excluded.feedstock_cost_per_gj,",
        "  supply_cost_per_gj = excluded.supply_cost_per_gj;",
        "",
    ])
    return sql, len(records)


def surcharge_sql(doc: dict) -> tuple[str, int]:
    """기후환경요금·연료비조정단가 시계열."""
    records = []
    for kind, key in (("기후환경요금", "climate_charge"), ("연료비조정단가", "fuel_adjustment")):
        for r in doc.get(key, []):
            records.append([kind, r["effective_from"], r.get("period"), r["won_per_kwh"],
                            r["source"], r["source_type"], r["confidence"], r.get("note")])
    sql = "\n".join([
        "-- " + doc["meta"]["title"],
        "-- source_type 이 '보도' 인 값은 한전 공식 고시로 확인되지 않았다.",
        "insert into pricing.electricity_surcharge",
        "  (kind, effective_from, period_label, won_per_kwh, source, source_type, confidence, note)",
        "values",
        ",\n".join(row(r) for r in records),
        "on conflict (kind, effective_from) do update set",
        "  won_per_kwh = excluded.won_per_kwh,",
        "  source = excluded.source,",
        "  source_type = excluded.source_type,",
        "  confidence = excluded.confidence,",
        "  note = excluded.note;",
        "",
    ])
    return sql, len(records)


def price_list_sql(doc: dict, table: str, equipment: bool) -> tuple[str, int]:
    items = doc.get("items", [])
    if not items:
        return f"-- {doc['meta']['title']}: 아직 등록된 단가가 없습니다.\n", 0
    cols = ["slug", "category"] + (["subcategory"] if equipment else []) + \
           ["name", "spec"] + (["cost_type"] if equipment else []) + \
           ["unit_price", "price_unit"] + (["scope"] if equipment else []) + \
           ["base_date", "source", "source_type", "note"]
    records = [[i.get(c) for c in cols] for i in items]
    updates = ",\n".join(f"  {c} = excluded.{c}" for c in cols
                         if c not in ("slug", "base_date"))
    sql = "\n".join([
        f"-- {doc['meta']['title']}",
        f"insert into pricing.{table}",
        "  (" + ", ".join(cols) + ")",
        "values",
        ",\n".join(row(r) for r in records),
        "on conflict (slug, base_date) do update set",
        updates + ";",
        "",
    ])
    return sql, len(records)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for path in sorted(DATA.rglob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        dataset = doc.get("meta", {}).get("dataset", "")
        if dataset == "kepco_electricity_tariff":
            sql, n = electricity_sql(doc)
        elif dataset == "kogas_wholesale":
            sql, n = gas_wholesale_sql(doc)
        elif dataset == "kogas_power_generation_monthly":
            sql, n = gas_monthly_sql(doc)
        elif dataset == "renewable_equipment_price":
            sql, n = price_list_sql(doc, "renewable_equipment_price", True)
        elif dataset == "misc_price":
            sql, n = price_list_sql(doc, "misc_price", False)
        elif dataset == "kepco_electricity_surcharge":
            sql, n = surcharge_sql(doc)
        else:
            continue
        out = OUT / (path.stem + ".sql")
        out.write_text(sql, encoding="utf-8")
        total += n
        print(f"생성: {out.relative_to(ROOT)}  ({n}행)")
    print(f"합계 {total}행")


if __name__ == "__main__":
    main()

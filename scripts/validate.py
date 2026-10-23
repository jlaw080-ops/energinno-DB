#!/usr/bin/env python3
"""data/ 안의 모든 단가 JSON이 약속한 형식을 지키는지 점검한다.

사용법:
    python3 scripts/validate.py

단가를 수정한 뒤 커밋하기 전에 돌리면 형식 실수를 미리 잡을 수 있다.
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

VALID_SEASONS = {"여름철", "봄·가을철", "겨울철", "여름·겨울철", "하계", "기타계절", "연중", "단일요금", "동절기", "하절기", "기타월"}
VALID_TIME_ZONES = {"경부하", "중간부하", "최대부하", "심야시간", "기타시간"}
VALID_COST_TYPES = {"자재비", "설치비", "턴키(합계)"}

errors: list[str] = []
warnings: list[str] = []


def err(path: Path, msg: str) -> None:
    errors.append(f"{path.relative_to(ROOT)}: {msg}")


def warn(path: Path, msg: str) -> None:
    warnings.append(f"{path.relative_to(ROOT)}: {msg}")


def check_iso_date(path: Path, value: str, field: str) -> None:
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        err(path, f"{field} 가 YYYY-MM-DD 형식이 아닙니다: {value!r}")


def check_electricity(path: Path, doc: dict) -> None:
    meta = doc.get("meta", {})
    for field in ("dataset", "source_file", "currency"):
        if not meta.get(field):
            err(path, f"meta.{field} 가 없습니다")
    src = ROOT / meta.get("source_file", "")
    if meta.get("source_file") and not src.exists():
        err(path, f"원본 파일이 없습니다: {meta['source_file']}")

    seen_ids: set[str] = set()
    for tariff in doc.get("tariffs", []):
        tid = tariff.get("id")
        if not tid:
            err(path, "id 없는 종별이 있습니다")
        elif tid in seen_ids:
            err(path, f"id 중복: {tid}")
        else:
            seen_ids.add(tid)
        if tariff.get("effective_from"):
            check_iso_date(path, tariff["effective_from"], f"{tid}.effective_from")
        if not tariff.get("rates"):
            err(path, f"{tid}: rates 가 비어 있습니다")
        for rate in tariff.get("rates", []):
            for e in rate.get("energy") or []:
                s, z = e.get("season"), e.get("time_zone")
                if s and s not in VALID_SEASONS:
                    err(path, f"{tid}: 모르는 계절값 {s!r}")
                if z and z not in VALID_TIME_ZONES:
                    err(path, f"{tid}: 모르는 시간대값 {z!r}")
                if not isinstance(e.get("charge"), (int, float)):
                    err(path, f"{tid}: charge 가 숫자가 아닙니다 ({e})")
            for tier in rate.get("tiers") or []:
                if not isinstance(tier.get("energy_charge"), (int, float)):
                    err(path, f"{tid}: energy_charge 가 숫자가 아닙니다 ({tier})")

    if doc.get("surcharges", {}).get("climate_charge_won_per_kwh") is None:
        warn(path, "기후환경요금 단가가 비어 있습니다 (한전 공지에서 채워야 전기요금 계산 가능)")
    if doc.get("surcharges", {}).get("fuel_adjustment_won_per_kwh") is None:
        warn(path, "연료비조정단가가 비어 있습니다 (분기마다 바뀜)")


def check_gas(path: Path, doc: dict) -> None:
    meta = doc.get("meta", {})
    if "series" in doc:
        series = doc["series"]
        months = [s["month"] for s in series]
        if len(months) != len(set(months)):
            err(path, "month 중복이 있습니다")
        if months != sorted(months):
            err(path, "month 가 오름차순이 아닙니다")
        for s in series:
            total = round(s["feedstock_cost_won_per_nm3"] + s["supply_cost_won_per_nm3"], 2)
            if abs(total - s["total_won_per_nm3"]) > 0.01:
                err(path, f"{s['month']}: 원/Nm3 합계가 맞지 않습니다")
        if meta.get("record_count") != len(series):
            err(path, "meta.record_count 와 실제 건수가 다릅니다")
    if "items" in doc and meta.get("dataset") == "kogas_wholesale":
        for i in doc["items"]:
            total = round(i["feedstock_cost_won_per_mj"] + i["supply_cost_won_per_mj"], 4)
            if abs(total - i["wholesale_price_won_per_mj"]) > 0.0001:
                err(path, f"{i['sector']}/{i['use']}: 원료비+공급비 != 도매요금")
            if i["season"] not in VALID_SEASONS:
                err(path, f"모르는 계절값 {i['season']!r}")


def check_price_list(path: Path, doc: dict, equipment: bool) -> None:
    required = {"slug", "category", "name", "unit_price", "price_unit", "base_date"}
    if equipment:
        required.add("cost_type")
    seen: set[tuple] = set()
    for item in doc.get("items", []):
        missing = required - item.keys()
        if missing:
            err(path, f"{item.get('slug', '?')}: 필수 항목 누락 {sorted(missing)}")
            continue
        check_iso_date(path, item["base_date"], f"{item['slug']}.base_date")
        if not isinstance(item["unit_price"], (int, float)):
            err(path, f"{item['slug']}: unit_price 가 숫자가 아닙니다")
        if equipment and item["cost_type"] not in VALID_COST_TYPES:
            err(path, f"{item['slug']}: cost_type 은 {sorted(VALID_COST_TYPES)} 중 하나여야 합니다")
        key = (item["slug"], item["base_date"])
        if key in seen:
            err(path, f"slug+base_date 중복: {key}")
        seen.add(key)
    if not doc.get("items"):
        warn(path, "items 가 비어 있습니다 (아직 단가 자료를 넣지 않은 템플릿)")


def main() -> None:
    files = sorted(DATA.rglob("*.json"))
    if not files:
        sys.exit("data/ 에 JSON 파일이 없습니다.")

    for path in files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(path, f"JSON 문법 오류: {exc}")
            continue
        dataset = doc.get("meta", {}).get("dataset", "")
        if dataset == "kepco_electricity_tariff":
            check_electricity(path, doc)
        elif dataset.startswith("kogas"):
            check_gas(path, doc)
        elif dataset == "renewable_equipment_price":
            check_price_list(path, doc, equipment=True)
        elif dataset == "misc_price":
            check_price_list(path, doc, equipment=False)
        else:
            err(path, f"meta.dataset 값을 알 수 없습니다: {dataset!r}")

    print(f"검사한 파일 {len(files)}개")
    for w in warnings:
        print(f"  [참고] {w}")
    if errors:
        print(f"\n✗ 오류 {len(errors)}건")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("✓ 형식 오류 없음")


if __name__ == "__main__":
    main()

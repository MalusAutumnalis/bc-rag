"""
Собирает уникальные значения группирующих полей (talents.category,
psychic_powers.discipline, [gearType, entryType] для chems/gear/instrument)
из полного JSON, пишет человекочитаемый отчёт и дозаполняет target_map.yaml
новыми ключами (со значением null), не трогая уже заполненные вами строки.

Запуск:
    python list_categories.py <путь_к_json>
"""
import sys
import json
import yaml
from collections import Counter
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
TARGET_MAP_PATH = SKILL_DIR / "target_map.yaml"
REPORT_PATH = SKILL_DIR / "categories_report.md"


def _items(block):
    if isinstance(block, dict) and "items" in block:
        return block["items"]
    if isinstance(block, list):
        return block
    return []


def collect(json_path: str):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    talent_categories = Counter(
        item.get("category", "—") for item in _items(data.get("talents", []))
    )
    # только discipline — subdiscipline не участвует в группировке файлов,
    # используется позже как H4-заголовок внутри файла дисциплины
    spell_disciplines = Counter(
        item.get("discipline") or "null" for item in _items(data.get("psychic_powers", []))
    )
    gear_entry_types = {
        cat: Counter(
            (item.get("gearType", "—"), item.get("entryType", "—"))
            for item in _items(data.get(cat, []))
        )
        for cat in ("chems", "gear", "instrument")
    }
    return talent_categories, spell_disciplines, gear_entry_types


def write_report(talent_cats, spell_disc, gear_entry_types):
    lines = ["# Отчёт по категориям (сгенерировано автоматически)\n"]

    lines.append("## talents.category\n")
    for cat, count in sorted(talent_cats.items(), key=lambda x: -x[1]):
        lines.append(f"- `{cat}` — {count}")

    for cat in ("chems", "gear", "instrument"):
        lines.append(f"\n## {cat}: gearType / entryType\n")
        for (gt, et), count in sorted(gear_entry_types[cat].items(), key=lambda x: -x[1]):
            lines.append(f"- `{gt}` / `{et}` — {count}")

    lines.append("\n## psychic_powers.discipline\n")
    for disc, count in sorted(spell_disc.items(), key=lambda x: -x[1]):
        lines.append(f"- `{disc}` — {count}")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Отчёт записан: {REPORT_PATH}")


def update_target_map(talent_cats, spell_disc, gear_entry_types):
    target_map = yaml.safe_load(TARGET_MAP_PATH.read_text(encoding="utf-8"))

    talents_map = target_map.setdefault("talents", {}).setdefault("map", {})
    for cat in talent_cats:
        talents_map.setdefault(cat, None)

    spells_map = target_map.setdefault("psychic_powers", {}).setdefault("map", {})
    # чистим устаревшие ключи в формате "disc|sub", если остались с прошлой схемы
    stale_spell_keys = [k for k in spells_map if "|" in k]
    for k in stale_spell_keys:
        del spells_map[k]
    if stale_spell_keys:
        print(f"  psychic_powers: удалены устаревшие ключи 'discipline|subdiscipline': {stale_spell_keys}")
    for disc in spell_disc:
        spells_map.setdefault(disc, None)

    for cat in ("chems", "gear", "instrument"):
        target_map.setdefault(cat, {})
        target_map[cat].pop("default_target", None)
        cat_map = target_map[cat].setdefault("map", {})

        stale_keys = [k for k in cat_map if "|" not in k]
        for k in stale_keys:
            del cat_map[k]
        if stale_keys:
            print(f"  {cat}: удалены устаревшие ключи без 'gearType|entryType': {stale_keys}")

        for gt, et in gear_entry_types[cat]:
            cat_map.setdefault(f"{gt}|{et}", None)

    TARGET_MAP_PATH.write_text(
        yaml.safe_dump(target_map, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"target_map.yaml дополнен новыми ключами: {TARGET_MAP_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python list_categories.py <путь_к_json>")
        sys.exit(1)

    talent_cats, spell_disc, gear_entry_types = collect(sys.argv[1])
    write_report(talent_cats, spell_disc, gear_entry_types)
    update_target_map(talent_cats, spell_disc, gear_entry_types)
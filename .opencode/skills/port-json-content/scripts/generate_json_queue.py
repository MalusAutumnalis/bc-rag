"""
Строит/обновляет json_porting_queue.yaml — по одной строке на каждую единицу
контента из включённых категорий JSON, с целевым файлом, подставленным из
target_map.yaml. Прогресс уже начатых записей (status != not_started) не
теряется при повторном запуске.

Запуск:
    python generate_json_queue.py <путь_к_json>
"""
import sys
import json
import yaml
from pathlib import Path

def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("Не найден корень репозитория (pyproject.toml)")

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "ingest"))
from json_source import load_entries  # noqa: E402

SKILL_DIR = Path(__file__).parent.parent
TARGET_MAP_PATH = SKILL_DIR / "target_map.yaml"
QUEUE_PATH = SKILL_DIR / "json_porting_queue.yaml"


def resolve_target(entry, target_map: dict) -> str | None:
    cat = entry.category

    if cat == "talents":
        return target_map["talents"]["map"].get(entry.raw.get("category", "—"))

    if cat == "psychic_powers":
        disc = entry.raw.get("discipline") or "null"
        return target_map["psychic_powers"]["map"].get(disc)

    if cat in ("chems", "gear", "instrument"):
        gear_type = entry.raw.get("gearType", "—")
        entry_type = entry.raw.get("entryType", "—")
        return target_map[cat]["map"].get(f"{gear_type}|{entry_type}")

    if cat in target_map:
        return target_map[cat].get("default_target")

    return None


def build_queue(json_path: str):
    target_map = yaml.safe_load(TARGET_MAP_PATH.read_text(encoding="utf-8"))
    entries = load_entries(json_path)  # исключённые категории уже отфильтрованы

    existing = {}
    if QUEUE_PATH.exists():
        for row in yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or []:
            existing[(row["category"], row["key"])] = row

    queue = []
    counts = {"not_started": 0, "needs_target": 0, "kept": 0}
    for entry in entries:
        prior = existing.get((entry.category, entry.key))
        if prior and prior.get("status") not in (None, "not_started", "needs_target"):
            # запись уже в работе/завершена — не перетираем прогресс,
            # но обновляем target на случай, если маппинг поменялся
            prior["target"] = resolve_target(entry, target_map)
            queue.append(prior)
            counts["kept"] += 1
            continue

        target = resolve_target(entry, target_map)
        status = "not_started" if target else "needs_target"
        counts[status] += 1
        queue.append({
            "category": entry.category,
            "key": entry.key,
            "name_ru": entry.raw.get("name"),
            "target": target,
            "status": status,
            "notes": "",
        })

    QUEUE_PATH.write_text(
        yaml.safe_dump(queue, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Очередь: {len(queue)} записей -> {QUEUE_PATH}")
    print(f"  not_started: {counts['not_started']}")
    print(f"  needs_target (заполните target_map.yaml): {counts['needs_target']}")
    print(f"  сохранён прогресс: {counts['kept']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python generate_json_queue.py <путь_к_json>")
        sys.exit(1)
    build_queue(sys.argv[1])
"""
Сбрасывает статус записей в json_porting_queue.yaml обратно на not_started.
Используется, когда агент пометил записи как done/needs_review, но
реально не перенёс контент (или перенёс с ошибкой) — чтобы прогнать их
заново, не трогая руками весь yaml.

Способы отбора записей для сброса (можно комбинировать):
  --category talents              — все записи категории
  --target "путь/к/файлу.md"       — все записи с этим target
  --keys "Chomper,Escape Artist"   — конкретные записи по key (через запятую)
  --status done                   — только записи в этом статусе (по умолчанию:
                                     done и needs_review, не трогает already
                                     not_started/needs_target)

Запуск:
    uv run python reset_queue_status.py --category talents
    uv run python reset_queue_status.py --target "iii продвижение/таланты/4. избегание.md"
    uv run python reset_queue_status.py --keys "Chomper,Escape Artist,Flip"
"""
import argparse
import yaml
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
QUEUE_PATH = SKILL_DIR / "json_porting_queue.yaml"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--keys", default=None, help="через запятую")
    parser.add_argument(
        "--status", default=None,
        help="сбрасывать только записи с этим текущим статусом (по умолчанию: done и needs_review)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="только показать, что будет сброшено, не менять файл",
    )
    args = parser.parse_args()

    if not any([args.category, args.target, args.keys]):
        raise SystemExit("Укажите хотя бы один из фильтров: --category, --target, --keys")

    key_filter = set(k.strip() for k in args.keys.split(",")) if args.keys else None
    resettable_statuses = {args.status} if args.status else {"done", "needs_review"}

    queue = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or []

    matched = []
    for row in queue:
        if row["status"] not in resettable_statuses:
            continue
        if args.category and row["category"] != args.category:
            continue
        if args.target and row.get("target") != args.target:
            continue
        if key_filter and row["key"] not in key_filter:
            continue
        matched.append(row)

    if not matched:
        print("Ничего не найдено по заданным фильтрам.")
        return

    print(f"Найдено {len(matched)} записей для сброса:")
    by_target = {}
    for row in matched:
        by_target.setdefault(row.get("target"), []).append(row["key"])
    for target, keys in by_target.items():
        print(f"  [{target}] {len(keys)} записей: {', '.join(keys[:5])}{' ...' if len(keys) > 5 else ''}")

    if args.dry_run:
        print("\n--dry-run: файл не изменён.")
        return

    for row in matched:
        row["status"] = "not_started"
        row["notes"] = ""

    QUEUE_PATH.write_text(
        yaml.safe_dump(queue, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\nСброшено {len(matched)} записей -> not_started. {QUEUE_PATH}")


if __name__ == "__main__":
    main()
"""
Готовит черновик для батч-обработки одной категории (или одного target-файла)
из json_porting_queue.yaml — выгружает сырые поля, специфичные под шаблон
категории (см. "Шаблоны вывода" в SKILL.md), сгруппированные по target.

Текстовые поля НЕ адаптируются этим скриптом — только выгружаются как есть.
Адаптацию по dictionary.yaml и проверку на Chaos-маркеры агент выполняет
сам, читая draft построчно, запись за записью.

Запуск:
    python batch_prepare.py <json_path> <category> [--target <путь_к_файлу>]

Вывод — YAML в stdout, сгруппированный по target:
    <target_file_1>:
      - key: ...
        <поля шаблона категории>
    <target_file_2>:
      - key: ...
        ...
"""
import sys
import argparse
import yaml
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("Не найден корень репозитория (pyproject.toml)")

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "ingest"))
from json_source import load_entries  # noqa: E402

SKILL_DIR = Path(__file__).parent.parent
QUEUE_PATH = SKILL_DIR / "json_porting_queue.yaml"


# Какие поля из raw-объекта нужны под шаблон каждой категории (см. SKILL.md,
# раздел "Шаблоны вывода"). Порядок — как в шаблоне, для удобства чтения.
_CATEGORY_FIELDS = {
    "talents": ["nameEn", "name", "level", "aptitude", "requirements", "description"],
    "traits": ["nameEn", "name", "description"],
    "skills": ["nameEn", "name", "characteristic", "description", "action"],
    "psychic_powers": [
        "nameEn", "name", "discipline", "subdiscipline", "requirements",
        "action", "sustain", "psychotest", "range", "powerType", "description",
    ],
    "chems": ["nameEn", "name", "gearType", "entryType", "description", "intake", "effect", "postEffect", "quality"],
    "gear": ["nameEn", "name", "gearType", "entryType", "description", "quality"],
    "instrument": ["nameEn", "name", "gearType", "entryType", "description", "quality"],
}


def load_queue_index(category: str) -> dict[str, dict]:
    """key -> queue row, только status == not_started для данной категории."""
    if not QUEUE_PATH.exists():
        raise SystemExit(f"Не найден {QUEUE_PATH}. Сначала запустите generate_json_queue.py")
    rows = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or []
    return {
        r["key"]: r for r in rows
        if r["category"] == category and r["status"] == "not_started" and r.get("target")
    }


def extract_fields(raw: dict, fields: list[str]) -> dict:
    return {f: raw.get(f) for f in fields if f in raw or f in ("requirements", "aptitude", "powerType")}


def build_draft(json_path: str, category: str, target_filter: str | None = None) -> dict:
    if category not in _CATEGORY_FIELDS:
        raise SystemExit(
            f"Неизвестная или неподдерживаемая категория: {category}. "
            f"Поддерживаются: {', '.join(_CATEGORY_FIELDS)}"
        )

    queue_index = load_queue_index(category)
    if not queue_index:
        print(f"Нет записей not_started для категории '{category}' с заполненным target.", file=sys.stderr)
        return {}

    entries = load_entries(json_path, include_excluded=True)
    fields = _CATEGORY_FIELDS[category]

    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        if entry.category != category:
            continue
        queue_row = queue_index.get(entry.key)
        if queue_row is None:
            continue  # не not_started, или нет target — пропускаем
        target = queue_row["target"]
        if target_filter and target != target_filter:
            continue

        block = {"key": entry.key, **extract_fields(entry.raw, fields)}
        grouped.setdefault(target, []).append(block)

    return grouped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("category", choices=list(_CATEGORY_FIELDS))
    parser.add_argument("--target", default=None, help="Ограничить одним target-файлом")
    args = parser.parse_args()

    grouped = build_draft(args.json_path, args.category, args.target)
    if not grouped:
        print("Пусто.", file=sys.stderr)
        sys.exit(0)

    total = sum(len(v) for v in grouped.values())
    print(f"# {total} записей, {len(grouped)} целевых файлов", file=sys.stderr)
    print(yaml.safe_dump(grouped, allow_unicode=True, sort_keys=False, width=100))


if __name__ == "__main__":
    main()
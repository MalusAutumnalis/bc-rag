"""
Сравнивает таблицы атаки психосил в файлах вики с полем weaponProfile
в исходном JSON. Ничего не правит — только строит отчёт с готовой строкой
таблицы для вставки. Правки вносятся вручную (агентом через str_replace),
чтобы не сломать форматирование вики (двойные пробелы в конце строк).

Источник истины — ТОЛЬКО weaponProfile. description/effect в JSON и текст
в .md на генерируемую таблицу не влияют.

Запуск:
    uv run python find_gaps.py <путь_к_json>

Вывод — YAML в stdout, сгруппированный по target-файлу вики, только записи
с category != "ok".
"""
import re
import sys
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
from config import load_sources  # noqa: E402

TARGET_MAP_PATH = REPO_ROOT / ".opencode/skills/port-core-rules/target_map.yaml"

HEADING_RE = re.compile(r'^######\s+(.+?)\s*/\s*(.+?)\s*$', re.MULTILINE)
TABLE_ROW_RE = re.compile(r'^\|.*\|\s*$', re.MULTILINE)
EMBEDDED_RAW_RE = re.compile(r'Rng\s+Dmg\s+Pen\s+Свойства', re.IGNORECASE)

DASH = "–"  # en-dash, как в существующих таблицах оружия


def norm_rof_part(v) -> str:
    v = (v or "").strip()
    if v in ("", "-", "—", "–"):
        return DASH
    return v


def build_rof(wp: dict) -> str:
    parts = [
        norm_rof_part(wp.get("rofSingle")),
        norm_rof_part(wp.get("rofShort")),
        norm_rof_part(wp.get("rofLong")),
    ]
    return "\\".join(parts)


def build_pen(wp: dict) -> str:
    pen = wp.get("pen")
    if pen in (None, "", "0", 0):
        return "0"
    return str(pen)


def build_properties(wp: dict) -> str:
    props = [p for p in (wp.get("properties") or []) if p and p.strip()]
    return ", ".join(props) if props else DASH


def build_dmg(wp: dict) -> str:
    dmg = (wp.get("damage") or "").strip()
    dtype = (wp.get("damageType") or "").strip()
    return f"{dmg} {dtype}".strip()


def build_table(wp: dict) -> str:
    rng = (wp.get("range") or "").strip()
    rof = build_rof(wp)
    dmg = build_dmg(wp)
    pen = build_pen(wp)
    props = build_properties(wp)
    return (
        "| Rng | RoF | Dmg | Pen | Свойства |\n"
        "|-----|-----|-----|-----|----------|\n"
        f"| {rng} | {rof} | {dmg} | {pen} | {props} |"
    )


def normalize_table_text(text: str) -> str:
    """Схлопывает пробелы для сравнения существующей таблицы с ожидаемой."""
    lines = [re.sub(r'\s+', ' ', ln.strip()) for ln in text.strip().splitlines()]
    return "\n".join(ln for ln in lines if ln)


def find_block(md_text: str, name_en: str) -> str | None:
    """Возвращает текст блока от заголовка ###### {name_en} / ... до следующего ###### или конца файла."""
    lines = md_text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m and m.group(1).strip().lower() == name_en.strip().lower():
            start_idx = i
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if HEADING_RE.match(lines[j]):
            end_idx = j
            break
    return "\n".join(lines[start_idx:end_idx])


def extract_existing_table(block: str) -> str | None:
    """Ищет markdown-таблицу с заголовком Rng внутри блока."""
    m = re.search(r'(\|[^\n]*Rng[^\n]*\|\n\|[-:\s|]+\|\n(?:\|.*\|\n?)+)', block)
    return m.group(1).strip() if m else None


def classify(entry_key: str, block: str | None, wp: dict) -> tuple[str, str]:
    expected = build_table(wp)
    if block is None:
        return "block_not_found", expected
    if EMBEDDED_RAW_RE.search(block):
        return "embedded_raw_stats", expected
    existing = extract_existing_table(block)
    if existing is None:
        return "missing", expected
    if normalize_table_text(existing) != normalize_table_text(expected):
        return "outdated", expected
    return "ok", expected


def has_weapon_profile(raw: dict) -> bool:
    wp = raw.get("weaponProfile")
    if not wp:
        return False
    return bool((wp.get("damage") or "").strip())


def main():
    if len(sys.argv) != 2:
        print("Использование: python find_gaps.py <путь_к_json>", file=sys.stderr)
        sys.exit(1)

    json_path = sys.argv[1]
    target_map = yaml.safe_load(TARGET_MAP_PATH.read_text(encoding="utf-8"))
    spells_map = target_map["psychic_powers"]["map"]

    sources = load_sources()
    wiki_root = Path(sources["homebrew_path"])
    if not wiki_root.is_absolute():
        wiki_root = REPO_ROOT / wiki_root

    entries = [
        e for e in load_entries(json_path, include_excluded=True)
        if e.category == "psychic_powers" and has_weapon_profile(e.raw)
    ]

    md_cache: dict[str, str] = {}
    report: dict[str, list[dict]] = {}
    counts = {"ok": 0, "missing": 0, "outdated": 0, "embedded_raw_stats": 0,
              "block_not_found": 0, "no_target": 0}

    for entry in entries:
        disc = entry.raw.get("discipline") or "null"
        target = spells_map.get(disc)
        if not target:
            counts["no_target"] += 1
            continue

        full_path = wiki_root / target
        if target not in md_cache:
            md_cache[target] = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        md_text = md_cache[target]

        block = find_block(md_text, entry.key)
        category, expected_table = classify(entry.key, block, entry.raw["weaponProfile"])
        counts[category] += 1

        if category == "ok":
            continue

        report.setdefault(target, []).append({
            "key": entry.key,
            "name": entry.raw.get("name"),
            "category": category,
            "expected_table": expected_table,
        })

    print(f"# Всего с weaponProfile: {len(entries)}", file=sys.stderr)
    for k, v in counts.items():
        print(f"#   {k}: {v}", file=sys.stderr)

    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False, width=120))


if __name__ == "__main__":
    main()
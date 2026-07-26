"""
Сканирует целевые .md файлы на предмет #Review и обновляет
json_porting_queue.yaml: для талантов меняет not_started -> done/needs_review.
"""
import re
import yaml
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
QUEUE_PATH = SKILL_DIR / "json_porting_queue.yaml"
WIKI_ROOT = Path("D:/Work/Pet/pathfinder-crusade-wiki")

# Ищем вхождения #Review в интервале от заголовка таланта до следующего
# заголовка того же уровня (######) или конца файла
HEADING_RE = re.compile(r'^######\s+(.+?)\s*/\s*(.+?)\s*$', re.MULTILINE)
REVIEW_RE = re.compile(r'#Review')

def find_review_for_key(filepath: Path, name_en: str, name_ru: str) -> bool:
    """True, если блок таланта содержит #Review."""
    text = filepath.read_text(encoding="utf-8")
    # Ищем открывающий заголовок
    # name_en в файле может быть как в merged.json (key), а name_ru — как в очереди
    # Паттерн: ###### <name_en> / <name_ru>
    # Но name_ru в файле может отличаться от name_ru в очереди (адаптация).
    # Ищем только по name_en (первая часть до /)
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            # Сравниваем name_en — берем то что до /
            file_name_en = m.group(1).strip().lower()
            # name_en в файле может быть с артефактами вроде лишних пробелов
            # Сравниваем нормализованно
            if file_name_en == name_en.strip().lower():
                start_idx = i
                break

    if start_idx is None:
        # Не нашли — возможно талант не попал в этот файл (пропущен)
        return False

    # Скан от start_idx до следующего ###### или конца файла
    for j in range(start_idx + 1, len(lines)):
        if HEADING_RE.match(lines[j]):
            break
        if REVIEW_RE.search(lines[j]):
            return True
    return False


def main():
    rows = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or []
    changed = 0
    skipped = 0
    not_found = 0
    for r in rows:
        if r["category"] != "talents" or r["status"] != "not_started":
            continue
        target = r.get("target")
        if not target:
            continue
        filepath = WIKI_ROOT / target
        if not filepath.exists():
            # некоторые файлы не были созданы (например из-за пропуска)
            # значит запись не была обработана
            skipped += 1
            continue

        name_en = r["key"]
        name_ru = r.get("name_ru", "")
        has_review = find_review_for_key(filepath, name_en, name_ru)
        if has_review is None:
            not_found += 1
            continue

        r["status"] = "needs_review" if has_review else "done"
        changed += 1

    QUEUE_PATH.write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False, width=10000, default_style=''),
        encoding="utf-8",
    )
    print(f"Обновлено: {changed} записей")
    print(f"Не найдено в файлах: {not_found}")
    print(f"Пропущено (файл отсутствует): {skipped}")


if __name__ == "__main__":
    main()

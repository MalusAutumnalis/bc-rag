"""
Точечный поиск одной записи в JSON по категории и имени (nameEn),
для использования агентом на шаге переноса конкретной единицы контента.

Запуск:
    python find_entry.py <путь_к_json> <категория> <фрагмент_имени>
"""
import sys
import json
from pathlib import Path

def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("Не найден корень репозитория (pyproject.toml)")

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "ingest"))
from json_source import load_entries  # noqa: E402


def find_entry(json_path: str, category: str, name_query: str) -> str:
    matches = [
        e for e in load_entries(json_path, include_excluded=True)
        if e.category == category and name_query.lower() in e.key.lower()
    ]
    if not matches:
        return f"Ничего не найдено: {category} / {name_query}"
    return "\n\n===\n\n".join(
        json.dumps(m.raw, ensure_ascii=False, indent=2) for m in matches
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Использование: python find_entry.py <json> <категория> <фрагмент_имени>")
        sys.exit(1)
    print(find_entry(sys.argv[1], sys.argv[2], sys.argv[3]))
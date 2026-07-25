# ingest/json_source.py
"""
Загружает плоские записи из основного JSON книги правил для индексации
в RAG и для точечного поиска при переносе в вики.

Система "поклонение богу меняет цену таланта/навыка" не используется —
поля god/rivalGod/alliedTo/hostileTo намеренно НЕ включаются ни в текст
для эмбеддинга, ни в перенос. Если понадобятся в будущем — доставать из
entry.raw напрямую, здесь их специально нет.
"""
import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class JsonEntry:
    category: str    # "talents", "traits", "psychic_powers", ...
    key: str          # nameEn — используется как id и часть heading_path
    text: str          # плоский текст для эмбеддинга
    raw: dict          # исходный объект — для скрипта переноса/адаптации


# Поля, которые тянем в текст для эмбеддинга. God-поля намеренно исключены.
_TEXT_FIELDS = {
    "skills": ["name", "description", "action"],
    "talents": ["name", "description", "action", "requirements"],
    "traits": ["name", "description"],
    "chems": ["name", "description", "effect", "postEffect"],
    "instrument": ["name", "description"],
    "gear": ["name", "description"],
    "psychic_powers": ["name", "description"],
}

# Категории, которые вообще не индексируются как источник для переноса
# (см. category_policy.yaml — держим списки синхронизированными вручную)
_EXCLUDED_CATEGORIES = {
    "elite_archetypes", "implants", "tech_powers", "power_shield",
    "steeds", "ranged", "melee", "armour", "characteristics",
}


def _flatten(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(_flatten(v) for v in value if v)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_flatten(v)}" for k, v in value.items() if v)
    return "" if value is None else str(value)


def load_entries(json_path: str | Path, include_excluded: bool = False) -> list[JsonEntry]:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    out = []
    for category, block in data.items():
        if not include_excluded and category in _EXCLUDED_CATEGORIES:
            continue
        if category not in _TEXT_FIELDS:
            # неизвестная/непереносимая категория — пропускаем молча,
            # чтобы не индексировать implants/tech_powers/etc по ошибке
            continue

        items = block["items"] if isinstance(block, dict) and "items" in block else (
            block if isinstance(block, list) else []
        )
        fields = _TEXT_FIELDS[category]
        for item in items:
            key = item.get("nameEn") or item.get("name") or "unknown"
            text = "\n".join(_flatten(item[f]) for f in fields if item.get(f))
            out.append(JsonEntry(category=category, key=key, text=text, raw=item))
    return out


if __name__ == "__main__":
    import sys
    entries = load_entries(sys.argv[1])
    print(f"Загружено {len(entries)} записей из включённых категорий")
    by_cat = {}
    for e in entries:
        by_cat[e.category] = by_cat.get(e.category, 0) + 1
    for cat, count in sorted(by_cat.items()):
        print(f"  {cat}: {count}")
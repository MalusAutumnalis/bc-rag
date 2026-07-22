# ingest/chunker.py
import re
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Chunk:
    text: str
    heading_path: str   # "Раса > Орк > Vicious Strikes"
    source_file: str
    source_type: str    # "core" | "homebrew"

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)

def split_by_headings(text: str, max_chars: int = 1800):
    """Разбивает по заголовкам, копит стек уровней, не рвёт таблицы/datatable."""
    positions = [(m.start(), len(m.group(1)), m.group(2).strip())
                 for m in HEADING_RE.finditer(text)]
    positions.append((len(text), 0, None))

    stack = []  # [(level, title)]
    chunks = []
    for i in range(len(positions) - 1):
        start, level, title = positions[i]
        end = positions[i + 1][0]
        body = text[start:end].strip()

        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = " > ".join(t for _, t in stack)

        # если блок огромный (например длинная datatable) — не рвём её насильно,
        # просто оставляем целиком, для правил точность важнее равномерного размера
        chunks.append((path, body))
    return chunks

def chunk_file(path: Path, source_type: str) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    out = []
    for heading_path, body in split_by_headings(text):
        if not body.strip():
            continue
        out.append(Chunk(
            text=body,
            heading_path=heading_path or path.stem,
            source_file=str(path),
            source_type=source_type,
        ))
    return out
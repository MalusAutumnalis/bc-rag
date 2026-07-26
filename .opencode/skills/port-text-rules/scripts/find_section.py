import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "ingest"))
from chunker import split_by_headings

def find_section(core_md_path: str, heading_query: str) -> str:
    text = Path(core_md_path).read_text(encoding="utf-8")
    matches = []
    for heading_path, body in split_by_headings(text):
        if heading_query.lower() in heading_path.lower():
            matches.append((heading_path, body))
    if not matches:
        return f"Ничего не найдено по запросу: {heading_query}"
    return "\n\n===\n\n".join(f"## {hp}\n{body}" for hp, body in matches)

if __name__ == "__main__":
    print(find_section(sys.argv[1], sys.argv[2]))
import re
import yaml
from pathlib import Path

def load_dictionary():
    path = Path(__file__).parent.parent / "dictionary.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def apply_invariant(text: str, entries: list[dict]) -> str:
    for entry in entries:
        pattern = re.escape(entry["from"])
        text = re.sub(rf"\b{pattern}\b", entry["to"], text)
    return text

def process_file(path: Path, entries: list[dict]):
    text = path.read_text(encoding="utf-8")
    new_text = apply_invariant(text, entries)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"Изменён: {path}")

if __name__ == "__main__":
    d = load_dictionary()
    wiki_root = Path("../pathfinder-crusade-wiki")  
    for md_file in wiki_root.rglob("*.md"):
        process_file(md_file, d["invariant"])
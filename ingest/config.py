import yaml
from pathlib import Path

def load_sources():
    cfg = yaml.safe_load(Path(__file__).parent.parent.joinpath("sources.yaml").read_text())
    return cfg
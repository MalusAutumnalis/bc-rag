import re
import sys
import threading
import time
from pathlib import Path

import pymorphy3
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    LayoutOptions,
)
from docling.datamodel.layout_model_specs import DOCLING_LAYOUT_HERON_101
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_pipeline_options() -> PdfPipelineOptions:
    opts = PdfPipelineOptions()
    opts.layout_options = LayoutOptions(model_spec=DOCLING_LAYOUT_HERON_101)
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE
    opts.table_structure_options.do_cell_matching = True
    return opts


def build_converter(use_fallback_backend: bool = False) -> DocumentConverter:
    fmt_kwargs = {"pipeline_options": build_pipeline_options()}
    if use_fallback_backend:
        fmt_kwargs["backend"] = PyPdfiumDocumentBackend
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(**fmt_kwargs)}
    )

morph = pymorphy3.MorphAnalyzer()

def dehyphenate(text: str) -> str:
    def try_join(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        candidate = left + right
        parses = morph.parse(candidate)
        if parses and parses[0].is_known:
            return candidate
        return m.group(0)  # оставляем как есть — вероятно составное слово или имя собственное

    text = re.sub(r"(\w+) -(\w+)", try_join, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def extract_failed_pages(result) -> list[int]:
    """Парсит result.errors в поисках номеров пропущенных страниц."""
    pages = set()
    for err in getattr(result, "errors", []) or []:
        msg = str(err)
        for m in re.finditer(r"pages?\s*\[([\d,\s]+)\]", msg):
            for num in m.group(1).split(","):
                num = num.strip()
                if num.isdigit():
                    pages.add(int(num))
    return sorted(pages)


class Heartbeat:
    """Раз в 30 сек печатает 'жив', раз настоящего прогресс-бара по страницам нет."""
    def __init__(self, interval=30):
        self.interval = interval
        self._stop = threading.Event()
        self._t0 = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            print(f"  ...ещё работаю ({int(time.time() - self._t0)} сек прошло)")

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()


def convert_pdf(pdf_path, out_dir: str = "data/core_rules"):
    pdf_path = Path(pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = PROJECT_ROOT / pdf_path
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")

    out = Path(out_dir)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    conv = build_converter()

    print(f"Начинаю конвертацию {pdf_path.name} (один прогон, без батчей)...")
    with Heartbeat():
        try:
            result = conv.convert(str(pdf_path))
        except Exception as e:
            print(f"[!] Основной бэкенд упал целиком: {e}")
            print("    Пробую pypdfium2 для всего документа...")
            conv_fb = build_converter(use_fallback_backend=True)
            result = conv_fb.convert(str(pdf_path))

    md_text = dehyphenate(result.document.export_to_markdown())

    failed_pages = extract_failed_pages(result)
    if failed_pages:
        print(f"⚠️  Docling пропустил страницы: {failed_pages}")
        print("    Пробую восстановить их отдельно через pypdfium2...")
        conv_fb = build_converter(use_fallback_backend=True)
        recovered_chunks = []
        for p in failed_pages:
            try:
                r2 = conv_fb.convert(str(pdf_path), page_range=(p, p))
                text = dehyphenate(r2.document.export_to_markdown())
                recovered_chunks.append(f"\n\n---\n### [Восстановлено отдельно, стр. {p}]\n{text}")
                print(f"    стр. {p}: восстановлена")
            except Exception as e:
                print(f"    стр. {p}: не удалось восстановить ({e})")
        md_text += "".join(recovered_chunks)

    out_file = out / (pdf_path.stem + ".md")
    out_file.write_text(md_text, encoding="utf-8")
    print(f"\nГотово: {out_file}")


if __name__ == "__main__":
    pdf_arg = sys.argv[1] if len(sys.argv) > 1 else "Black_Crusade.pdf"
    convert_pdf(pdf_arg)
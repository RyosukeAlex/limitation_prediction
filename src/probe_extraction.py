#!/usr/bin/env python3
"""
probe_extraction.py  --  Limsight step 0: 抽出プローブ

目的:
    arXiv論文のPDFから「セクション構造」と「限界・将来展望に関する記述」が
    どこまで取れるかを、時代をまたいで目視確認するための診断スクリプト。
    収集パイプラインを組む前に、抽出のキレ具合を実データで確かめるのが狙い。

ポイント:
    - 明示的な "Limitations" セクションは近年の文化なので、
      ヘッダ依存ではなく「キーワード周辺の本文」も走査して、
      古い論文(2014/2017)と現代論文で取れ方がどう違うかを比較する。

実行はローカルで（このサンドボックスからarXivには繋がらない）:
    pip install arxiv pymupdf
    python probe_extraction.py
"""

import re
import sys
import textwrap
import urllib.request
from pathlib import Path

try:
    import arxiv
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("依存が無い: pip install arxiv pymupdf")


# --- 対象: 「長距離依存 → Transformer」の検証に使える既知の論文セット ---
# 時代をまたいで抽出のキレを目視で比べるための小サンプル。
# IDは自由に差し替え/追加してOK。特に、明示的な Limitations セクションを持つ
# 2023年以降の論文や、本番ドメインの SAR/RS 論文を1本足すと比較になる。
ARXIV_IDS = [
    "1409.3215",   # Seq2Seq (Sutskever+ 2014)  RNN時代
    "1409.0473",   # Neural MT with Attention (Bahdanau+ 2014/15)
    "1706.03762",  # Attention Is All You Need (Vaswani+ 2017)
    # "2302.13971", # 例: 近年の論文を足すならこの辺(LLaMA)
]

# セクションヘッダっぽい行を拾うヒューリスティック
# (短い行 / 番号付き任意 / 大文字始まり)
HEADER_RE = re.compile(
    r"^\s*(\d{1,2}(\.\d{1,2})*\.?\s+)?[A-Z][A-Za-z][\w\s\-&]{1,40}\s*$"
)

# 関心キーワード（ヘッダ非依存で本文も走査する）
KEYWORDS = [
    "limitation", "future work", "future direction",
    "discussion", "conclusion", "shortcoming", "drawback",
    "remains", "open problem", "long-range", "long range",
    "long-term depend", "vanishing gradient",
]


def download_text(arxiv_id: str, outdir: Path) -> tuple[str, str]:
    """arXiv IDからメタ(title)とPDFを取得し、(title, full_text)を返す。

    arxivライブラリのバージョン差を避けるため、PDFはURLを直接取得する
    （download_pdf がResultから無くなったバージョンに対応）。
    """
    result = next(arxiv.Client().results(arxiv.Search(id_list=[arxiv_id])))
    title = result.title.strip().replace("\n", " ")

    pdf_path = outdir / f"{arxiv_id.replace('/', '_')}.pdf"
    if not pdf_path.exists():
        pdf_url = getattr(result, "pdf_url", None) or f"https://arxiv.org/pdf/{arxiv_id}"
        req = urllib.request.Request(
            pdf_url, headers={"User-Agent": "Mozilla/5.0 (limsight-probe)"}
        )
        with urllib.request.urlopen(req) as resp, open(pdf_path, "wb") as f:
            f.write(resp.read())

    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return title, text


def find_headers(text: str) -> list[str]:
    """ヘッダっぽい行を出現順に抽出。"""
    headers = []
    for line in text.splitlines():
        if HEADER_RE.match(line) and len(line.split()) <= 6:
            headers.append(line.strip())
    return headers


def keyword_snippets(text: str, width: int = 220) -> list[tuple[str, str]]:
    """キーワード周辺の本文スニペットを返す（ヘッダ非依存の確認用）。"""
    low = text.lower()
    hits = []
    seen = set()
    for kw in KEYWORDS:
        start = 0
        while True:
            i = low.find(kw, start)
            if i == -1:
                break
            a = max(0, i - width // 2)
            b = min(len(text), i + width // 2)
            snippet = " ".join(text[a:b].split())
            key = (kw, snippet[:60])
            if key not in seen:
                seen.add(key)
                hits.append((kw, snippet))
            start = i + len(kw)
    return hits


def main() -> None:
    outdir = Path("pdfs")
    outdir.mkdir(exist_ok=True)

    for aid in ARXIV_IDS:
        print("=" * 80)
        print(f"[{aid}] downloading ...")
        try:
            title, text = download_text(aid, outdir)
        except Exception as e:  # noqa: BLE001  (診断用なので広く拾う)
            print(f"  失敗: {e}")
            continue

        print(f"TITLE        : {title}")
        print(f"本文文字数   : {len(text):,}")

        headers = find_headers(text)
        print(f"\n-- 検出したヘッダ候補 ({len(headers)}) --")
        for h in headers[:40]:
            print(f"   - {h}")

        hits = keyword_snippets(text)
        print(f"\n-- キーワード周辺スニペット ({len(hits)}) --")
        for kw, snip in hits[:12]:
            print(f"   [{kw}]")
            print(textwrap.fill(
                snip, width=78,
                initial_indent="     ", subsequent_indent="     ",
            ))
            print()


if __name__ == "__main__":
    main()
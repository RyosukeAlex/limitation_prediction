#!/usr/bin/env python3
"""
probe_grobid.py  --  GROBID抽出プローブ

目的: arXiv論文1本をGROBIDに投げてTEI XMLにし、
  (a) セクション見出しが構造として取れるか
  (b) Referencesが本文から分離されるか (引用混入を構造で弾けるか)
  (c) limitation/future work/long-range 系の語が本文のどのセクションに出るか
を確認する。前回の probe_extraction.py (pymupdfフラットテキスト) との比較用。

前提: GROBIDがlocalhost:8070で起動中であること
    curl http://localhost:8070/api/isalive  -> true

実行:
    pip install requests lxml
    python probe_grobid.py            # デフォルトで Attention Is All You Need
    python probe_grobid.py 1409.0473  # 任意のarXiv IDを指定
"""

import sys
import urllib.request
from pathlib import Path

import requests
from lxml import etree

GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# limitation/将来展望/検証ケースのキーワード
KEYWORDS = [
    "limitation", "future work", "shortcoming", "drawback",
    "long-range", "long range", "long-term depend", "remains",
]


def fetch_pdf(arxiv_id: str, outdir: Path) -> Path:
    pdf_path = outdir / f"{arxiv_id.replace('/', '_')}.pdf"
    if not pdf_path.exists():
        url = f"https://arxiv.org/pdf/{arxiv_id}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (limsight-grobid-probe)"}
        )
        with urllib.request.urlopen(req) as resp, open(pdf_path, "wb") as f:
            f.write(resp.read())
    return pdf_path


def grobid_tei(pdf_path: Path) -> bytes:
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            GROBID_URL,
            files={"input": (pdf_path.name, f, "application/pdf")},
            data={"consolidateHeader": "0", "consolidateCitations": "0"},
            timeout=300,
        )
    resp.raise_for_status()
    return resp.content


def analyze(tei: bytes) -> None:
    root = etree.fromstring(tei)

    body = root.find(".//tei:text/tei:body", TEI_NS)
    back = root.find(".//tei:text/tei:back", TEI_NS)

    # (a) 本文のセクション見出し一覧
    print("-- (a) 本文セクション見出し --")
    heads = body.findall(".//tei:div/tei:head", TEI_NS) if body is not None else []
    for h in heads:
        n = h.get("n", "")
        print(f"   {n + ' ' if n else ''}{(h.text or '').strip()}")
    print(f"   [計 {len(heads)} 見出し]")

    # (b) References分離の確認
    print("\n-- (b) References分離 --")
    bibls = back.findall(".//tei:listBibl/tei:biblStruct", TEI_NS) if back is not None else []
    print(f"   <back>の参考文献エントリ数: {len(bibls)}")
    print("   -> 本文(body)と参考文献(back)が別構造 = 引用領域を明示除外できる"
          if bibls else "   -> 参考文献が構造分離されていない(要確認)")

    # (c) キーワードが本文のどのセクション(段落)に出るか
    print("\n-- (c) キーワード出現箇所 (本文のみ / References除外済み) --")
    paras = body.findall(".//tei:p", TEI_NS) if body is not None else []
    full = "\n".join("".join(p.itertext()) for p in paras)
    low = full.lower()
    for kw in KEYWORDS:
        i = low.find(kw)
        if i == -1:
            continue
        a, b = max(0, i - 90), min(len(full), i + 90)
        snip = " ".join(full[a:b].split())
        print(f"   [{kw}] …{snip}…")


def main() -> None:
    arxiv_id = sys.argv[1] if len(sys.argv) > 1 else "1706.03762"
    outdir = Path("pdfs")
    outdir.mkdir(exist_ok=True)

    print(f"[{arxiv_id}] fetching PDF ...")
    pdf_path = fetch_pdf(arxiv_id, outdir)

    print("posting to GROBID ...")
    try:
        tei = grobid_tei(pdf_path)
    except requests.exceptions.ConnectionError:
        sys.exit("GROBIDに接続できない。localhost:8070 が起動中か確認:"
                 " curl http://localhost:8070/api/isalive")

    tei_path = outdir / f"{arxiv_id.replace('/', '_')}.tei.xml"
    tei_path.write_bytes(tei)
    print(f"saved TEI -> {tei_path}\n")

    analyze(tei)


if __name__ == "__main__":
    main()

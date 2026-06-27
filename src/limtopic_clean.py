"""
limtopic_clean.py  --  LimTopicの前処理(②)の忠実移植

元: code/Data preprocessing/(LimTopic)_Data_Preprocessing.ipynb
論文の散文ではなく実コードの閾値を採用している点に注意:
  - 行長 < 272文字 を除去   (論文に数値記載なし)
  - 単語数 < 20 の行を空に   (論文は「15語」と記載 → 実コードは20)
  - '.'で割った小片で 単語数 < 7 を除去
  - 括弧内を中身ごと削除      (注: 引用マーカーも巻き添えになる)
  - URL / CJK文 / ARRチェックリスト定型文 を除去

注意(将来用): この「括弧ごと削除」は、抽出済みの綺麗な限界文が相手だから
成立する。我々が生本文から文レベル抽出する段では、引用マーカーを
"他人の限界への言及"のシグナルとして先に使う必要があるため、順序を
変える(引用検出→括弧除去)。本モジュールは「LimTopic CSVの再現」用。
"""

import re

import pandas as pd

_PARENS = re.compile(r"\([^)]*\)")
_URL = re.compile(r"http\S+|www\S+", re.IGNORECASE)
_CJK = re.compile(r"[\u4e00-\u9fa5]")
_RISK_BOILERPLATE = ". Did you discuss any potential risks of your work?"


def _drop_short_subsentences(text: str, min_words: int = 7) -> str:
    parts = text.split(".")
    parts = ["" if len(p.split()) < min_words else p for p in parts]
    return ".".join(parts)


def _drop_cjk_sentences(text: str) -> str:
    parts = text.split(".")
    parts = [p.strip() for p in parts if not _CJK.search(p)]
    return ".".join(parts)


def clean_dataframe(df: pd.DataFrame, text_col: str = "Text") -> pd.DataFrame:
    """LimTopicの前処理をDataFrameに適用し、cleanな行のみ返す。"""
    df = df.copy()
    s = df[text_col].astype(str)

    # 改行除去 → 括弧(中身ごと)除去
    s = s.str.replace("\n", " ", regex=False)
    s = s.str.replace(_PARENS, "", regex=True)
    df[text_col] = s

    # 272文字未満の行を除去(外れ値)
    df = df[df[text_col].str.len() >= 272].copy()

    # URL除去
    df[text_col] = df[text_col].str.replace(_URL, "", regex=True)
    df = df.reset_index(drop=True)

    # 20語未満の行を空に
    mask_short = df[text_col].apply(lambda t: len(t.split()) < 20)
    df.loc[mask_short, text_col] = ""

    # 7語未満の小片を除去
    df[text_col] = df[text_col].apply(_drop_short_subsentences)

    # ARRチェックリスト定型文で始まる行を除去
    df = df[~df[text_col].str.startswith(_RISK_BOILERPLATE)].copy()

    # CJK文を除去
    df[text_col] = df[text_col].apply(_drop_cjk_sentences)

    # 空・極端に短い行を最終除去
    df[text_col] = df[text_col].str.strip()
    df = df[df[text_col].str.len() >= 30].reset_index(drop=True)
    return df


def clean_corpus(df: pd.DataFrame, text_col: str = "Text") -> list[str]:
    """cleanなドキュメント文字列のリストを返す。"""
    return clean_dataframe(df, text_col)[text_col].tolist()
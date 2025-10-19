#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import sys
from openai import OpenAI

DEFAULT_MODEL = "gpt-4o-mini"
OUTPUT_FILE = "document.txt"

SYSTEM_MSG = (
    "あなたは日本語の契約書ドラフトを作成する専門家です。"
    "常に簡潔で実務的、かつ最低限の必須条項のみを含めて作成してください。"
)

def build_user_prompt(customer: str, options: str) -> str:
    # -o が空なら「特になし」と明示
    considered = options.strip() if options and options.strip() else "特になし"
    return (
        "日本語の契約書を出力してください。"
        "契約はソフトウェア開発委託契約書で、最低限の条文のみ作成してください。"
        "最後の押印欄は不要。"
        f"顧客の名称は「{customer}」で、"
        f"契約書に加味して欲しい内容は「{considered}」です。\n\n"
        "出力形式：\n"
        "・冒頭に契約名\n"
        "・第1条（目的）から始め、最低限必要な条項（目的、業務範囲/成果物、対価/支払、検収、知的財産権、秘密保持、再委託、保証/責任、契約期間/解除、損害賠償、免責、準拠法/合意管轄）を簡潔に列挙\n"
        "・箇条書きや番号付き条項で可\n"
        "・日付や当事者欄は不要（押印欄不要指定のため）\n"
    )

def strip_code_fences(text: str) -> str:
    """念のためコードフェンスや余分なバッククォートを除去"""
    t = text.strip()
    if t.startswith("```"):
        # 先頭の ```xxx\n を落とす
        first_newline = t.find("\n")
        if first_newline != -1:
            t = t[first_newline+1:]
        # 末尾の ``` を落とす
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()

def generate_contract(customer: str, options: str, model: str) -> str:
    client = OpenAI()
    user_prompt = build_user_prompt(customer, options)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content or ""
    return strip_code_fences(content)

def main():
    parser = argparse.ArgumentParser(
        description="契約ドラフト（ソフトウェア開発委託契約・最低限条項）を生成して document.txt に保存します。"
    )
    parser.add_argument(
        "-c", "--customer", required=True,
        help="顧客の会社名（必須）"
    )
    parser.add_argument(
        "-o", "--options", default="",
        help="契約ドラフト作成時に考慮して欲しい条件（自然言語で自由に記述）"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"OpenAIのモデル名（既定: {DEFAULT_MODEL}）"
    )
    args = parser.parse_args()

    try:
        draft = generate_contract(args.customer, args.options, args.model)
    except Exception as e:
        print(f"エラー: 契約書の生成に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        Path(OUTPUT_FILE).write_text(draft, encoding="utf-8")
    except Exception as e:
        print(f"エラー: ファイルへの書き込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"契約ドラフトを {OUTPUT_FILE} に出力しました。")

if __name__ == "__main__":
    main()

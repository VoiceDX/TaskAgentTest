# check_contract.py
import argparse
from pathlib import Path
from openai import OpenAI

DEFAULT_MODEL = "gpt-4o-mini"
TARGET_FILE = "document.txt"

PROMPT = """あなたは文書の種類を判定する厳格な分類器です。
与えられた日本語テキストが「契約書（契約当事者・契約条項・権利義務・有効期間・準拠法等が記載された法的合意文書）」に該当するかのみを判定してください。

出力は次のどちらか1語のみ:
- CONTRACT  （契約書に該当する）
- NOT_CONTRACT （契約書に該当しない）

注意:
- 申込書、見積書、請求書、議事録、覚書（法的拘束力が弱いメモ）だけの文書は NOT_CONTRACT。
- NDA（秘密保持契約）、業務委託契約、売買契約、ライセンス契約等は CONTRACT。
- 迷う場合は NOT_CONTRACT。
"""

def classify_is_contract(text: str, model: str) -> bool:
    client = OpenAI()
    # 念のため入力を上限カット（トークン節約）
    snippet = text[:20000]
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": "Output EXACTLY one token: CONTRACT or NOT_CONTRACT."},
            {"role": "user", "content": PROMPT},
            {"role": "user", "content": f"--- 文書本文 ---\n{snippet}\n--- 終了 ---"}
        ]
    )
    out = resp.choices[0].message.content.strip().upper()
    return out == "CONTRACT"

def main():
    parser = argparse.ArgumentParser(description="Check if document.txt is a contract.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model (default: gpt-4o-mini)")
    args = parser.parse_args()

    p = Path(TARGET_FILE)
    if not p.exists():
        print("契約書未作成")
        return

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        print("契約書未作成")
        return

    try:
        is_contract = classify_is_contract(text, args.model)
    except Exception:
        # APIエラー時は未作成扱い
        print("契約書未作成")
        return

    if is_contract:
        print(f"契約書{TARGET_FILE}あり")
    else:
        print("契約書未作成")

if __name__ == "__main__":
    main()

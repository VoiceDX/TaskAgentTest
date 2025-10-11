# TaskAgentTest

## 概要
TaskAgentTest は、OpenAI API と AutoGen を組み合わせた最小構成の ReAct 型 AI エージェントです。ツールの定義を JSON ファイルから読み込み、ユーザーが入力した目的を達成するために計画立案・ツール実行・結果評価を繰り返します。提供されているサンプルでは、Python スクリプトとして登録された数式評価ツールを利用できます。

## 必要要件
- Python 3.10 以上
- OpenAI API キー（環境変数 `OPENAI_API_KEY` に設定）
- 以下の Python パッケージ
  - `autogen`
  - `openai`

```bash
pip install autogen openai
```

## 設定
1. OpenAI API キーを環境変数に設定します。
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
2. 使用するモデルを変更したい場合は `OPENAI_MODEL` を設定します（デフォルトは `gpt-4o-mini`）。
   ```bash
   export OPENAI_MODEL="gpt-4o"
   ```
3. 利用可能なツールは `tools/tools.json` に JSON 配列で記述します。
   - 各要素は `name`, `description`, `script_path`, `arguments` を持ちます。
   - `arguments` はコマンドライン引数の定義を表すオブジェクト配列です。
     - `name`: エージェントが値を指定する際に使用する引数名。
     - `option`: Python スクリプト起動時に付与するコマンドラインオプション（例: `--expression`）。
     - `description`: 引数の説明。
     - `required`: 必須かどうかを示す真偽値。
   - `script_path` には Python スクリプトへの相対パスを指定します。

   ```json
   [
     {
       "name": "math_tool",
       "description": "数式を評価して結果を返すツール",
       "script_path": "tools/math_tool.py",
       "arguments": [
         {
           "name": "expression",
           "option": "--expression",
           "description": "評価したい数式 (例: 2+3*4)",
           "required": true
         }
       ]
     }
   ]
   ```

   新しいツールを追加する場合は、対応する Python スクリプトを作成した上で、必要な引数定義を含めて JSON に登録してください。

## 使い方
1. プロジェクトルートで以下のコマンドを実行します。
   ```bash
   python src/main.py
   ```
2. プロンプトに従って目的（例: `2+3*4 を計算して`）を入力します。
3. エージェントが最大試行回数（既定は 5 回）まで計画とツール実行を繰り返し、最終結果を表示します。ツールに引数が定義されている場合、エージェントは `action_input` を JSON オブジェクトとして出力し、各引数名に対する値を指定します。

## 実装ファイル
- `src/agent.py`: ReAct エージェント本体とツール登録クラスを実装しています。
- `src/main.py`: コマンドラインからエージェントを起動するエントリーポイントです。
- `tools/`: エージェントが利用できる Python ツール群とその定義 JSON を含みます。
- `docs/agent_description.md`: クラスと処理フローの詳細な解説ドキュメントです。

## トラブルシューティング
- OpenAI API 呼び出しでエラーが発生する場合は、API キーと利用モデルが正しく設定されているか確認してください。
- ツール実行で失敗する場合は、対象スクリプトが実行可能か、また `tools/tools.json` に正しいパスが設定されているかを確認してください。

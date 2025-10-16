# AIエージェント構成概要

## クラス・関数解説
- `ToolArgument`クラス（`src/agent.py`）
  - JSON で定義されたコマンドライン引数情報（名前・オプション・説明・必須フラグ）を保持します。
- `Tool`クラス（`src/agent.py`）
  - ツールの名前・説明・スクリプトパス・引数定義を保持するデータクラスです。
- `ToolRegistry`クラス
  - `__init__`でJSONファイルのパスを受け取り、`load_tools`でツール定義を読み込みます。
  - JSON配列の各要素から`Tool`インスタンスを生成し、引数定義 (`ToolArgument`) を含めて辞書に登録します。
- `ReactAgent`クラス
  - `__init__`でツール群と LLM 設定を初期化し、AutoGen の `AssistantAgent` / `UserProxyAgent` が利用可能な環境であれば両エージェントを生成して各ツールを登録します。AutoGen が利用できない場合は `OpenAIWrapper` によるフォールバックで動作します。
  - `_build_system_prompt` と `_build_tool_overview` が、登録されたツール情報から ReAct 用のシステムプロンプトを構築します。
  - `_register_autogen_tools` / `_register_single_tool` が、JSON で定義されたツールを AutoGen の関数呼び出しとして公開し、LLM からの function call に対応できるようにします。
  - `plan_action` が ReAct ステップの計画フェーズを担い、AutoGen の `AssistantAgent.generate_reply` を優先的に呼び出して JSON 形式のプランを取得します。フォールバックでは従来どおり `OpenAIWrapper` でチャット補完を実行します。
  - `_normalize_action_input` が LLM 出力の `action_input` を文字列・JSON・配列のいずれでも扱えるように整形します。
  - `_invoke_tool_command` がツール定義と正規化された引数からコマンドラインを組み立て、Python スクリプトとしてサブプロセス実行します。`execute_tool` はこのメソッドを利用して観測値を取得します。
  - `run` が目的達成のメインループで、計画→実行→評価を繰り返しながら終了条件（成功または最大試行回数）まで処理を進めます。
- `main`関数（`src/main.py`）
  - ツール定義ファイルを読み込み、`ReactAgent`を生成します。
  - ユーザから入力された目的を`run`に渡し、最終応答をコンソール出力します。

## 処理の流れ
1. `main`関数でツール定義JSONを読み込み、`ToolRegistry`と`ReactAgent`を初期化します。
2. ユーザが入力した目的文が`ReactAgent.run`へ渡され、履歴と観測を初期化した上でループ処理が始まります。
3. 各ループで`plan_action`が呼び出され、AutoGen の `AssistantAgent` が利用可能であれば function call として、なければフォールバックの `OpenAIWrapper` によって次の`action`と`action_input`が計画されます。引数付きツールの場合、`action_input` は引数名をキーとするJSONオブジェクトとして出力されます。
4. `_normalize_action_input` が `action_input` を辞書・配列・文字列のいずれかに正規化した後、`_invoke_tool_command` が計画されたツールをPythonスクリプトとして実行し、標準出力・標準エラーを観測値として取得します。`execute_tool` はこの結果を呼び出し元へ返します。
5. 観測結果を履歴に追加した上で、成功判定（`is_final`が真）または最大試行回数に到達するまで3〜4を繰り返します。
6. 成功または失敗メッセージを`run`が返し、`main`関数がコンソールに表示します。

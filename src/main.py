import os
from pathlib import Path

from agent import ReactAgent, ToolRegistry


def main() -> None:
    tool_path = Path("tools/tools.json")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    print(f"[main.py][main] tool_path={tool_path}, model={model}")
    registry = ToolRegistry(tool_path)
    agent = ReactAgent(registry, model=model)
    user_goal = input("目的を入力してください: ")
    result = agent.run(user_goal)
    print(result)
    print(f"[main.py][main] result={result}")


if __name__ == "__main__":
    main()

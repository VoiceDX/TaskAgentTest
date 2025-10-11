import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from autogen import OpenAIWrapper


@dataclass
class Tool:
    name: str
    description: str
    script_path: str


class ToolRegistry:
    def __init__(self, registry_path: Path):
        print(f"[agent.py][ToolRegistry.__init__] registry_path={registry_path}")
        self.registry_path = registry_path
        self.tools: Dict[str, Tool] = {}
        print(f"[agent.py][ToolRegistry.__init__] tools={self.tools}")

    def load_tools(self) -> Dict[str, Tool]:
        print(f"[agent.py][ToolRegistry.load_tools] registry_path={self.registry_path}")
        with self.registry_path.open("r", encoding="utf-8") as fp:
            # JSON format: [{"name": str, "description": str, "script_path": str}, ...]
            data = json.load(fp)
        for item in data:
            tool = Tool(
                name=item["name"],
                description=item["description"],
                script_path=item["script_path"],
            )
            self.tools[tool.name] = tool
        print(f"[agent.py][ToolRegistry.load_tools] tools={self.tools}")
        return self.tools


class ReactAgent:
    def __init__(self, tool_registry: ToolRegistry, model: str = "gpt-4o-mini", max_turns: int = 5):
        print(
            f"[agent.py][ReactAgent.__init__] model={model}, max_turns={max_turns}, registry_path={tool_registry.registry_path}"
        )
        self.tool_registry = tool_registry
        self.tools = tool_registry.load_tools()
        self.model = model
        self.max_turns = max_turns
        self.llm = OpenAIWrapper(config={"model": model})
        print(
            f"[agent.py][ReactAgent.__init__] tools={list(self.tools.keys())}, model={self.model}, max_turns={self.max_turns}"
        )

    def _chat_completion(self, messages: List[Dict[str, str]]) -> Dict[str, object]:
        print(f"[agent.py][ReactAgent._chat_completion] messages={messages}")
        try:
            response = self.llm.create(messages=messages)
        except AttributeError:
            response = self.llm.chat_completion(messages=messages)
        print(f"[agent.py][ReactAgent._chat_completion] response={response}")
        return response

    def plan_action(self, objective: str, history: List[str], observation: Optional[str]) -> Dict[str, str]:
        print(
            f"[agent.py][ReactAgent.plan_action] objective={objective}, history={history}, observation={observation}"
        )
        tool_descriptions = "\n".join(
            f"- {tool.name}: {tool.description} (python {tool.script_path})" for tool in self.tools.values()
        )
        prompt = (
            "You are an assistant following the ReAct approach.\n"
            "Available tools:\n"
            f"{tool_descriptions}\n"
            "Respond in JSON with keys 'thought', 'action', 'action_input', 'is_final', and 'final_answer'.\n"
            "If you believe the objective is achieved or impossible, set 'is_final' to true and provide 'final_answer'."
        )
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "objective": objective,
                        "history": history,
                        "observation": observation,
                    }
                ),
            },
        ]
        response = self._chat_completion(messages)
        content = response["choices"][0]["message"]["content"]
        try:
            plan = json.loads(content)
        except json.JSONDecodeError:
            plan = {
                "thought": content,
                "action": "",
                "action_input": "",
                "is_final": True,
                "final_answer": content,
            }
        print(f"[agent.py][ReactAgent.plan_action] plan={plan}")
        return plan

    def execute_tool(self, tool_name: str, action_input: str) -> str:
        print(f"[agent.py][ReactAgent.execute_tool] tool_name={tool_name}, action_input={action_input}")
        tool = self.tools.get(tool_name)
        if not tool:
            result = f"Unknown tool: {tool_name}"
            print(f"[agent.py][ReactAgent.execute_tool] result={result}")
            return result
        command = ["python", tool.script_path, action_input]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            result = completed.stderr.strip()
        else:
            result = completed.stdout.strip()
        print(f"[agent.py][ReactAgent.execute_tool] result={result}")
        return result

    def run(self, objective: str) -> str:
        print(f"[agent.py][ReactAgent.run] objective={objective}")
        history: List[str] = []
        observation: Optional[str] = None
        for step in range(self.max_turns):
            plan = self.plan_action(objective, history, observation)
            if plan.get("is_final"):
                final_answer = plan.get("final_answer", "")
                print(
                    f"[agent.py][ReactAgent.run] final_answer={final_answer}, step={step}, history={history}"
                )
                return final_answer
            action = plan.get("action", "")
            action_input = plan.get("action_input", "")
            observation = self.execute_tool(action, action_input)
            history.append(
                json.dumps({
                    "thought": plan.get("thought"),
                    "action": action,
                    "action_input": action_input,
                    "observation": observation,
                })
            )
        final_message = (
            "最大試行回数に達したため目的を完遂できませんでした。"
        )
        print(f"[agent.py][ReactAgent.run] final_message={final_message}, history={history}")
        return final_message

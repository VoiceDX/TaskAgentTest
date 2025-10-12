import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from autogen import OpenAIWrapper


@dataclass
class ToolArgument:
    name: str
    option: Optional[str]
    description: str
    required: bool = False


@dataclass
class Tool:
    name: str
    description: str
    script_path: str
    arguments: List[ToolArgument] = field(default_factory=list)


class ToolRegistry:
    def __init__(self, registry_path: Path):
        print(f"[agent.py][ToolRegistry.__init__] registry_path={registry_path}")
        self.registry_path = registry_path
        self.tools: Dict[str, Tool] = {}
        print(f"[agent.py][ToolRegistry.__init__] tools={self.tools}")

    def load_tools(self) -> Dict[str, Tool]:
        print(f"[agent.py][ToolRegistry.load_tools] registry_path={self.registry_path}")
        with self.registry_path.open("r", encoding="utf-8") as fp:
            # JSON format: [{"name": str, "description": str, "script_path": str, "arguments": [{"name": str, "option": Optional[str], "description": str, "required": bool}]}, ...]
            data = json.load(fp)
        for item in data:
            arguments = [
                ToolArgument(
                    name=argument.get("name"),
                    option=argument.get("option"),
                    description=argument.get("description", ""),
                    required=argument.get("required", False),
                )
                for argument in item.get("arguments", [])
            ]
            tool = Tool(
                name=item["name"],
                description=item["description"],
                script_path=item["script_path"],
                arguments=arguments,
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
            response = self.llm.create(messages=messages, model=self.model)
        except AttributeError:
            response = self.llm.chat_completion(messages=messages, model=self.model)
        print(f"[agent.py][ReactAgent._chat_completion] response={response}")
        return response

    def plan_action(self, objective: str, history: List[str], observation: Optional[str]) -> Dict[str, Any]:
        print(
            f"[agent.py][ReactAgent.plan_action] objective={objective}, history={history}, observation={observation}"
        )
        tool_descriptions = []
        for tool in self.tools.values():
            if not tool.arguments:
                arguments_description = "No arguments. Pass a simple string as action_input."
            else:
                argument_details: List[str] = []
                for argument in tool.arguments:
                    option_text = f" (option: {argument.option})" if argument.option else ""
                    requirement_text = "required" if argument.required else "optional"
                    argument_details.append(
                        f"{argument.name}{option_text} - {argument.description} ({requirement_text})"
                    )
                arguments_description = "; ".join(argument_details)
            tool_descriptions.append(
                f"- {tool.name}: {tool.description} (python {tool.script_path})\n  Arguments: {arguments_description}"
            )
        tool_description_text = "\n".join(tool_descriptions)
        prompt = (
            "You are an assistant following the ReAct approach.\n"
            "Available tools:\n"
            f"{tool_description_text}\n"
            "Respond in JSON with keys 'thought', 'action', 'action_input', 'is_final', and 'final_answer'.\n"
            "When invoking a tool with defined arguments, set 'action_input' to a JSON object mapping argument names to their values.\n"
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

    def _normalize_action_input(
        self, action_input: Union[str, Dict[str, Any], List[Any]]
    ) -> Union[str, Dict[str, Any], List[Any]]:
        print(f"[agent.py][ReactAgent._normalize_action_input] action_input={action_input}")
        normalized: Union[str, Dict[str, Any], List[Any]]
        if isinstance(action_input, str):
            trimmed = action_input.strip()
            if not trimmed:
                normalized = {}
            else:
                try:
                    parsed = json.loads(trimmed)
                except json.JSONDecodeError:
                    normalized = trimmed
                else:
                    normalized = parsed
        else:
            normalized = action_input
        print(f"[agent.py][ReactAgent._normalize_action_input] normalized={normalized}")
        return normalized

    def execute_tool(self, tool_name: str, action_input: Union[str, Dict[str, Any], List[Any]]) -> str:
        print(f"[agent.py][ReactAgent.execute_tool] tool_name={tool_name}, action_input={action_input}")
        tool = self.tools.get(tool_name)
        if not tool:
            result = f"Unknown tool: {tool_name}"
            print(f"[agent.py][ReactAgent.execute_tool] result={result}")
            return result
        normalized_input = self._normalize_action_input(action_input)
        command: List[str] = ["python", tool.script_path]
        if isinstance(normalized_input, dict):
            missing_arguments = [
                argument.name
                for argument in tool.arguments
                if argument.required and argument.name not in normalized_input
            ]
            if missing_arguments:
                result = f"Missing required arguments: {', '.join(missing_arguments)}"
                print(f"[agent.py][ReactAgent.execute_tool] result={result}")
                return result
            recognized_arguments = {argument.name for argument in tool.arguments}
            for argument in tool.arguments:
                if argument.name not in normalized_input:
                    continue
                value = normalized_input[argument.name]
                if argument.option:
                    command.append(argument.option)
                if isinstance(value, list):
                    command.extend(str(item) for item in value)
                else:
                    command.append(str(value))
            for key, value in normalized_input.items():
                if key in recognized_arguments:
                    continue
                if isinstance(value, list):
                    command.extend(str(item) for item in value)
                else:
                    command.append(str(value))
        elif isinstance(normalized_input, list):
            command.extend(str(item) for item in normalized_input)
        else:
            if normalized_input:
                command.append(str(normalized_input))
        print(f"[agent.py][ReactAgent.execute_tool] command={command}")
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

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from autogen import OpenAIWrapper

try:
    from autogen import AssistantAgent, UserProxyAgent
except ImportError:  # pragma: no cover - fallback when AutoGen agentchat is unavailable
    AssistantAgent = None
    UserProxyAgent = None


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
        self.assistant_agent: Optional[AssistantAgent] = None
        self.user_proxy_agent: Optional[UserProxyAgent] = None
        self._autogen_enabled = AssistantAgent is not None and UserProxyAgent is not None
        if self._autogen_enabled:
            self.assistant_agent = AssistantAgent(
                name="react_planner",
                system_message="",
                llm_config={"config_list": [{"model": model}]},
            )
            self.user_proxy_agent = UserProxyAgent(
                name="react_runtime",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=1,
                code_execution_config=False,
            )
            self._register_autogen_tools()
        print(
            f"[agent.py][ReactAgent.__init__] tools={list(self.tools.keys())}, model={self.model}, max_turns={self.max_turns}, autogen_enabled={self._autogen_enabled}"
        )

    def _register_autogen_tools(self) -> None:
        print(f"[agent.py][ReactAgent._register_autogen_tools] autogen_enabled={self._autogen_enabled}")
        if not self._autogen_enabled or not self.user_proxy_agent:
            print(
                f"[agent.py][ReactAgent._register_autogen_tools] skipped because autogen_enabled={self._autogen_enabled}"
            )
            return
        for tool in self.tools.values():
            self._register_single_tool(tool)
        print(f"[agent.py][ReactAgent._register_autogen_tools] registered_tools={list(self.tools.keys())}")

    def _register_single_tool(self, tool: Tool) -> None:
        print(f"[agent.py][ReactAgent._register_single_tool] tool={tool}")
        if not self._autogen_enabled or not self.user_proxy_agent:
            print(
                f"[agent.py][ReactAgent._register_single_tool] skipped tool={tool.name}, autogen_enabled={self._autogen_enabled}"
            )
            return

        description = self._build_tool_docstring(tool)

        def _executor(**kwargs: Any) -> str:
            print(f"[agent.py][ReactAgent._register_single_tool._executor] tool={tool.name}, kwargs={kwargs}")
            normalized = kwargs if kwargs else {}
            result = self._invoke_tool_command(tool, normalized)
            print(f"[agent.py][ReactAgent._register_single_tool._executor] result={result}")
            return result

        decorator = getattr(self.user_proxy_agent, "register_for_execution", None)
        if callable(decorator):
            decorator(name=tool.name, description=description)(_executor)
        if self.assistant_agent:
            llm_decorator = getattr(self.assistant_agent, "register_for_llm_execution", None)
            if callable(llm_decorator):
                llm_decorator(name=tool.name, description=description)(_executor)
        print(
            f"[agent.py][ReactAgent._register_single_tool] registered tool={tool.name} with description={description}"
        )

    def _build_tool_docstring(self, tool: Tool) -> str:
        print(f"[agent.py][ReactAgent._build_tool_docstring] tool={tool}")
        if not tool.arguments:
            description = f"{tool.description}. 実行例: python {tool.script_path} '<input>'"
            print(f"[agent.py][ReactAgent._build_tool_docstring] description={description}")
            return description
        argument_lines = []
        for argument in tool.arguments:
            option_text = f" (option: {argument.option})" if argument.option else ""
            requirement_text = "必須" if argument.required else "任意"
            argument_lines.append(
                f"{argument.name}{option_text}: {argument.description} [{requirement_text}]"
            )
        formatted_arguments = " | ".join(argument_lines)
        description = f"{tool.description}. 引数: {formatted_arguments}"
        print(f"[agent.py][ReactAgent._build_tool_docstring] description={description}")
        return description

    def _build_tool_overview(self) -> str:
        print(f"[agent.py][ReactAgent._build_tool_overview] tools={self.tools}")
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
        overview = "\n".join(tool_descriptions)
        print(f"[agent.py][ReactAgent._build_tool_overview] overview={overview}")
        return overview

    def _build_system_prompt(self) -> str:
        print(f"[agent.py][ReactAgent._build_system_prompt] building_prompt=True")
        overview = self._build_tool_overview()
        prompt = (
            "You are an assistant following the ReAct approach.\n"
            "Available tools:\n"
            f"{overview}\n"
            "Respond in JSON with keys 'thought', 'action', 'action_input', 'is_final', and 'final_answer'.\n"
            "When invoking a tool with defined arguments, set 'action_input' to a JSON object mapping argument names to their values.\n"
            "If you believe the objective is achieved or impossible, set 'is_final' to true and provide 'final_answer'."
        )
        print(f"[agent.py][ReactAgent._build_system_prompt] prompt={prompt}")
        return prompt

    def _extract_reply_content(self, reply: Any) -> str:
        print(f"[agent.py][ReactAgent._extract_reply_content] reply={reply}")
        content = ""
        if isinstance(reply, str):
            content = reply
        elif isinstance(reply, dict):
            content = reply.get("content", "")
        elif isinstance(reply, list) and reply:
            first = reply[0]
            if isinstance(first, dict):
                content = first.get("content", "")
            else:
                content = str(first)
        else:
            content = str(reply)
        print(f"[agent.py][ReactAgent._extract_reply_content] content={content}")
        return content

    def _invoke_tool_command(
        self, tool: Tool, normalized_input: Union[str, Dict[str, Any], List[Any]]
    ) -> str:
        print(
            f"[agent.py][ReactAgent._invoke_tool_command] tool={tool}, normalized_input={normalized_input}"
        )
        command: List[str] = ["python", tool.script_path]
        if isinstance(normalized_input, dict):
            missing_arguments = [
                argument.name
                for argument in tool.arguments
                if argument.required and argument.name not in normalized_input
            ]
            if missing_arguments:
                message = f"Missing required arguments: {', '.join(missing_arguments)}"
                print(f"[agent.py][ReactAgent._invoke_tool_command] message={message}")
                return message
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
        print(f"[agent.py][ReactAgent._invoke_tool_command] command={command}")
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            result = completed.stderr.strip()
        else:
            result = completed.stdout.strip()
        print(f"[agent.py][ReactAgent._invoke_tool_command] result={result}")
        return result

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
        system_prompt = self._build_system_prompt()
        payload = {
            "objective": objective,
            "history": history,
            "observation": observation,
        }
        if self.assistant_agent and self._autogen_enabled:
            update_system_message = getattr(self.assistant_agent, "update_system_message", None)
            if callable(update_system_message):
                update_system_message(system_prompt)
            messages = [
                {
                    "role": "user",
                    "content": json.dumps(payload),
                }
            ]
            try:
                reply = self.assistant_agent.generate_reply(messages=messages, sender=self.user_proxy_agent)
            except TypeError:
                reply = self.assistant_agent.generate_reply(messages)
            content = self._extract_reply_content(reply)
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload)},
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
        result = self._invoke_tool_command(tool, normalized_input)
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

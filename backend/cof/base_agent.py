"""COF async base agent — wraps a single AgentSkill via the openai-agents SDK.

Mode resolution at construction time:
  1. agents SDK + COF environment (no key required) → "agents_sdk"
  2. agents SDK + OPENAI_API_KEY in env → "agents_sdk"
  3. Neither available → mode = "unavailable", chat() raises a clear error

There is NO mock fallback. If neither path is available, the chat router will
return an error response telling the analyst to configure the connection.
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from typing import Any, Callable

from agent.skill_loader import AgentSkill

log = logging.getLogger("cma.cof.base_agent")

try:
    from agents import Agent, Runner, FunctionTool, RunResult
    from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False


def _convert_tool(spec: dict, handler: Callable[[str, dict], str]) -> Any:
    """Convert an OpenAI-format tool dict into an agents.FunctionTool."""
    func_def = spec.get("function", spec)
    name = func_def["name"]
    description = func_def.get("description", "")
    params = func_def.get("parameters", {})

    async def _h(ctx, input: str) -> str:
        try:
            args = json.loads(input) if input else {}
        except json.JSONDecodeError:
            args = {}
        try:
            return handler(name, args)
        except Exception as e:
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()[-400:]})

    return FunctionTool(
        name=name, description=description,
        params_json_schema=params, on_invoke_tool=_h,
    )


def _filter_tools(openai_tools: list[dict], allowed: set[str] | None,
                  handler: Callable[[str, dict], str]) -> list[Any]:
    out = []
    for spec in openai_tools:
        func_def = spec.get("function", spec)
        if allowed is not None and func_def.get("name") not in allowed:
            continue
        out.append(_convert_tool(spec, handler))
    return out


_DETAIL_LIMIT = 1500


def _truncate(text: str, limit: int = _DETAIL_LIMIT) -> tuple[str, bool]:
    if not text:
        return text, False
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n…", True


def _safe_attr(obj, *names):
    """Return first attribute that exists on obj OR its `raw_item` field."""
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v is not None:
                return v
    raw = getattr(obj, "raw_item", None)
    if raw is not None:
        for n in names:
            if hasattr(raw, n):
                v = getattr(raw, n)
                if v is not None:
                    return v
            if isinstance(raw, dict) and n in raw and raw[n] is not None:
                return raw[n]
    return None


def _format_args(arguments) -> str:
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return json.dumps(parsed, indent=2, default=str)
        except Exception:
            return arguments
    try:
        return json.dumps(arguments, indent=2, default=str)
    except Exception:
        return str(arguments)


def _step_from_item(item) -> dict | None:
    """Convert one RunItem to a TraceStep dict. Returns None on unknown shapes
    that produce no useful info (so callers can skip silently)."""
    cls_name = type(item).__name__
    agent_name = None
    agent = getattr(item, "agent", None)
    if agent is not None:
        agent_name = getattr(agent, "name", None)

    try:
        if cls_name == "ToolCallItem":
            tool_name = _safe_attr(item, "name", "tool_name") or "tool"
            args = _safe_attr(item, "arguments", "input") or ""
            detail, trunc = _truncate(_format_args(args))
            return {
                "kind": "tool_call",
                "label": f"called {tool_name}",
                "detail": detail or None,
                "tool_name": tool_name,
                "agent_name": agent_name,
                "truncated": trunc,
            }
        if cls_name == "ToolCallOutputItem":
            tool_name = _safe_attr(item, "name", "tool_name") or "tool"
            output = _safe_attr(item, "output", "content")
            detail, trunc = _truncate(_format_args(output) if output is not None else "")
            return {
                "kind": "tool_output",
                "label": f"{tool_name} returned",
                "detail": detail or None,
                "tool_name": tool_name,
                "agent_name": agent_name,
                "truncated": trunc,
            }
        if cls_name == "MessageOutputItem":
            content = ""
            raw = getattr(item, "raw_item", None)
            if raw is not None:
                parts = getattr(raw, "content", None)
                if isinstance(parts, list):
                    for p in parts:
                        t = getattr(p, "text", None) if not isinstance(p, dict) else p.get("text")
                        if t:
                            content += t
                elif isinstance(parts, str):
                    content = parts
            preview, trunc = _truncate(content, limit=400)
            return {
                "kind": "message",
                "label": "produced final message",
                "detail": preview or None,
                "agent_name": agent_name,
                "truncated": trunc,
            }
        if cls_name == "ReasoningItem":
            content = _safe_attr(item, "content", "summary") or ""
            detail, trunc = _truncate(_format_args(content))
            return {
                "kind": "reasoning",
                "label": "reasoning",
                "detail": detail or None,
                "agent_name": agent_name,
                "truncated": trunc,
            }
        if cls_name in ("HandoffCallItem", "HandoffOutputItem"):
            target = _safe_attr(item, "target_agent", "to_agent") or "?"
            target_name = getattr(target, "name", None) or str(target)
            kind_label = "handing off to" if cls_name == "HandoffCallItem" else "handoff returned from"
            return {
                "kind": "handoff",
                "label": f"{kind_label} {target_name}",
                "agent_name": agent_name,
                "tool_name": target_name,
            }
        return {
            "kind": "info",
            "label": cls_name,
            "agent_name": agent_name,
        }
    except Exception as e:
        log.debug("trace step extraction failed for %s: %s", cls_name, e)
        return {
            "kind": "info",
            "label": f"{cls_name} (unparsed)",
        }


def _extract_trace(result) -> list[dict]:
    """Convert RunResult.new_items into a list of plain TraceStep dicts.
    Used by callers that take the non-streaming code path."""
    steps: list[dict] = []
    items = getattr(result, "new_items", None) or []
    for item in items:
        s = _step_from_item(item)
        if s is not None:
            steps.append(s)
    return steps


class CofBaseAgent:
    """A single specialist agent backed by openai-agents."""

    MAX_TURNS = 10

    def __init__(
        self,
        skill: AgentSkill,
        openai_tools: list[dict],
        tool_handler: Callable[[str, dict], str],
    ):
        self.skill = skill
        self.tool_handler = tool_handler
        self._mode = "unavailable"
        self._init_error: str | None = None

        if not HAS_AGENTS_SDK:
            self._init_error = "openai-agents SDK is not installed. `pip install openai-agents`."
            return

        try:
            from agents import set_tracing_disabled
            from openai import AsyncOpenAI
            set_tracing_disabled(True)

            allowed = set(skill.tools) if skill.tools else None
            self._function_tools = _filter_tools(openai_tools, allowed, tool_handler)

            client_kwargs: dict[str, Any] = {}
            cof_base = os.getenv("COF_BASE_URL")
            cof_key  = os.getenv("COF_API_KEY")
            api_key  = os.getenv("OPENAI_API_KEY")
            if cof_base:
                client_kwargs["base_url"] = cof_base
                client_kwargs["api_key"] = cof_key or "cof-internal"
            elif api_key:
                client_kwargs["api_key"] = api_key
            else:
                # Bare AsyncOpenAI() — only works if running inside a COF environment
                # where the SDK auto-resolves credentials. Otherwise the first chat call
                # surfaces a 401 from the API and we report it.
                pass

            self._client = AsyncOpenAI(**client_kwargs)
            self._model = OpenAIChatCompletionsModel(
                model=skill.model, openai_client=self._client,
            )
            self._agent = Agent(
                name=skill.name,
                instructions=skill.system_prompt,
                model=self._model,
                tools=self._function_tools,
            )
            self._mode = "agents_sdk"
            log.info("CofBaseAgent[%s] initialized with model %s", skill.name, skill.model)
        except Exception as e:
            self._init_error = f"Init failed: {e}"
            log.error("CofBaseAgent[%s] init error: %s", skill.name, e)

    async def chat(self, user_message: str, extra_context: str = "") -> str:
        text, _ = await self.chat_with_trace(user_message, extra_context=extra_context)
        return text

    async def chat_with_trace(
        self,
        user_message: str,
        extra_context: str = "",
        on_step: Callable[[dict], None] | None = None,
    ) -> tuple[str, list[dict]]:
        """Run the agent in streaming mode and return (final_text, trace_steps).

        Each RunItem (tool call → tool output → message → reasoning → handoff)
        is converted to a TraceStep dict and pushed through `on_step` as soon
        as it lands, so the playbook runner can append to a shared
        `pe.trace` list and the UI's polling loop can render live progress.
        """
        if self._mode != "agents_sdk":
            raise RuntimeError(self._init_error or "Agent unavailable")
        try:
            messages: list[dict[str, str]] = []
            if extra_context:
                messages.append({"role": "user", "content": f"[Context]\n{extra_context}"})
            messages.append({"role": "user", "content": user_message})

            trace: list[dict] = []
            seen_ids: set[int] = set()  # id() of items we've already emitted

            stream = Runner.run_streamed(
                starting_agent=self._agent,
                input=messages,
                max_turns=self.MAX_TURNS,
            )
            async for ev in stream.stream_events():
                # Only the run_item_stream_event carries the structured items
                # we want to surface as trace steps. The raw token stream is
                # too noisy and the agent_updated event is implicit in handoffs.
                ev_type = getattr(ev, "type", None)
                if ev_type == "run_item_stream_event":
                    item = getattr(ev, "item", None)
                    if item is None or id(item) in seen_ids:
                        continue
                    seen_ids.add(id(item))
                    step = _step_from_item(item)
                    if step is not None:
                        trace.append(step)
                        if on_step is not None:
                            try:
                                on_step(step)
                            except Exception as cb_err:
                                log.debug("on_step callback raised: %s", cb_err)

            # Stream completed — final_output is now populated on the result.
            final_text = getattr(stream, "final_output", None) or ""
            return final_text, trace
        except Exception as e:
            log.error("CofBaseAgent[%s] chat error: %s", self.skill.name, e)
            log.debug(traceback.format_exc())
            raise

    @property
    def available(self) -> bool:
        return self._mode == "agents_sdk"

    @property
    def init_error(self) -> str | None:
        return self._init_error

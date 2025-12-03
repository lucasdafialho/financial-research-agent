import time
from abc import ABC, abstractmethod
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.exceptions import AgentError
from src.core.types import AgentState


class BaseAgent(ABC, LoggerMixin):
    """Abstract base class for all agents in the system."""

    name: str = "base_agent"
    description: str = "Base agent"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm = self._create_llm()

    def _create_llm(self) -> ChatOpenAI | ChatAnthropic:
        """Create the LLM client based on settings."""
        if self._settings.llm_provider == "openai":
            api_key = self._settings.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API key required")
            return ChatOpenAI(
                model=self._settings.llm_model,
                temperature=self._settings.llm_temperature,
                max_tokens=self._settings.llm_max_tokens,
                api_key=api_key.get_secret_value(),
            )
        else:
            api_key = self._settings.anthropic_api_key
            if not api_key:
                raise ValueError("Anthropic API key required")
            return ChatAnthropic(
                model=self._settings.llm_model,
                temperature=self._settings.llm_temperature,
                max_tokens=self._settings.llm_max_tokens,
                api_key=api_key.get_secret_value(),
            )

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent's main logic and return updated state."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    async def invoke_llm(
        self,
        user_message: str,
        system_message: str | None = None,
    ) -> str:
        """Invoke the LLM with the given messages."""
        messages = []

        if system_message:
            messages.append(SystemMessage(content=system_message))
        else:
            messages.append(SystemMessage(content=self.system_prompt))

        messages.append(HumanMessage(content=user_message))

        start_time = time.perf_counter()

        try:
            response = await self._llm.ainvoke(messages)
            duration_ms = (time.perf_counter() - start_time) * 1000

            self.log_operation(
                f"{self.name}_llm_invoke",
                status="success",
                duration_ms=duration_ms,
            )

            return str(response.content)

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_operation(
                f"{self.name}_llm_invoke",
                status="failed",
                duration_ms=duration_ms,
                error=str(e),
            )
            raise AgentError(
                message=f"LLM invocation failed: {str(e)}",
                agent_name=self.name,
            )

    def update_state(
        self,
        state: AgentState,
        updates: dict[str, Any],
    ) -> AgentState:
        """Update the agent state with new values."""
        new_state = dict(state)
        new_state.update(updates)
        new_state["current_agent"] = self.name

        completed = list(new_state.get("completed_agents", []))
        if self.name not in completed:
            completed.append(self.name)
        new_state["completed_agents"] = completed

        return AgentState(**new_state)

    def add_error(
        self,
        state: AgentState,
        error: Exception,
    ) -> AgentState:
        """Add an error to the state."""
        errors = list(state.get("errors", []))
        errors.append(
            {
                "agent": self.name,
                "error": str(error),
                "type": type(error).__name__,
            }
        )
        return self.update_state(state, {"errors": errors})

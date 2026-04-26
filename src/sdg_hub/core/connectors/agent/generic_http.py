# SPDX-License-Identifier: Apache-2.0
"""Generic HTTP agent connector for arbitrary REST chat endpoints."""

from typing import Any, Optional
import uuid

from mlflow.types.agent import ChatAgentMessage, ChatAgentRequest, ChatAgentResponse
from pydantic import Field, field_validator

from ...utils.logger_config import setup_logger
from ..exceptions import ConnectorError
from ..registry import ConnectorRegistry
from .base import BaseAgentConnector

logger = setup_logger(__name__)


def _set_nested(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-notation path."""
    keys = path.split(".")
    for key in keys[:-1]:
        obj = obj.setdefault(key, {})
    obj[keys[-1]] = value


def _get_nested(obj: dict[str, Any], path: str) -> Any:
    """Get a value from a nested dict using dot-notation path.

    Returns None if any key in the path is missing.
    """
    for key in path.split("."):
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


@ConnectorRegistry.register("generic_http")
class GenericHTTPConnector(BaseAgentConnector):
    """Connector for arbitrary REST chat endpoints.

    Uses declarative JSON path configuration to map between the standardized
    request/response models and an arbitrary REST API shape.
    """

    request_message_path: str = Field(
        ...,
        min_length=1,
        description=(
            "Dot-notation path where the message content is placed "
            "in the request body (e.g., 'input.question')."
        ),
    )
    response_text_path: str = Field(
        ...,
        min_length=1,
        description=(
            "Dot-notation path to extract text from the response "
            "(e.g., 'output.answer')."
        ),
    )
    response_session_id_path: Optional[str] = Field(
        None,
        description="Dot-notation path to extract session ID from the response.",
    )
    request_session_id_path: Optional[str] = Field(
        None,
        description="Dot-notation path where session ID is placed in the request body.",
    )

    @field_validator(
        "request_message_path",
        "response_text_path",
        "request_session_id_path",
        "response_session_id_path",
    )
    @classmethod
    def validate_path_format(cls, v: str | None) -> str | None:
        """Validate that path contains only valid dot-notation segments."""
        if v is None:
            return v
        for segment in v.split("."):
            if not segment:
                raise ValueError(
                    f"Invalid path '{v}': empty segment. "
                    f"Use dot-notation like 'output.answer'."
                )
        return v

    def build_request(
        self,
        request: ChatAgentRequest | list[dict[str, Any]],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Build request payload by placing message content at the configured path.

        The connector now accepts ``ChatAgentRequest`` for standardized execution.
        A legacy ``(messages, session_id)`` call shape is still accepted to remain
        backward-compatible with direct connector tests and custom integrations.
        """
        messages: list[ChatAgentMessage] | list[dict[str, Any]]
        resolved_session_id: str

        if isinstance(request, ChatAgentRequest):
            messages = request.messages
            resolved_session_id = (
                request.context.conversation_id if request.context else ""
            ) or ""
        else:
            messages = request
            resolved_session_id = session_id or ""

        content = self._extract_last_user_message(messages)

        payload: dict[str, Any] = {}
        _set_nested(payload, self.request_message_path, content)

        if self.request_session_id_path:
            message_path = self.request_message_path
            configured_session_path = self.request_session_id_path
            if (
                message_path == configured_session_path
                or message_path.startswith(f"{configured_session_path}.")
                or configured_session_path.startswith(f"{message_path}.")
            ):
                raise ConnectorError(
                    "request_message_path and request_session_id_path must not overlap"
                )
            _set_nested(payload, configured_session_path, resolved_session_id)

        return payload

    def parse_response(self, response: dict[str, Any]) -> ChatAgentResponse:
        """Parse endpoint output into a standardized ``ChatAgentResponse``."""
        if not isinstance(response, dict):
            raise ConnectorError(
                f"Expected dict response, got {type(response).__name__}"
            )

        text = _get_nested(response, self.response_text_path)
        assistant_text = "" if text is None else str(text)
        messages = [
            ChatAgentMessage(
                role="assistant",
                content=assistant_text,
                id=str(uuid.uuid4()),
            )
        ]

        custom_outputs: dict[str, Any] | None = None
        if self.response_session_id_path:
            extracted_session_id = _get_nested(response, self.response_session_id_path)
            if extracted_session_id is not None:
                custom_outputs = {"session_id": str(extracted_session_id)}

        return ChatAgentResponse(
            messages=messages,
            custom_outputs=custom_outputs,
        )

    def _extract_last_user_message(
        self,
        messages: list[ChatAgentMessage] | list[dict[str, Any]],
    ) -> str:
        """Extract the last user message content."""
        for msg in reversed(messages):
            if isinstance(msg, ChatAgentMessage):
                role = msg.role
                content = msg.content
            else:
                role = msg.get("role")
                content = msg.get("content")

            if role == "user" and content:
                return str(content)

        raise ConnectorError(
            "No user message found in messages. "
            "Expected at least one message with role='user' and content."
        )

    @classmethod
    def extract_text(cls, response: ChatAgentResponse) -> str | None:
        """Extract assistant text from a standardized response."""
        for msg in reversed(response.messages):
            if msg.role == "assistant" and msg.content:
                return msg.content
        return None

    @classmethod
    def extract_session_id(cls, response: ChatAgentResponse) -> str | None:
        """Extract session ID from ``custom_outputs`` if available."""
        if not response.custom_outputs:
            return None
        session_id = response.custom_outputs.get("session_id")
        if session_id is None:
            return None
        return str(session_id)

    @classmethod
    def extract_tool_trace(
        cls, response: ChatAgentResponse
    ) -> list[dict[str, Any]] | None:
        """Generic HTTP endpoints typically don't produce tool traces."""
        return None

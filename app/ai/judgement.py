"""
One answer to "Claude returned the wrong shape".

Four analysers repeat the same five steps around ``ClaudeClient.analyze`` --
load a prompt, build a context dict, call, validate, persist -- and each
answered a malformed response differently:

- ``deal_scorer:160``  sets every missing field to ``None`` and carries on, so
  a truncated response becomes a package with a null score and no error
- ``event_scorer:118`` uses ``result.get("relevance_score", 0.0)``, so a
  malformed response reads as a genuinely *bad* event rather than a failure
- ``itinerary_generator:318`` raises a real validation error

Three different error modes for the same condition, none documented at the
seam. This module states it once: a response that does not satisfy the
declared schema raises ``MalformedJudgement``, and callers decide what to do.

``ClaudeClient.analyze`` already hides cache keys, retry, JSON parsing and
cost tracking behind one call -- that seam is well placed and is left alone.
This sits just above it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from app.ai.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class MalformedJudgement(ValueError):
    """
    Claude's response did not satisfy the schema the caller declared.

    Attributes:
        operation: The analysis that was running, e.g. ``"deal_scoring"``.
        missing: Required fields that were absent.
        response: The raw response, for logging.
    """

    def __init__(
        self,
        operation: str,
        missing: Sequence[str],
        response: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.operation = operation
        self.missing = list(missing)
        self.response = dict(response or {})
        super().__init__(
            f"{operation}: response missing required field(s): "
            f"{', '.join(self.missing)}"
        )


@dataclass(frozen=True)
class JudgementSchema:
    """
    What a caller requires from a response.

    Attributes:
        required: Fields that must be present. Absent ones raise.
        optional: Fields filled with ``defaults`` when absent.
        defaults: Values for absent optional fields.
    """

    required: Sequence[str] = ()
    optional: Sequence[str] = ()
    defaults: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, response: Mapping[str, Any], operation: str) -> Dict[str, Any]:
        """
        Check a response and fill in optional defaults.

        Args:
            response: Parsed response from Claude.
            operation: Name used in the error message.

        Returns:
            A copy with optional defaults applied.

        Raises:
            MalformedJudgement: If any required field is missing.
        """
        missing = [key for key in self.required if key not in response]
        if missing:
            raise MalformedJudgement(operation, missing, response)

        result = dict(response)
        for key in self.optional:
            if key not in result:
                result[key] = self.defaults.get(key)
        return result


async def judge(
    claude,
    *,
    prompt_name: str,
    context: Mapping[str, Any],
    schema: JudgementSchema,
    operation: str,
    max_tokens: int = 2048,
    use_cache: bool = True,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run one analysis: load prompt, call Claude, validate the response.

    Every analyser goes through here, so a prompt is always loaded from
    ``app/ai/prompts/`` (two of the four used to build prompts inline, meaning
    editing a prompt file changed behaviour for some analysers and not others)
    and a malformed response always raises the same error.

    Args:
        claude: A ``ClaudeClient``.
        prompt_name: Template name under ``app/ai/prompts/``.
        context: Values the template needs.
        schema: What the response must contain.
        operation: Label for cost attribution and error messages.
        max_tokens: Response cap.
        use_cache: Whether to reuse a cached response.
        temperature: Sampling temperature, if the caller wants one.

    Returns:
        The validated response.

    Raises:
        MalformedJudgement: If the response does not satisfy ``schema``.
    """
    prompt = load_prompt(prompt_name)

    kwargs: Dict[str, Any] = {
        "prompt": prompt,
        "data": dict(context),
        "response_format": "json",
        "use_cache": use_cache,
        "max_tokens": max_tokens,
        "operation": operation,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = await claude.analyze(**kwargs)

    if not isinstance(response, Mapping):
        raise MalformedJudgement(operation, ["<response was not an object>"])

    return schema.validate(response, operation)

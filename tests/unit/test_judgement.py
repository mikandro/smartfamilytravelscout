"""
Unit tests for the AI judgement seam.

The regression these exist for: three analysers answered "Claude returned the
wrong shape" three different ways -- inject None, default to 0.0, or raise --
so a malformed response could silently become a null score or a genuinely
bad rating.
"""

from unittest.mock import AsyncMock

import pytest

from app.ai.judgement import JudgementSchema, MalformedJudgement, judge

pytestmark = pytest.mark.unit


class TestSchemaValidation:
    def test_passes_a_complete_response(self):
        schema = JudgementSchema(required=("score", "reasoning"))
        result = schema.validate({"score": 80, "reasoning": "good"}, "op")
        assert result["score"] == 80

    def test_raises_on_a_missing_required_field(self):
        schema = JudgementSchema(required=("score", "reasoning"))
        with pytest.raises(MalformedJudgement):
            schema.validate({"score": 80}, "deal_scoring")

    def test_error_names_every_missing_field(self):
        schema = JudgementSchema(required=("score", "reasoning", "confidence"))
        with pytest.raises(MalformedJudgement) as exc:
            schema.validate({"score": 80}, "deal_scoring")
        assert set(exc.value.missing) == {"reasoning", "confidence"}

    def test_error_names_the_operation(self):
        schema = JudgementSchema(required=("score",))
        with pytest.raises(MalformedJudgement) as exc:
            schema.validate({}, "event_scoring")
        assert exc.value.operation == "event_scoring"
        assert "event_scoring" in str(exc.value)

    def test_optional_fields_get_defaults(self):
        schema = JudgementSchema(
            required=("score",),
            optional=("highlights",),
            defaults={"highlights": []},
        )
        result = schema.validate({"score": 70}, "op")
        assert result["highlights"] == []

    def test_present_optional_fields_are_kept(self):
        schema = JudgementSchema(
            required=(), optional=("highlights",), defaults={"highlights": []}
        )
        result = schema.validate({"highlights": ["a"]}, "op")
        assert result["highlights"] == ["a"]

    def test_a_falsy_required_value_is_still_present(self):
        """0 and "" are values, not absences."""
        schema = JudgementSchema(required=("score",))
        assert schema.validate({"score": 0}, "op")["score"] == 0

    def test_does_not_mutate_the_response(self):
        schema = JudgementSchema(optional=("x",), defaults={"x": 1})
        original = {"score": 1}
        schema.validate(original, "op")
        assert "x" not in original


class TestJudge:
    async def test_loads_the_prompt_and_calls_claude(self):
        claude = AsyncMock()
        claude.analyze = AsyncMock(return_value={"score": 90, "reasoning": "ok"})

        result = await judge(
            claude,
            prompt_name="deal_analysis",
            context={"city": "Lisbon"},
            schema=JudgementSchema(required=("score", "reasoning")),
            operation="deal_scoring",
        )

        assert result["score"] == 90
        claude.analyze.assert_awaited_once()
        kwargs = claude.analyze.await_args.kwargs
        assert kwargs["operation"] == "deal_scoring"
        assert kwargs["response_format"] == "json"
        # The prompt came from a file, not an inline string.
        assert isinstance(kwargs["prompt"], str) and kwargs["prompt"]

    async def test_malformed_response_raises(self):
        claude = AsyncMock()
        claude.analyze = AsyncMock(return_value={"partial": True})

        with pytest.raises(MalformedJudgement):
            await judge(
                claude,
                prompt_name="deal_analysis",
                context={},
                schema=JudgementSchema(required=("score",)),
                operation="deal_scoring",
            )

    async def test_non_object_response_raises(self):
        claude = AsyncMock()
        claude.analyze = AsyncMock(return_value="not json")

        with pytest.raises(MalformedJudgement):
            await judge(
                claude,
                prompt_name="deal_analysis",
                context={},
                schema=JudgementSchema(),
                operation="deal_scoring",
            )

    async def test_temperature_is_only_passed_when_given(self):
        claude = AsyncMock()
        claude.analyze = AsyncMock(return_value={})

        await judge(
            claude,
            prompt_name="deal_analysis",
            context={},
            schema=JudgementSchema(),
            operation="op",
        )
        assert "temperature" not in claude.analyze.await_args.kwargs

        await judge(
            claude,
            prompt_name="deal_analysis",
            context={},
            schema=JudgementSchema(),
            operation="op",
            temperature=0.7,
        )
        assert claude.analyze.await_args.kwargs["temperature"] == 0.7


class TestScorerSchemas:
    """The concrete schemas the analysers declare."""

    def test_deal_schema_requires_a_score(self):
        from app.ai.deal_scorer import DEAL_SCHEMA

        with pytest.raises(MalformedJudgement):
            DEAL_SCHEMA.validate({"reasoning": "x"}, "deal_scoring")

    def test_deal_schema_defaults_highlights_and_concerns(self):
        from app.ai.deal_scorer import DEAL_SCHEMA

        complete = {
            "score": 80,
            "value_assessment": "good",
            "family_suitability": 9,
            "timing_quality": 8,
            "recommendation": "book_now",
            "confidence": 90,
            "reasoning": "because",
        }
        result = DEAL_SCHEMA.validate(complete, "deal_scoring")
        assert result["highlights"] == []
        assert result["concerns"] == []

    def test_event_schema_requires_relevance_score(self):
        """It used to default to 0.0, reading as a genuinely bad event."""
        from app.ai.event_scorer import EVENT_SCHEMA

        with pytest.raises(MalformedJudgement):
            EVENT_SCHEMA.validate({"reasoning": "x"}, "event_scoring")

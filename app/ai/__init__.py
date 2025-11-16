"""
AI services for SmartFamilyTravelScout.

This module provides integration with Claude API for intelligent
travel deal analysis, itinerary generation, and recommendations.
"""

from app.ai.claude_client import ClaudeClient, ClaudeAPIError
from app.ai.prompt_loader import PromptLoader, get_prompt_loader, load_prompt

__all__ = [
    "ClaudeClient",
    "ClaudeAPIError",
    "PromptLoader",
    "get_prompt_loader",
    "load_prompt",
]

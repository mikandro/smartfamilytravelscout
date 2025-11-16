"""
Prompt template loader and management utilities.

This module provides utilities for loading, managing, and validating
prompt templates used with Claude API.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"


class PromptLoader:
    """
    Load and manage prompt templates from files.

    Prompt templates are stored as text files in the prompts directory
    and can contain {variable} placeholders for formatting.

    Example:
        >>> loader = PromptLoader()
        >>> prompt = loader.load("deal_analysis")
        >>> formatted = prompt.format(deal_details="Flight to Lisbon €400")
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt template files.
                        Defaults to app/ai/prompts/
        """
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: Dict[str, str] = {}

        if not self.prompts_dir.exists():
            logger.warning(
                f"Prompts directory does not exist: {self.prompts_dir}. "
                f"Creating it now."
            )
            self.prompts_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized PromptLoader with directory: {self.prompts_dir}")

    def load(self, prompt_name: str, use_cache: bool = True) -> str:
        """
        Load a prompt template from a file.

        Args:
            prompt_name: Name of the prompt (without .txt extension)
            use_cache: Whether to use cached prompts (default: True)

        Returns:
            The prompt template as a string

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
        """
        # Check cache first
        if use_cache and prompt_name in self._cache:
            logger.debug(f"Loading prompt from cache: {prompt_name}")
            return self._cache[prompt_name]

        # Load from file
        prompt_path = self.prompts_dir / f"{prompt_name}.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {prompt_path}. "
                f"Available prompts: {self.list_prompts()}"
            )

        logger.info(f"Loading prompt template: {prompt_name}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()

        # Cache for future use
        if use_cache:
            self._cache[prompt_name] = prompt

        return prompt

    def save(self, prompt_name: str, prompt_content: str) -> Path:
        """
        Save a prompt template to a file.

        Args:
            prompt_name: Name of the prompt (without .txt extension)
            prompt_content: The prompt template content

        Returns:
            Path to the saved file
        """
        prompt_path = self.prompts_dir / f"{prompt_name}.txt"

        logger.info(f"Saving prompt template: {prompt_name}")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_content.strip())

        # Update cache
        self._cache[prompt_name] = prompt_content.strip()

        return prompt_path

    def list_prompts(self) -> list[str]:
        """
        List all available prompt templates.

        Returns:
            List of prompt names (without .txt extension)
        """
        if not self.prompts_dir.exists():
            return []

        prompts = [
            p.stem for p in self.prompts_dir.glob("*.txt") if p.is_file()
        ]
        return sorted(prompts)

    def reload(self, prompt_name: str) -> str:
        """
        Reload a prompt template, bypassing cache.

        Args:
            prompt_name: Name of the prompt to reload

        Returns:
            The reloaded prompt template
        """
        if prompt_name in self._cache:
            del self._cache[prompt_name]
        return self.load(prompt_name, use_cache=False)

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        logger.info("Clearing prompt cache")
        self._cache.clear()

    def validate_template(self, prompt_name: str, required_vars: list[str]) -> bool:
        """
        Validate that a prompt template contains required variables.

        Args:
            prompt_name: Name of the prompt to validate
            required_vars: List of required variable names

        Returns:
            True if all required variables are present, False otherwise
        """
        prompt = self.load(prompt_name)

        missing_vars = []
        for var in required_vars:
            if f"{{{var}}}" not in prompt:
                missing_vars.append(var)

        if missing_vars:
            logger.warning(
                f"Prompt '{prompt_name}' is missing variables: {missing_vars}"
            )
            return False

        logger.info(f"Prompt '{prompt_name}' validation successful")
        return True

    def get_template_variables(self, prompt_name: str) -> list[str]:
        """
        Extract all variable names from a prompt template.

        Args:
            prompt_name: Name of the prompt

        Returns:
            List of variable names found in the template
        """
        import re

        prompt = self.load(prompt_name)

        # Find all {variable} patterns
        variables = re.findall(r"\{(\w+)\}", prompt)

        return sorted(set(variables))


# Global prompt loader instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """
    Get the global PromptLoader instance (singleton pattern).

    Returns:
        Global PromptLoader instance
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def load_prompt(prompt_name: str) -> str:
    """
    Convenience function to load a prompt using the global loader.

    Args:
        prompt_name: Name of the prompt to load

    Returns:
        The prompt template string
    """
    return get_prompt_loader().load(prompt_name)

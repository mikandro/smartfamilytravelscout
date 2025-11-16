"""
Unit tests for PromptLoader.

Tests the prompt template loading and management functionality.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ai.prompt_loader import PromptLoader, get_prompt_loader, load_prompt


class TestPromptLoader:
    """Test suite for PromptLoader class."""

    @pytest.fixture
    def temp_prompts_dir(self):
        """Create a temporary directory for prompt templates."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def prompt_loader(self, temp_prompts_dir):
        """Create PromptLoader instance with temporary directory."""
        return PromptLoader(prompts_dir=temp_prompts_dir)

    @pytest.fixture
    def sample_prompt_files(self, temp_prompts_dir):
        """Create sample prompt template files."""
        # Create test prompt files
        (temp_prompts_dir / "test_prompt.txt").write_text(
            "Analyze this deal: {deal_details}"
        )
        (temp_prompts_dir / "simple_prompt.txt").write_text("Hello, world!")
        (temp_prompts_dir / "complex_prompt.txt").write_text(
            """
You are analyzing {destination} for {travelers} travelers.

Budget: {budget}
Duration: {duration} days

Provide a detailed analysis.
            """.strip()
        )
        return temp_prompts_dir

    def test_initialization(self, temp_prompts_dir):
        """Test PromptLoader initialization."""
        loader = PromptLoader(prompts_dir=temp_prompts_dir)

        assert loader.prompts_dir == temp_prompts_dir
        assert isinstance(loader._cache, dict)
        assert len(loader._cache) == 0

    def test_initialization_creates_directory(self):
        """Test that PromptLoader creates directory if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            nonexistent_dir = Path(tmpdir) / "prompts"
            assert not nonexistent_dir.exists()

            loader = PromptLoader(prompts_dir=nonexistent_dir)

            assert nonexistent_dir.exists()
            assert nonexistent_dir.is_dir()

    def test_load_existing_prompt(self, prompt_loader, sample_prompt_files):
        """Test loading an existing prompt template."""
        prompt = prompt_loader.load("test_prompt")

        assert prompt == "Analyze this deal: {deal_details}"

    def test_load_caches_prompt(self, prompt_loader, sample_prompt_files):
        """Test that loaded prompts are cached."""
        # Load prompt first time
        prompt1 = prompt_loader.load("test_prompt")

        # Verify it's in cache
        assert "test_prompt" in prompt_loader._cache

        # Load again - should use cache
        prompt2 = prompt_loader.load("test_prompt")

        assert prompt1 == prompt2

    def test_load_without_cache(self, prompt_loader, sample_prompt_files):
        """Test loading prompt without using cache."""
        prompt = prompt_loader.load("test_prompt", use_cache=False)

        # Should not be in cache
        assert "test_prompt" not in prompt_loader._cache
        assert prompt == "Analyze this deal: {deal_details}"

    def test_load_nonexistent_prompt(self, prompt_loader):
        """Test loading a non-existent prompt raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            prompt_loader.load("nonexistent_prompt")

        assert "Prompt template not found" in str(exc_info.value)
        assert "Available prompts" in str(exc_info.value)

    def test_save_prompt(self, prompt_loader, temp_prompts_dir):
        """Test saving a new prompt template."""
        prompt_content = "This is a new prompt about {topic}"

        saved_path = prompt_loader.save("new_prompt", prompt_content)

        # Verify file was created
        assert saved_path.exists()
        assert saved_path == temp_prompts_dir / "new_prompt.txt"

        # Verify content
        assert saved_path.read_text() == prompt_content

        # Verify it's cached
        assert "new_prompt" in prompt_loader._cache

    def test_save_updates_existing(self, prompt_loader, sample_prompt_files):
        """Test that save overwrites existing prompt."""
        new_content = "Updated content for {variable}"

        prompt_loader.save("test_prompt", new_content)

        # Verify file was updated
        loaded = prompt_loader.load("test_prompt", use_cache=False)
        assert loaded == new_content

    def test_list_prompts(self, prompt_loader, sample_prompt_files):
        """Test listing all available prompts."""
        prompts = prompt_loader.list_prompts()

        assert len(prompts) == 3
        assert "test_prompt" in prompts
        assert "simple_prompt" in prompts
        assert "complex_prompt" in prompts
        assert prompts == sorted(prompts)  # Should be sorted

    def test_list_prompts_empty_directory(self, prompt_loader):
        """Test listing prompts in empty directory."""
        prompts = prompt_loader.list_prompts()

        assert prompts == []

    def test_reload_prompt(self, prompt_loader, sample_prompt_files):
        """Test reloading a prompt bypasses cache."""
        # Load and cache original
        original = prompt_loader.load("test_prompt")
        assert "test_prompt" in prompt_loader._cache

        # Modify the file directly
        prompt_file = sample_prompt_files / "test_prompt.txt"
        prompt_file.write_text("Modified content: {new_var}")

        # Reload should get new content
        reloaded = prompt_loader.reload("test_prompt")

        assert reloaded != original
        assert reloaded == "Modified content: {new_var}"
        assert "test_prompt" in prompt_loader._cache
        assert prompt_loader._cache["test_prompt"] == reloaded

    def test_clear_cache(self, prompt_loader, sample_prompt_files):
        """Test clearing the prompt cache."""
        # Load some prompts to populate cache
        prompt_loader.load("test_prompt")
        prompt_loader.load("simple_prompt")

        assert len(prompt_loader._cache) == 2

        # Clear cache
        prompt_loader.clear_cache()

        assert len(prompt_loader._cache) == 0

    def test_validate_template_success(self, prompt_loader, sample_prompt_files):
        """Test validating a template with all required variables."""
        is_valid = prompt_loader.validate_template(
            "complex_prompt", ["destination", "travelers", "budget", "duration"]
        )

        assert is_valid is True

    def test_validate_template_missing_vars(self, prompt_loader, sample_prompt_files):
        """Test validating a template with missing variables."""
        is_valid = prompt_loader.validate_template(
            "complex_prompt", ["destination", "travelers", "missing_var"]
        )

        assert is_valid is False

    def test_validate_template_extra_vars_ok(self, prompt_loader, sample_prompt_files):
        """Test that validation passes if required vars are present (extra vars in template ok)."""
        is_valid = prompt_loader.validate_template(
            "complex_prompt", ["destination"]  # Only require one var
        )

        assert is_valid is True

    def test_get_template_variables(self, prompt_loader, sample_prompt_files):
        """Test extracting variables from a template."""
        variables = prompt_loader.get_template_variables("complex_prompt")

        assert len(variables) == 4
        assert "destination" in variables
        assert "travelers" in variables
        assert "budget" in variables
        assert "duration" in variables
        assert variables == sorted(variables)  # Should be sorted

    def test_get_template_variables_no_vars(self, prompt_loader, sample_prompt_files):
        """Test extracting variables from template with no variables."""
        variables = prompt_loader.get_template_variables("simple_prompt")

        assert variables == []

    def test_get_template_variables_single_var(
        self, prompt_loader, sample_prompt_files
    ):
        """Test extracting variables from template with one variable."""
        variables = prompt_loader.get_template_variables("test_prompt")

        assert len(variables) == 1
        assert variables == ["deal_details"]

    def test_get_template_variables_deduplication(self, prompt_loader):
        """Test that duplicate variables are deduplicated."""
        # Create a prompt with duplicate variables
        prompt_loader.save(
            "duplicate_vars", "Process {item} and then {item} again with {other}"
        )

        variables = prompt_loader.get_template_variables("duplicate_vars")

        assert len(variables) == 2
        assert "item" in variables
        assert "other" in variables

    def test_global_prompt_loader(self):
        """Test the global prompt loader singleton."""
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()

        # Should return the same instance
        assert loader1 is loader2

    def test_load_prompt_convenience_function(self, temp_prompts_dir):
        """Test the convenience load_prompt function."""
        # Create a prompt file
        (temp_prompts_dir / "test.txt").write_text("Test content")

        # Note: This test uses the global loader, so we can't easily
        # control the directory. We'll just test that it doesn't crash
        # when trying to load a non-existent prompt.
        with pytest.raises(FileNotFoundError):
            load_prompt("definitely_does_not_exist")

    def test_strips_whitespace(self, prompt_loader):
        """Test that saved prompts have whitespace stripped."""
        prompt_content = "\n\n  This has whitespace  \n\n"

        prompt_loader.save("whitespace_test", prompt_content)

        loaded = prompt_loader.load("whitespace_test")
        assert loaded == "This has whitespace"
        assert not loaded.startswith(" ")
        assert not loaded.endswith(" ")

    def test_load_multiline_prompt(self, prompt_loader, sample_prompt_files):
        """Test loading a multiline prompt template."""
        prompt = prompt_loader.load("complex_prompt")

        assert "{destination}" in prompt
        assert "{travelers}" in prompt
        assert "\n" in prompt  # Should preserve newlines

    def test_non_txt_files_ignored(self, prompt_loader, temp_prompts_dir):
        """Test that non-.txt files are ignored in listing."""
        # Create various file types
        (temp_prompts_dir / "valid.txt").write_text("Valid prompt")
        (temp_prompts_dir / "readme.md").write_text("Not a prompt")
        (temp_prompts_dir / "script.py").write_text("Also not a prompt")

        prompts = prompt_loader.list_prompts()

        assert len(prompts) == 1
        assert prompts == ["valid"]

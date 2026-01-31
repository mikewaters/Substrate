from ontology.utils.slug import generate_slug


class TestTopicRepositorySlugGeneration:
    """Tests for slug generation."""

    def test_generate_slug_basic(self) -> None:
        """Test basic slug generation."""
        slug = generate_slug("Hello World")
        assert slug == "hello-world"

    def test_generate_slug_with_special_chars(self) -> None:
        """Test slug generation with special characters."""
        slug = generate_slug("Hello, World! @ 2024")
        assert slug == "hello-world-2024"

    def test_generate_slug_with_multiple_spaces(self) -> None:
        """Test slug generation with multiple spaces."""
        slug = generate_slug("Hello    World")
        assert slug == "hello-world"

    def test_generate_slug_with_unicode(self) -> None:
        """Test slug generation with unicode characters."""
        slug = generate_slug("Café Münchën")
        # Unicode characters are preserved in lowercase
        assert slug == "café-münchën"

"""Tests for text preprocessing in services/preprocessor.py."""

from api.services.preprocessor import detect_and_extract, extract_text_from_markdown


class TestExtractTextFromMarkdown:
    def test_strips_yaml_frontmatter(self):
        content = "---\ntitle: test\nauthor: me\n---\n# Hello World"
        result = extract_text_from_markdown(content)
        assert result == "# Hello World"

    def test_no_frontmatter_unchanged(self):
        content = "# Just markdown\nSome text"
        result = extract_text_from_markdown(content)
        assert "# Just markdown" in result
        assert "Some text" in result

    def test_empty_string(self):
        assert extract_text_from_markdown("") == ""

    def test_frontmatter_only(self):
        content = "---\nfoo: bar\n---\n"
        result = extract_text_from_markdown(content)
        assert result == ""


class TestDetectAndExtract:
    def test_markdown_mime(self):
        content = "---\nfoo: bar\n---\nactual content"
        result = detect_and_extract(content, "text/markdown")
        assert result == "actual content"

    def test_plain_text_passthrough(self):
        assert detect_and_extract("hello world", "text/plain") == "hello world"

    def test_unknown_mime_passthrough(self):
        assert detect_and_extract("raw", "application/octet-stream") == "raw"

import pytest
from src.notion_to_md.utils import md
import aiohttp
from unittest.mock import patch, Mock
from src.notion_to_md.notion_to_md import NotionToMarkdown
import unittest

@pytest.fixture
def notion_to_md():
    return NotionToMarkdown(notion_client=None)  # Mock client for testing

class TestCallout:
    def test_callout_without_emoji(self):
        text = "Call out text content."
        assert md.callout(text) == f"> {text}"

    def test_callout_with_emoji(self):
        text = "Call out text content."
        assert md.callout(text, {"type": "emoji", "emoji": "😍"}) == "> 😍 Call out text content."

class TestMarkdownTable:
    def test_simple_table(self):
        mock_table = [
            ["number", "char"],
            ["1", "a"],
            ["2", "b"]
        ]
        expected = (
            "| number | char |\n"
            "| ------ | ---- |\n"
            "| 1      | a    |\n"
            "| 2      | b    |"
        ).strip()
        assert md.table(mock_table).strip() == expected

class TestTextAnnotations:
    def test_inline_code(self):
        assert md.inline_code("simple text") == "`simple text`"

    def test_code_block(self):
        assert md.code_block("simple text", "javascript") == (
            "```javascript\n"
            "simple text\n"
            "```"
        )

    def test_inline_equation(self):
        assert md.inline_equation("E = mc^2") == "$E = mc^2$"

    def test_equation_block(self):
        assert md.equation("E = mc^2") == (
            "$$\n"
            "E = mc^2\n"
            "$$"
        )

    def test_bold(self):
        assert md.bold("simple text") == "**simple text**"

    def test_italic(self):
        assert md.italic("simple text") == "_simple text_"

    def test_strikethrough(self):
        assert md.strikethrough("simple text") == "~~simple text~~"

    def test_underline(self):
        assert md.underline("simple text") == "<u>simple text</u>"

    def test_empty_annotations(self):
        assert md.bold("") == "**"
        assert md.italic("") == "__"
        assert md.strikethrough("") == "~~~~"
        assert md.underline("") == "<u></u>"

class TestHeadings:
    def test_heading1(self):
        assert md.heading1("simple text") == "# simple text"

    def test_heading2(self):
        assert md.heading2("simple text") == "## simple text"

    def test_heading3(self):
        assert md.heading3("simple text") == "### simple text"

class TestListElements:
    def test_bullet(self):
        assert md.bullet("simple text") == "- simple text"

    def test_checked_todo(self):
        assert md.todo("simple text", True) == "- [x] simple text"

    def test_unchecked_todo(self):
        assert md.todo("simple text", False) == "- [ ] simple text"

class TestImage:
    @pytest.mark.asyncio
    async def test_image_with_alt_text(self):
        result = await md.image("simple text", "https://example.com/image", False)
        assert result == "![simple text](https://example.com/image)"

    @pytest.mark.asyncio
    async def test_image_to_base64(self, monkeypatch):
        async def mock_get(*args, **kwargs):
            class MockResponse:
                async def read(self):
                    return b"mock_image_data"
                status = 200
            return MockResponse()

        async def mock_session():
            class MockSession:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                async def get(self, *args, **kwargs):
                    return await mock_get()
            return MockSession()

        monkeypatch.setattr(aiohttp, "ClientSession", mock_session)
        
        result = await md.image("simple text", "https://example.com/image", True)
        assert "data:image/png;base64," in result

    @pytest.mark.asyncio
    async def test_image_base64_preserves_existing(self):
        existing_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA..."
        result = await md.image("simple text", existing_base64, True)
        assert result == f"![simple text]({existing_base64})"

class TestToggle:
    def test_displays_content_if_title_empty(self):
        assert md.toggle(None, "content").strip() == "content"

    def test_empty_title_and_content(self):
        assert md.toggle(None, None).strip() == ""

    def test_displays_toggle_with_details(self):
        result = md.toggle("title", "content").replace(" ", "").strip()
        assert result == "<details><summary>title</summary>content</details>"

class TestQuote:
    def test_single_line_quote(self):
        assert md.quote("text") == "> text"

    def test_multiline_quote(self):
        assert md.quote("line1\nline2") == "> line1\n> line2"

class TestLink:
    def test_basic_link(self):
        assert md.link("text", "https://example.com") == "[text](https://example.com)"

    def test_link_with_special_chars(self):
        assert md.link("te[x]t", "https://exa(m)ple.com") == "[te[x]t](https://exa(m)ple.com)"

def test_callout_basic():
    assert md.callout("Note") == "> Note"

def test_callout_with_heading():
    assert md.callout("# Heading\nContent") == "> # Heading\n> Content"

def test_text_annotations():
    assert md.inline_code("code") == "`code`"
    assert md.bold("text") == "**text**"
    assert md.italic("text") == "_text_"
    assert md.strikethrough("text") == "~~text~~"
    assert md.underline("text") == "<u>text</u>"

def test_code_blocks():
    assert md.code_block("console.log()", "javascript") == "```javascript\nconsole.log()\n```"
    assert md.code_block("text", "plain text") == "```text\ntext\n```"

def test_equations():
    assert md.inline_equation("E=mc^2") == "$E=mc^2$"
    assert md.equation("E=mc^2") == "$$\nE=mc^2\n$$"

def test_headings():
    assert md.heading1("Title") == "# Title"
    assert md.heading2("Title") == "## Title" 
    assert md.heading3("Title") == "### Title"

def test_lists():
    assert md.bullet("item") == "- item"
    assert md.bullet("item", 5) == "5. item"
    assert md.todo("task", True) == "- [x] task"
    assert md.todo("task", False) == "- [ ] task"

def test_quote():
    assert md.quote("line1\nline2") == "> line1\n> line2"

def test_divider():
    assert md.divider() == "---"

@pytest.mark.asyncio
async def test_image_base64_conversion(monkeypatch):
    async def mock_get(*args, **kwargs):
        class MockResponse:
            async def read(self):
                return b"mock_image_data"
            async def raise_for_status(self):
                pass
        return MockResponse()

    async def mock_session():
        class MockSession:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, *args, **kwargs):
                return await mock_get()
        return MockSession()

    monkeypatch.setattr(aiohttp, "ClientSession", mock_session)
    
    result = await md.image("alt", "http://fake.url", True)
    assert result == "![alt](data:image/png;base64,bW9ja19pbWFnZV9kYXRh)"

@pytest.mark.asyncio
async def test_image_base64_preserves_mime_type():
    href = "data:image/jpeg;base64,/9j/4AAQSkZJRgABA..."
    result = await md.image("alt", href, True)
    assert "data:image/jpeg;base64" in result

def test_toggle_behavior():
    assert md.toggle(None, "content") == "content"
    assert md.toggle("", "") == ""
    assert md.toggle("Summary", "Content") == "<details><summary>Summary</summary>Content</details>"

def test_link():
    assert md.link("Example", "https://example.com") == "[Example](https://example.com)"

def test_empty_annotations():
    assert md.bold("") == "****"
    assert md.italic("   ") == "_   _"

def test_special_characters():
    assert md.link("Te[]xt", "https://exa(m)ple.com") == "[Te[]xt](https://exa(m)ple.com)"

@pytest.mark.asyncio
async def test_synced_block(notion_to_md):
    mock_block = {
        "type": "synced_block",
        "synced_block": {
            "synced_from": {"block_id": "source123"},
            "children": [{"paragraph": {"text": "Synced content"}}]
        }
    }
    
    with patch("notion2md.utils.notion.get_block_children") as mock_get:
        mock_get.return_value = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        result = await notion_to_md.block_to_markdown(mock_block)
        assert "Synced content" in result

def test_child_database_block():
    block = {
        "type": "child_database",
        "child_database": {"title": "Tasks"}
    }
    result = notion_to_md.handle_child_database(block)
    assert "## Tasks" in result
    assert "| Property | Type | Content |" in result

@pytest.mark.parametrize("media_type", ["audio", "video", "pdf"])
def test_media_blocks(media_type):
    block = {
        media_type: {
            "caption": [{"plain_text": "Demo"}],
            "external": {"url": "https://example.com/media"}
        }
    }
    result = notion_to_md.handle_media_block(block, media_type)
    assert f"[{media_type.upper()}: Demo](https://example.com/media)" in result

def test_callout_multiline_heading():
    result = md.callout("# Heading\nLine2")
    assert result == "> # Heading\n> Line2"

class TestCustomTransformers(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.n2m = NotionToMarkdown(self.mock_client)

    async def test_block_to_markdown_sends_block_to_custom_transformer(self):
        """Test that blockToMarkdown sends parsing block to customTransformer"""
        custom_transformer_mock = Mock()
        self.n2m.set_custom_transformer("test", custom_transformer_mock)
        
        test_block = {
            "id": "test",
            "name": "test", 
            "type": "test",
            "test": {"foo": "bar"}
        }
        
        await self.n2m.block_to_markdown(test_block)
        custom_transformer_mock.assert_called_with(test_block)

    async def test_supports_only_one_custom_transformer_per_type(self):
        """Test that only one customTransformer is supported per type"""
        custom_transformer_mock1 = Mock()
        custom_transformer_mock2 = Mock()
        
        self.n2m.set_custom_transformer("test", custom_transformer_mock1)
        self.n2m.set_custom_transformer("test", custom_transformer_mock2)
        
        test_block = {
            "id": "test",
            "name": "test",
            "type": "test", 
            "test": {"foo": "bar"}
        }
        
        await self.n2m.block_to_markdown(test_block)
        custom_transformer_mock1.assert_not_called()
        custom_transformer_mock2.assert_called_once()

    async def test_custom_transformer_implementation(self):
        """Test that customTransformer implementation works"""
        async def custom_transformer_mock(block):
            return "hello"
            
        self.n2m.set_custom_transformer("divider", custom_transformer_mock)
        
        md = await self.n2m.block_to_markdown({
            "id": "test",
            "type": "divider",
            "divider": {},
            "object": "block"
        })
        
        self.assertEqual(md, "hello")

    async def test_custom_transformer_default_implementation(self):
        """Test that customTransformer default implementation works"""
        async def custom_transformer_mock(block):
            return False
            
        self.n2m.set_custom_transformer("divider", custom_transformer_mock)
        
        md = await self.n2m.block_to_markdown({
            "id": "test",
            "type": "divider",
            "divider": {},
            "object": "block"
        })
        
        self.assertEqual(md, "---")

if __name__ == '__main__':
    unittest.main()

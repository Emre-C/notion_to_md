# notion_to_md (Python)

Convert Notion pages to clean, readable Markdown. Python port of [notion-to-md](https://github.com/souvikinator/notion-to-md).

## Quick Start

1. Install the package:
```bash
pip install notion_to_md
```

2. Basic usage:
```python
from notion_client import AsyncClient
from notion_to_md import NotionToMarkdown

async def convert_page(notion_token: str, page_id: str) -> str:
    # Initialize clients
    notion = AsyncClient(auth=notion_token)
    n2m = NotionToMarkdown(notion_client=notion)
    
    # Convert page to markdown
    md_blocks = await n2m.page_to_markdown(page_id)
    md_string = await n2m.to_markdown_string(md_blocks)
    
    return md_string['parent']  # Returns the main page content

# Usage
result = await convert_page("your-notion-token", "your-page-id")
print(result)
```

## Features

- 🎯 Supports all common Notion blocks (text, lists, tables, code, etc.)
- 📝 Preserves formatting (bold, italic, code, colors)
- 🖼️ Handles images (with optional base64 conversion)
- 📑 Supports nested content (child pages, synced blocks)
- ⚡ Modern async/await API
- 🔁 Built-in error handling and API retry logic

## Configuration

Control the converter's behavior with configuration options:

```python
from notion_to_md import NotionToMarkdown, ConfigurationOptions

n2m = NotionToMarkdown(
    notion_client=notion,
    config=ConfigurationOptions(
        # Core Options
        separate_child_page=False,  # True to split child pages into separate files
        parse_child_pages=True,     # False to skip child pages entirely
        
        # Image Handling
        convert_images_to_base64=False,  # True to embed images as base64
        
        # API Behavior
        api_retry_attempts=3,          # Number of retries for failed API calls
        api_rate_limit_delay=0.5,      # Delay between API calls
        max_concurrent_requests=5,      # Max concurrent API requests
        
        # Debugging
        debug_mode=False               # Enable detailed error tracking
    )
)
```

## Advanced Usage

### 1. Handling Child Pages

```python
# Convert page with child pages as separate files
md_blocks = await n2m.page_to_markdown(page_id)
md_string = await n2m.to_markdown_string(md_blocks)

# Main page content
main_content = md_string['parent']

# Child pages (if separate_child_page=True)
for page_id, content in md_string.items():
    if page_id != 'parent':
        # Each child page content
        print(f"Child page {page_id}: {content}")
```

### 2. Custom Block Transformers

Add custom handling for specific block types:

```python
def custom_code_block(block):
    """Custom transformer for code blocks"""
    if block["type"] != "code":
        return False  # Let default handler process it
        
    language = block["code"].get("language", "")
    code = "".join(text["plain_text"] for text in block["code"].get("rich_text", []))
    return f"```{language}\n{code}\n```"

# Register the transformer
n2m.set_custom_transformer("code", custom_code_block)
```

### 3. Error Handling and Debugging

Enable debug mode for detailed error tracking:

```python
n2m = NotionToMarkdown(
    notion_client=notion,
    config=ConfigurationOptions(debug_mode=True)
)

# Convert your page
md_blocks = await n2m.page_to_markdown(page_id)

# Get debug information
debug_info = n2m.get_debug_info()
if debug_info:
    print(f"Success rate: {debug_info['success_rate']}")
    print(f"Errors: {len(debug_info['errors'])}")
    print(f"Unhandled types: {debug_info['unhandled_types']}")
```

## Complete Example

Here's a full example that exports a Notion page to a Markdown file with metadata:

```python
async def export_notion_page(notion_token: str, page_id: str, output_file: str):
    notion = AsyncClient(auth=notion_token)
    n2m = NotionToMarkdown(notion_client=notion)
    
    try:
        # Get page metadata
        page = await notion.pages.retrieve(page_id=page_id)
        title = page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')
        
        # Convert to markdown
        md_blocks = await n2m.page_to_markdown(page_id)
        md_string = await n2m.to_markdown_string(md_blocks)
        
        # Add metadata
        content = f"""---
title: {title}
notion_url: {page.get('url')}
last_edited: {page.get('last_edited_time')}
---

{md_string['parent']}"""
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"✓ Exported: {title} -> {output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
```

## Supported Content

### Block Types
- Text (paragraphs, headings)
- Lists (bulleted, numbered, to-do)
- Media (images, videos, files)
- Embeds (bookmarks, PDFs)
- Structural (tables, columns, toggles)
- Interactive (equations, code blocks)
- Organizational (child pages, databases)

### Text Formatting
- Basic (bold, italic, strikethrough)
- Code (inline, blocks)
- Colors (text and background)
- Links
- Equations

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT](LICENSE)
# notion_to_md (Python)

A Python library to convert Notion blocks into Markdown formatted text. This is a Python port of the popular [notion-to-md](https://github.com/souvikinator/notion-to-md) JavaScript library.

## Features

- 🔄 Converts Notion blocks to clean Markdown
- 🎯 Supports all common Notion block types
- 📝 Handles rich text annotations (bold, italic, code, etc.)
- 🖼️ Image conversion with base64 support
- 📑 Supports nested blocks and child pages
- 🔄 Handles synced blocks
- 📊 Database block support
- 🎨 Custom block transformer support
- ⚡ Async/await API
- 🔁 Automatic retry with exponential backoff for API calls

## Installation

```bash
pip install notion_to_md
```

## Usage

```python
from notion_to_md import NotionToMarkdown
from notion_client import Client

# Initialize the Notion client
notion = Client(auth="your-notion-api-key")

# Create NotionToMarkdown instance
n2m = NotionToMarkdown(notion_client=notion)

# Convert a page to markdown
async def convert_page(page_id: str):
    blocks = await n2m.get_block_children(block_id=page_id)
    markdown = await n2m.blocks_to_markdown(blocks)
    return markdown

# Configuration options
n2m.set_config({
    "separate_child_page": True,      # Create separate files for child pages
    "convert_images_to_base64": True, # Convert images to base64
    "parse_child_pages": True,        # Parse child pages
    "api_retry_attempts": 3,          # Number of API retry attempts
    "api_rate_limit_delay": 0.5,      # Delay between API calls
    "max_concurrent_requests": 5       # Maximum concurrent API requests
})

# Custom block transformer
async def custom_transformer(block):
    if block["type"] == "my_custom_block":
        return "Custom markdown output"
    return False  # Return False to use default transformer

n2m.set_custom_transformer("my_custom_block", custom_transformer)
```

## Supported Block Types

- Paragraphs
- Headings (H1, H2, H3)
- Bulleted lists
- Numbered lists
- To-do lists
- Toggle blocks
- Code blocks
- Images
- Videos
- Files
- PDFs
- Bookmarks
- Callouts
- Synced blocks
- Tables
- Columns
- Link previews
- Page links
- Equations
- Dividers
- Table of contents
- Child pages
- Child databases

## Text Annotations

The library supports all Notion text annotations:
- Bold
- Italic
- Strikethrough
- Underline
- Code
- Colors
- Links

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT](LICENSE)
# notion_to_md (Python)

A Python library to convert Notion blocks into Markdown formatted text. This is a Python port of the popular [notion-to-md](https://github.com/souvikinator/notion-to-md) JavaScript library so all kudos go to those wonderful folks.

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

## Quickstart Guide

Here's a complete example showing how to export Notion pages to Markdown files:

```python
import asyncio
from pathlib import Path
from notion_client import AsyncClient
from notion_to_md import NotionToMarkdown, ConfigurationOptions

async def export_notion_page(notion_token: str, page_id: str, output_dir: str = "exports"):
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize Notion client and NotionToMarkdown
    notion = AsyncClient(auth=notion_token)
    n2m = NotionToMarkdown(
        notion_client=notion,
        config=ConfigurationOptions(
            separate_child_page=True,      # Create separate files for child pages
            convert_images_to_base64=False, # Keep images as URLs
            parse_child_pages=True,        # Include child pages
            api_retry_attempts=3,          # Number of API retry attempts
            api_rate_limit_delay=0.5,      # Delay between API calls
            max_concurrent_requests=5       # Maximum concurrent API requests
        )
    )
    
    try:
        # Get page metadata
        page = await notion.pages.retrieve(page_id=page_id)
        title = page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')
        
        # Convert page to markdown
        md_blocks = await n2m.page_to_markdown(page_id)
        md_string = await n2m.to_markdown_string(md_blocks)
        
        if md_string:
            # Create markdown file
            file_name = f"{title.lower().replace(' ', '_')}.md"
            file_path = output_dir / file_name
            
            # Add metadata header
            content = f"""---
notion_url: {page.get('url')}
last_updated: {page.get('last_edited_time')}
---

{md_string['parent']}"""
            
            # Write to file
            file_path.write_text(content)
            print(f"✓ Exported: {title} to {file_path}")
            
            # Handle child pages if any
            if len(md_string) > 1:  # Has child pages
                child_dir = output_dir / file_name.replace('.md', '')
                child_dir.mkdir(parents=True, exist_ok=True)
                
                for child_id, child_content in md_string.items():
                    if child_id != 'parent' and child_content:
                        child_page = await notion.pages.retrieve(page_id=child_id)
                        child_title = child_page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')
                        child_file = child_dir / f"{child_title.lower().replace(' ', '_')}.md"
                        
                        # Add metadata to child page
                        child_content_with_meta = f"""---
notion_url: {child_page.get('url')}
last_updated: {child_page.get('last_edited_time')}
---

{child_content}"""
                        child_file.write_text(child_content_with_meta)
                        print(f"  ↳ Child page exported: {child_title}")
            
            return True
    except Exception as e:
        print(f"Error exporting page {page_id}: {str(e)}")
        return False

# Example usage
if __name__ == "__main__":
    NOTION_TOKEN = "your-notion-integration-token"
    PAGE_ID = "your-page-id"
    
    asyncio.run(export_notion_page(NOTION_TOKEN, PAGE_ID))

## Usage

```python
from notion_to_md import NotionToMarkdown, ConfigurationOptions
from notion_client import AsyncClient

# Initialize the Notion client
notion = AsyncClient(auth="your-notion-api-key")

# Create NotionToMarkdown instance with configuration
n2m = NotionToMarkdown(
    notion_client=notion,
    config=ConfigurationOptions(
        separate_child_page=True,      # Create separate files for child pages
        convert_images_to_base64=True, # Convert images to base64
        parse_child_pages=True,        # Parse child pages
        api_retry_attempts=3,          # Number of API retry attempts
        api_rate_limit_delay=0.5,      # Delay between API calls
        max_concurrent_requests=5       # Maximum concurrent API requests
    )
)

# Convert a page to markdown
async def convert_page(page_id: str):
    blocks = await n2m.get_block_children(block_id=page_id)
    markdown = await n2m.blocks_to_markdown(blocks)
    return markdown

# Custom block transformer (synchronous)
def custom_transformer(block):
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
- Audio blocks
- Embed blocks
- Breadcrumbs

## Text Annotations

The library supports these Notion text annotations:
- Bold
- Italic
- Strikethrough
- Underline
- Code
- Colors (including background colors)
- Links

Colors are rendered using HTML spans with Notion-specific CSS classes (e.g., `notion-red`, `notion-blue-background`, etc.). You'll need to include appropriate CSS styles to see the colors in your rendered markdown.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT](LICENSE)
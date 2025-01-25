"""Markdown formatting utilities."""

import base64
import logging
from typing import List, Optional, Dict
import re
from contextlib import asynccontextmanager
from aiohttp import ClientTimeout, ClientSession
from .types import CalloutIcon

# Pre-compile regex pattern
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+([.*\s\S]+)')

# Configure logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_client_session():
    """Create and manage aiohttp client session."""
    timeout = ClientTimeout(total=30)
    async with ClientSession(timeout=timeout) as session:
        yield session

async def image_to_base64(url: str) -> str:
    """Convert image URL to base64 string."""
    if not url:
        return ""
        
    if url.startswith("data:"):
        try:
            # Extract and normalize existing base64 data
            base64_data = url.split(",", 1)[-1]
            return f"data:image/png;base64,{base64_data}"
        except Exception as e:
            logger.error(f"Failed to process data URL: {e}")
            return url
            
    try:
        async with get_client_session() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    content_type = response.headers.get('content-type', 'image/png')
                    return f"data:{content_type};base64,{base64.b64encode(image_data).decode()}"
                logger.warning(f"Failed to fetch image, status: {response.status}")
    except Exception as e:
        logger.error(f"Failed to convert image to base64: {e}")
    return url

def inline_code(text: str) -> str:
    """Format text as inline code."""
    return f"`{text}`"

def inline_equation(text: str) -> str:
    """Format text as inline equation."""
    return f"${text}$"

def bold(text: str) -> str:
    """Format text as bold."""
    return f"**{text}**"

def italic(text: str) -> str:
    """Format text as italic."""
    return f"_{text}_"

def strikethrough(text: str) -> str:
    """Format text as strikethrough."""
    return f"~~{text}~~"

def underline(text: str) -> str:
    """Format text as underline."""
    return f"<u>{text}</u>"

def color(text: str, color_value: str) -> str:
    """Format text with color.
    
    Args:
        text: The text to color
        color_value: The color value from Notion (e.g., 'red', 'blue', 'gray', etc.)
        
    Returns:
        Text wrapped in HTML span with appropriate color class
    """
    # Map Notion colors to CSS classes
    color_map = {
        "default": "default",
        "gray": "gray",
        "brown": "brown",
        "orange": "orange",
        "yellow": "yellow",
        "green": "green",
        "blue": "blue",
        "purple": "purple",
        "pink": "pink",
        "red": "red",
        "gray_background": "gray-background",
        "brown_background": "brown-background",
        "orange_background": "orange-background",
        "yellow_background": "yellow-background",
        "green_background": "green-background",
        "blue_background": "blue-background",
        "purple_background": "purple-background",
        "pink_background": "pink-background",
        "red_background": "red-background"
    }
    
    css_class = color_map.get(color_value, "default")
    return f'<span class="notion-{css_class}">{text}</span>'

def link(text: str, href: str) -> str:
    """Format text as link."""
    return f"[{text}]({href})"

def code_block(text: str, language: Optional[str] = None) -> str:
    """Format text as code block."""
    if language == "plain text":
        language = "text"
    return f"```{language or ''}\n{text}\n```"

def equation(text: str) -> str:
    """Format text as equation block."""
    return f"$$\n{text}\n$$"

def heading1(text: str) -> str:
    """Format text as h1 heading."""
    return f"# {text}"

def heading2(text: str) -> str:
    """Format text as h2 heading."""
    return f"## {text}"

def heading3(text: str) -> str:
    """Format text as h3 heading."""
    return f"### {text}"

def quote(text: str) -> str:
    """Format text as quote."""
    return f"> {text.replace('\n', '\n> ')}"

def bullet(text: str, number: Optional[int] = None) -> str:
    """Format text as bullet point or numbered list item."""
    if number is not None:
        return f"{number}. {text}"
    return f"- {text}"

def todo(text: str, checked: bool = False) -> str:
    """Format text as todo item."""
    return f"- [{'x' if checked else ' '}] {text}"

def toggle(summary: Optional[str] = None, content: Optional[str] = None) -> str:
    """Format text as toggle/collapsible section."""
    if not summary:
        return content or ""
    return f"""<details>
<summary>{summary}</summary>
{content or ""}
</details>

"""

def divider() -> str:
    """Return markdown divider."""
    return "---"

def table(rows: List[List[str]]) -> str:
    """Format rows as markdown table."""
    if not rows:
        return ""
        
    # Escape pipe characters in content
    def escape_pipes(text: str) -> str:
        return str(text).replace("|", "\\|")
        
    # Ensure all rows have same number of columns
    max_cols = max(len(row) for row in rows) if rows else 0
    normalized_rows = [
        [escape_pipes(cell) for cell in (row + [""] * (max_cols - len(row)))]
        for row in rows
    ]
    
    # Create header row if none exists
    if len(normalized_rows) == 1:
        header = [""] * len(normalized_rows[0])
        normalized_rows.insert(0, header)
        
    # Calculate column widths
    col_widths = []
    for col in range(max_cols):
        col_widths.append(
            max(len(str(row[col]).replace("\n", "<br>"))
                for row in normalized_rows)
        )
        
    # Format rows
    table_rows = []
    for i, row in enumerate(normalized_rows):
        # Format and pad each cell
        cells = [
            str(cell).replace("\n", "<br>").ljust(col_widths[j])
            for j, cell in enumerate(row)
        ]
        table_rows.append(f"| {' | '.join(cells)} |")
        
        # Add separator after header
        if i == 0:
            separators = ["-" * width for width in col_widths]
            table_rows.append(f"| {' | '.join(separators)} |")
            
    return "\n".join(table_rows)

def add_tab_space(text: str, n: int = 0) -> str:
    """Add tab spaces for nested content."""
    if n <= 0:
        return text
        
    tab = "\t"  # Use tab character instead of spaces
    result = text
    
    for _ in range(n):
        if "\n" in result:
            # Handle multiline text
            lines = result.split("\n")
            result = tab + ("\n" + tab).join(lines)
        else:
            result = tab + result
            
    return result

async def image(title: str, url: str, convert_to_base64: bool = False) -> str:
    """Format image with optional base64 conversion."""
    if not url:
        return ""
        
    title = str(title).replace('"', '\\"')  # Escape quotes in title
        
    if not convert_to_base64 or url.startswith("data:"):
        if url.startswith("data:"):
            try:
                base64_data = url.split(",", 1)[-1]
                return f"![{title}](data:image/png;base64,{base64_data})"
            except Exception as e:
                logger.error(f"Failed to process data URL: {e}")
                return f"![{title}]({url})"
        return f"![{title}]({url})"
        
    try:
        async with get_client_session() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    content_type = response.headers.get('content-type', 'image/png')
                    base64_data = base64.b64encode(image_data).decode()
                    return f"![{title}](data:{content_type};base64,{base64_data})"
    except Exception as e:
        logger.error(f"Failed to convert image to base64: {e}")
    return f"![{title}]({url})"

def callout(text: str, icon: Optional[CalloutIcon] = None) -> str:
    """Format text as callout with optional icon."""
    if not text:
        return ""
        
    icon_str = ""
    if icon:
        if icon.get("type") == "emoji":
            icon_str = f"{icon.get('emoji', '')} "
        elif icon.get("type") in ["external", "file"]:
            external_data = icon.get("external") or {}
            file_data = icon.get("file") or {}
            url = external_data.get("url") or file_data.get("url", "")
            if url:
                icon_str = f"![icon]({url}) "
    
    # Handle heading matches within callouts
    heading_match = HEADING_PATTERN.match(text)
    if heading_match:
        heading_level = len(heading_match.group(1))
        heading_content = heading_match.group(2)
        return f"> {'#' * heading_level} {icon_str}{heading_content}"
    
    formatted_text = text.replace('\n', '\n> ')
    return f"> {icon_str}{formatted_text}"

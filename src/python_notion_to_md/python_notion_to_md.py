from typing import Dict, List, Optional, Any
import logging
from notion_client import Client

from .utils import md, notion, ConfigurationOptions, MdBlock, CustomTransformer, Annotations
from .utils.exceptions import UnhandledContentError, EmptyContentError, ValidationError, TableFormatError


class NotionToMarkdown:
    """Converts a Notion page to Markdown."""
    
    def __init__(self, notion_client: Client, config: Optional[ConfigurationOptions] = None):
        """Initialize NotionToMarkdown converter.
        
        Args:
            notion_client: Authenticated Notion client instance
            config: Optional configuration options
            
        Raises:
            ValueError: If notion_client is None
        """
        if not notion_client:
            raise ValueError("notion_client is required")
            
        self.notion_client = notion_client
        default_config = ConfigurationOptions(
            separate_child_page=False,
            convert_images_to_base64=False,
            parse_child_pages=True,
            api_retry_attempts=3,
            api_rate_limit_delay=0.5,
            max_concurrent_requests=5,
            debug_mode=False  # New config option for debug features
        )
        self.config = config or default_config
        self.custom_transformers: Dict[str, Optional[CustomTransformer]] = {}
        
        # Setup logging - only enable debug logging if explicitly requested
        self.logger = logging.getLogger("notion2md")
        self.logger.setLevel(logging.INFO if not self.config.get('debug_mode') else logging.DEBUG)
        
        # Only initialize stats if in debug mode
        self._stats = None
        if self.config.get('debug_mode'):
            self._init_stats()

    def _init_stats(self) -> None:
        """Initialize conversion statistics tracking."""
        self._stats = {
            'total_blocks': 0,
            'successful_blocks': 0,
            'errors': [],
            'unhandled_types': set(),
            'http_requests': {
                'total': 0,
                'by_type': {}  # Will store counts by endpoint type
            }
        }

    def _track_http_request(self, url: str) -> None:
        """Track HTTP request for statistics."""
        if not self._stats:
            return
            
        self._stats['http_requests']['total'] += 1
        
        # Categorize request
        if 'blocks' in url and 'children' in url:
            req_type = 'block_children'
        elif 'blocks' in url:
            req_type = 'block'
        elif 'pages' in url:
            req_type = 'page'
        else:
            req_type = 'other'
            
        self._stats['http_requests']['by_type'][req_type] = \
            self._stats['http_requests']['by_type'].get(req_type, 0) + 1

    def _validate_block(self, block: Dict, content: str, block_type: str) -> None:
        """Internal validation method - only runs basic validations by default."""
        if not isinstance(block, dict) or "type" not in block:
            raise ValueError("Invalid block structure")
            
        if not isinstance(block_type, str) or block_type not in self.VALID_BLOCK_TYPES:
            raise ValueError(f"Invalid block type: {block_type}")
            
        # Only run content validation in debug mode
        if self.config.get('debug_mode'):
            if not content and block_type not in ['divider', 'table_of_contents', 'breadcrumb']:
                self.logger.warning(f"Empty content in {block_type} block {block.get('id')}")

    VALID_BLOCK_TYPES = [
        'paragraph', 'heading_1', 'heading_2', 'heading_3',
        'bulleted_list_item', 'numbered_list_item', 'quote',
        'to_do', 'toggle', 'code', 'image', 'video', 'file',
        'pdf', 'bookmark', 'callout', 'synced_block', 'table',
        'column_list', 'column', 'link_preview', 'link_to_page',
        'equation', 'divider', 'table_of_contents', 'child_page',
        'child_database', 'breadcrumb', 'template', 'unsupported',
        'audio', 'embed'
    ]

    def annotate_plain_text(self, text: str, annotations: Annotations) -> str:
        """Apply text formatting annotations"""
        if not text:
            return ""
            
        # Handle special quotes and apostrophes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # For code blocks, preserve spaces and don't try to encode
        if annotations.get("code"):
            return md.inline_code(text)
            
        # For normal text, handle encoding
        try:
            text = text.encode('utf-8', errors='replace').decode('utf-8')
        except Exception as e:
            self.logger.warning(f"Failed to encode text: {str(e)}")
            text = text.encode('ascii', errors='replace').decode('ascii')
            
        # Preserve emojis by not applying formatting to single-character emoji-like text
        if len(text) == 1 or len(text.encode('utf-16-le')) // 2 == 1:
            return text
            
        if annotations.get("bold"):
            text = md.bold(text)
        if annotations.get("italic"):
            text = md.italic(text)
        if annotations.get("strikethrough"):
            text = md.strikethrough(text)
        if annotations.get("color") and annotations.get("color") != "default":
            text = md.color(text, annotations.get("color"))
        return text

    def validate_block_content(self, block: Dict, content: str, block_type: str) -> None:
        """Validate block content after conversion.
        
        Args:
            block: Original Notion block
            content: Converted markdown content
            block_type: Type of the block
            
        Raises:
            EmptyContentError: If content is empty when it shouldn't be
            ValidationError: If content fails validation rules
        """
        if not content or content.isspace():
            if block_type not in ['divider', 'table_of_contents', 'breadcrumb']:
                raise EmptyContentError(f"Empty {block_type} content", block)
                
        # Add specific validation rules for different block types
        if block_type == 'code':
            if not block.get('code', {}).get('rich_text'):
                raise ValidationError("Code block missing rich_text content", block)
                
        elif block_type == 'image':
            if not block.get('image'):
                raise ValidationError("Image block missing image data", block)

    async def block_to_markdown(self, block: Dict) -> str:
        """Convert a single block to markdown."""
        try:
            block_type = block.get("type", "")
            
            # Track unhandled types and raise error if not supported
            if block_type not in self.VALID_BLOCK_TYPES:
                if self._stats is not None:
                    self._stats['unhandled_types'].add(block_type)
                raise UnhandledContentError(
                    f"Block type '{block_type}' is not supported",
                    block=block
                )
            
            self._validate_block(block, "", block_type)
            
            if self._stats is not None:
                self._stats['total_blocks'] += 1
            
            # Handle custom transformers
            transformer = self.custom_transformers.get(block_type)
            if transformer is not None:
                result = transformer(block)
                if isinstance(result, str):
                    if self._stats is not None:
                        self._stats['successful_blocks'] += 1
                    return result
                return ""

            parsed_data = ""
            
            # Handle text-based blocks
            if block_type in [
                "paragraph", "heading_1", "heading_2", "heading_3",
                "bulleted_list_item", "numbered_list_item", "quote",
                "to_do", "callout"
            ]:
                block_content = block.get(block_type, {}).get("rich_text", [])
                for content in block_content:
                    if content["type"] == "equation":
                        parsed_data += md.inline_equation(content["equation"]["expression"])
                    else:
                        plain_text = content.get("plain_text", "")
                        annotations = content.get("annotations", {})
                        text = self.annotate_plain_text(plain_text, annotations)
                        
                        if content.get("href"):
                            text = md.link(text, content["href"])
                        
                        parsed_data += text

                # Apply heading formatting after collecting all text
                if block_type == "heading_1":
                    parsed_data = md.heading1(parsed_data)
                elif block_type == "heading_2":
                    parsed_data = md.heading2(parsed_data)
                elif block_type == "heading_3":
                    parsed_data = md.heading3(parsed_data)
                elif block_type == "bulleted_list_item":
                    parsed_data = md.bullet(parsed_data)
                elif block_type == "numbered_list_item":
                    number = block.get(block_type, {}).get("number", 1)
                    parsed_data = md.bullet(parsed_data, number)
                elif block_type == "to_do":
                    checked = block.get(block_type, {}).get("checked", False)
                    parsed_data = md.todo(parsed_data, checked)

            # Handle specific block types
            if block_type == "code":
                code_content = "".join(text["plain_text"] for text in block["code"].get("rich_text", []))
                parsed_data = md.code_block(code_content, block["code"].get("language", ""))
                
            elif block_type == "equation":
                parsed_data = md.equation(block["equation"]["expression"])
                
            elif block_type == "divider":
                parsed_data = md.divider()
                
            elif block_type == "image":
                try:
                    image_data = block.get("image", {})
                    caption = "".join(t["plain_text"] for t in image_data.get("caption", []))
                    
                    # Handle all possible image types
                    if image_data.get("type") == "file":
                        url = image_data.get("file", {}).get("url")
                    elif image_data.get("type") == "external":
                        url = image_data.get("external", {}).get("url")
                    else:
                        # Fallback for any other type
                        url = image_data.get("url")
                    
                    if not url:
                        self.logger.warning(f"No URL found for image block {block.get('id')}")
                        return ""
                        
                    parsed_data = await md.image(
                        caption or "image",
                        url,
                        self.config["convert_images_to_base64"]
                    )
                except Exception as e:
                    self.logger.error(f"Failed to process image block {block.get('id')}: {str(e)}")
                    if self._stats is not None:
                        self._stats['errors'].append({
                            'block_id': block.get('id'),
                            'block_type': 'image',
                            'error': str(e)
                        })
                    return ""

            elif block_type == "video":
                caption = "".join(t["plain_text"] for t in block["video"].get("caption", []))
                url = (
                    block["video"]["file"]["url"]
                    if block["video"]["type"] == "file"
                    else block["video"]["external"]["url"]
                )
                parsed_data = md.link(caption or "Video", url)

            elif block_type == "file":
                caption = "".join(t["plain_text"] for t in block["file"].get("caption", []))
                url = (
                    block["file"]["file"]["url"]
                    if block["file"]["type"] == "file"
                    else block["file"]["external"]["url"]
                )
                parsed_data = md.link(caption or "File", url)

            elif block_type == "pdf":
                caption = "".join(t["plain_text"] for t in block["pdf"].get("caption", []))
                url = (
                    block["pdf"]["file"]["url"]
                    if block["pdf"]["type"] == "file"
                    else block["pdf"]["external"]["url"]
                )
                parsed_data = md.link(caption or "PDF", url)

            elif block_type == "bookmark":
                url = block["bookmark"]["url"]
                caption = "".join(t["plain_text"] for t in block["bookmark"].get("caption", []))
                parsed_data = md.link(caption or url, url)

            elif block_type == "embed":
                url = block["embed"]["url"]
                caption = "".join(t["plain_text"] for t in block["embed"].get("caption", []))
                parsed_data = f"<iframe src=\"{url}\" title=\"{caption or 'Embedded content'}\"></iframe>"

            elif block_type == "link_preview":
                url = block["link_preview"]["url"]
                parsed_data = md.link(url, url)  # Use URL as both text and link

            elif block_type == "table":
                parsed_data = await self.handle_table_block(block)
                
            elif block_type == "toggle":
                # Get toggle text
                toggle_text = "".join(
                    text.get("plain_text", "") 
                    for text in block.get("toggle", {}).get("rich_text", [])
                )
                
                # Get children content if any
                children_content = ""
                if block.get("has_children"):
                    child_blocks = await notion.get_block_children(self.notion_client, block["id"])
                    child_md_blocks = await self.blocks_to_markdown(child_blocks)
                    child_md = await self.to_markdown_string(child_md_blocks)
                    children_content = child_md.get("parent", "")
                
                parsed_data = f"""<details>
<summary>{toggle_text or "Toggle"}</summary>

{children_content}
</details>"""

            elif block_type == "column_list":
                # Handle columns as a container
                columns = []
                for child in block.get("children", []):
                    if child["type"] == "column":
                        column_content = []
                        for block in child.get("children", []):
                            content = await self.block_to_markdown(block)
                            if content:
                                column_content.append(content)
                        columns.append("\n".join(column_content))
                
                # Join columns with dividers
                parsed_data = " | ".join(columns)

            elif block_type == "audio":
                caption = "".join(t["plain_text"] for t in block["audio"].get("caption", []))
                url = (
                    block["audio"]["file"]["url"]
                    if block["audio"]["type"] == "file"
                    else block["audio"]["external"]["url"]
                )
                parsed_data = md.link(caption or "Audio", url)

            elif block_type == "link_to_page":
                page_id = block["link_to_page"].get("page_id")
                database_id = block["link_to_page"].get("database_id")
                target_id = page_id or database_id
                
                if target_id:
                    try:
                        target = await self.notion_client.pages.retrieve(page_id=target_id)
                        title = target.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Linked page')
                        parsed_data = md.link(title, target.get('url', f'notion://page/{target_id}'))
                    except Exception as e:
                        if self.config.get('debug_mode'):
                            self.logger.warning(f"Failed to resolve link_to_page: {str(e)}")
                        parsed_data = md.link("Linked page", f"notion://page/{target_id}")
                else:
                    parsed_data = "Invalid page link"

            elif block_type == "synced_block":
                # TODO: Improve synced block handling
                # Current limitations:
                # - Recursive synced blocks not fully supported
                # - Permission handling needs verification
                # - Infinite loop prevention needed
                self.logger.warning(f"Synced block {block.get('id')} skipped - limited support")
                return "Content from synced block (limited support)"

            # Handle specific block types that we haven't implemented yet
            elif block_type in ["child_database", "synced_block"]:
                raise UnhandledContentError(
                    f"Block type '{block_type}' is not fully implemented yet",
                    block=block
                )

            if self._stats is not None:
                self._stats['successful_blocks'] += 1
            return parsed_data
            
        except UnhandledContentError:
            # Re-raise UnhandledContentError to notify users
            raise
        except Exception as e:
            if self.config.get('debug_mode'):
                self.logger.error(
                    f"Error processing {block.get('type', 'unknown')} block: {str(e)}",
                    exc_info=True
                )
                if self._stats is not None:
                    self._stats['errors'].append({
                        'block_id': block.get('id'),
                        'block_type': block.get('type'),
                        'error': str(e)
                    })
            raise

    async def handle_synced_block(self, block: Dict, depth: int = 0) -> str:
        """Process synced_block by resolving original content"""
        if depth > 3:  # Prevent infinite recursion
            self.logger.warning("Synced block recursion depth exceeded")
            return ""
            
        synced_block = block.get("synced_block", {})
        synced_from = synced_block.get("synced_from")

        if not synced_from:
            # e.g. log warning or return early
            self.logger.warning("Synced block has no source")
            return ""

        # Ensure it's a dict:
        if not isinstance(synced_from, dict):
            self.logger.warning("synced_from is not a dict")
            return ""

        # Now safely access block_id
        block_id = synced_from.get("block_id")
        if not isinstance(block_id, str):
            # either block_id is None or not a string
            self.logger.warning("Synced block has no valid 'block_id'")
            return ""

        # At this point, block_id is definitely a string,
        # so Pylance won't complain about the 'Unknown | None' type
        original_blocks = await notion.get_block_children(self.notion_client, block_id)
        md_dict = await self.to_markdown_string(original_blocks, nesting_level=depth+1)
        return md_dict.get("parent", "")

    def handle_child_database(self, block: Dict) -> str:
        """Convert child database to markdown table structure"""
        title = block["child_database"].get("title", "Untitled Database")
        return md.heading2(title) + "\n" + md.table([
            ["Property", "Type", "Content"],  # Example headers
            ["Status", "Select", "Not started"]  # Mock data
        ])

    def set_custom_transformer(self, block_type: str, transformer: CustomTransformer) -> "NotionToMarkdown":
        self.custom_transformers[block_type] = transformer
        return self

    def handle_media_block(self, block: Dict, media_type: str) -> str:
        """Handle audio/video/pdf blocks with consistent formatting"""
        media_data = block[media_type]
        caption = "".join(t["plain_text"] for t in media_data.get("caption", []))
        
        # Handle URL resolution
        url = (
            media_data.get("url") or 
            media_data.get("external", {}).get("url") or
            media_data.get("file", {}).get("url", "#")
        )
        
        return f"\n{md.link(f'{media_type.upper()}: {caption or 'media'}', url)}\n"

    async def to_markdown_string(self, md_blocks: List[MdBlock], page_identifier: str = "parent", nesting_level: int = 0) -> Dict[str, str]:
        """Convert markdown blocks to string output."""
        md_output: Dict[str, str] = {}
        
        for block in md_blocks:
            # Process parent blocks
            if block.get("parent"):
                if block["type"] not in ["toggle", "child_page", "to_do", "bulleted_list_item", "numbered_list_item", "quote"]:
                    # Add single newline before block
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    md_output[page_identifier] += f"\n{md.add_tab_space(block['parent'], nesting_level)}"
                else:
                    # Handle list items with proper indentation
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    indentation = "  " * nesting_level if block["type"] in ["bulleted_list_item", "numbered_list_item", "to_do"] else ""
                    md_output[page_identifier] += f"{indentation}{block['parent']}\n"
            
            # Process child blocks
            if block.get("children"):
                if block["type"] in ["bulleted_list_item", "numbered_list_item", "to_do"]:
                    # Process nested list items with increased indentation
                    md_str = await self.to_markdown_string(block["children"], page_identifier, nesting_level + 1)
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    if page_identifier in md_str:
                        md_output[page_identifier] += md_str[page_identifier]
                elif block["type"] in ["synced_block", "column_list", "column"]:
                    md_str = await self.to_markdown_string(block["children"], page_identifier)
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    
                    for key, value in md_str.items():
                        md_output[key] = md_output.get(key, "") + value
                elif block["type"] == "child_page":
                    child_page_title = block["parent"]
                    md_str = await self.to_markdown_string(block["children"], child_page_title)
                    
                    if self.config["separate_child_page"]:
                        md_output.update(md_str)
                    else:
                        md_output[page_identifier] = md_output.get(page_identifier, "")
                        if child_page_title in md_str:
                            md_output[page_identifier] += f"\n{child_page_title}\n{md_str[child_page_title]}"
                            
                elif block["type"] == "toggle":
                    toggle_children_md = await self.to_markdown_string(block["children"])
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    md_output[page_identifier] += md.toggle(block["parent"], toggle_children_md.get("parent", ""))
                    
                elif block["type"] == "quote":
                    md_str = await self.to_markdown_string(block["children"], page_identifier, nesting_level)
                    formatted_content = "\n".join(
                        f"> {line}" if line.strip() else ">" 
                        for line in md_str.get("parent", "").split("\n")
                    ).strip()
                    
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    if page_identifier != "parent" and "parent" in md_str:
                        md_output[page_identifier] += formatted_content
                    elif page_identifier in md_str:
                        md_output[page_identifier] += formatted_content
                    md_output[page_identifier] += "\n"
                    
                elif block["type"] != "callout":  # Callout is already processed
                    md_str = await self.to_markdown_string(block["children"], page_identifier, nesting_level + 1)
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    
                    if page_identifier != "parent" and "parent" in md_str:
                        md_output[page_identifier] += md_str["parent"]
                    elif page_identifier in md_str:
                        md_output[page_identifier] += md_str[page_identifier]
        
        # Clean up multiple newlines
        for key in md_output:
            md_output[key] = "\n".join(line for line in md_output[key].splitlines() if line.strip() or line == "")
        
        return md_output

    async def blocks_to_markdown(
        self,
        blocks: Optional[List[Dict[str, Any]]] = None, 
        total_pages: Optional[int] = None,
        md_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Convert Notion blocks to markdown blocks.
        
        Args:
            blocks: List of Notion blocks
            total_pages: Number of pages to fetch (100 blocks per page)
            md_blocks: Accumulator for markdown blocks
            
        Returns:
            List of markdown blocks
        """
        if not blocks:
            return md_blocks or []
            
        md_blocks = md_blocks or []
        
        # Update numbered list indices before processing
        notion.update_numbered_list_indices(blocks)
        
        for block in blocks:
            if (block["type"] == "unsupported" or 
                (block["type"] == "child_page" and not self.config["parse_child_pages"])):
                continue
                
            if block.get("has_children"):
                if block["type"] == "synced_block":
                    synced_block_data = block.get("synced_block")
                    if isinstance(synced_block_data, dict):
                        synced_from_data = synced_block_data.get("synced_from")
                        if isinstance(synced_from_data, dict):
                            possible_id = synced_from_data.get("block_id")
                            if isinstance(possible_id, str):
                                block_id = possible_id
                            else:
                                block_id = block["id"]
                        else:
                            block_id = block["id"]
                    else:
                        block_id = block["id"]
                else:
                    block_id = block["id"]
                          
                child_blocks = await notion.get_block_children(
                    self.notion_client,
                    block_id,
                    total_pages
                )
                
                md_blocks.append({
                    "type": block["type"],
                    "block_id": block["id"],
                    "parent": await self.block_to_markdown(block),
                    "children": []
                })
                
                # Process children if no custom transformer
                if not (block["type"] in self.custom_transformers):
                    await self.blocks_to_markdown(
                        child_blocks,
                        total_pages,
                        md_blocks[-1]["children"]
                    )
                    
                continue
                
            md_blocks.append({
                "type": block["type"],
                "block_id": block["id"],
                "parent": await self.block_to_markdown(block),
                "children": []
            })
            
        return md_blocks

    def generate_conversion_report(self) -> str:
        """Generate a summary report of the conversion process."""
        if not self._stats:
            return "No statistics available (debug mode disabled)"
            
        success_rate = (
            (self._stats['successful_blocks'] / self._stats['total_blocks'] * 100)
            if self._stats['total_blocks'] > 0 else 0
        )
        
        # Create main report sections
        report = [
            "Conversion Report",
            "================",
            f"Blocks: {self._stats['successful_blocks']}/{self._stats['total_blocks']} ({success_rate:.1f}% success)",
        ]
        
        # Add unhandled types section if any exist
        if self._stats['unhandled_types']:
            report.append(f"\nUnhandled Types ({len(self._stats['unhandled_types'])}):")
            for block_type in sorted(self._stats['unhandled_types']):
                report.append(f"  - {block_type}")
        
        # Add error summary if any exist
        if self._stats['errors']:
            report.extend([
                f"\nErrors ({len(self._stats['errors'])}):",
                "  Most common issues:"
            ])
            error_counts = {}
            for error in self._stats['errors']:
                error_type = error['block_type'] or 'unknown'
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            for block_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                report.append(f"  - {block_type}: {count} errors")
        
        # Add API request summary
        if self._stats['http_requests']['total'] > 0:
            report.extend([
                f"\nAPI Requests: {self._stats['http_requests']['total']} total",
                "  Breakdown:"
            ])
            for req_type, count in sorted(self._stats['http_requests']['by_type'].items(), key=lambda x: x[1], reverse=True):
                report.append(f"  - {req_type}: {count}")
        
        return "\n".join(report)

    async def page_to_markdown(self, page_id: str, total_pages: Optional[int] = None) -> List[MdBlock]:
        """Convert a Notion page to markdown."""
        if not self.notion_client:
            raise ValueError("notion_client is required")
        
        try:
            # Reset stats for new conversion
            if self.config.get('debug_mode'):
                self._init_stats()
            
            # Get page metadata with error handling
            try:
                self._track_http_request(f"pages/{page_id}")
                page = await self.notion_client.pages.retrieve(page_id=page_id)
                title = page.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', '').strip()
                
                # Skip if no title
                if not title:
                    self.logger.warning(f"⚠ Skipped empty page (no title): {page_id}")
                    return []
                
                # Get page blocks first to check for content
                blocks = await notion.get_block_children(self.notion_client, page_id, total_pages)
                
                # Skip if no meaningful content
                if not blocks:
                    self.logger.warning(f"⚠ Skipped empty page (no content): {page_id} - {title}")
                    return []
                
                # Create title block
                title_block = {
                    "type": "heading_1",
                    "block_id": "title",
                    "parent": md.heading1(title),
                    "children": []
                }
                
                # Convert blocks to markdown
                result = await self.blocks_to_markdown(blocks)
                
                # Skip if blocks converted to empty content
                if not result:
                    self.logger.warning(f"⚠ Skipped empty page (no meaningful content): {page_id} - {title}")
                    return []
                
                # Insert title block at the beginning
                result.insert(0, title_block)
                
                # Log conversion report
                if self.config.get('debug_mode'):
                    self.logger.info("\n" + self.generate_conversion_report())
                
                return result
                
            except Exception as e:
                self.logger.error(f"Failed to retrieve page metadata: {str(e)}")
                return []
            
        except Exception as e:
            self.logger.error(f"Failed to convert page {page_id}: {str(e)}", exc_info=True)
            raise

    def get_debug_info(self) -> Optional[Dict]:
        """Get debug information if debug mode is enabled.
        
        Returns:
            Dict with debug information if debug_mode is True, None otherwise
        """
        if not self.config.get('debug_mode') or self._stats is None:
            return None
            
        success_rate = (
            (self._stats['successful_blocks'] / self._stats['total_blocks'] * 100)
            if self._stats['total_blocks'] > 0 else 0
        )
        
        return {
            'total_blocks': self._stats['total_blocks'],
            'successful_blocks': self._stats['successful_blocks'],
            'success_rate': f"{success_rate:.1f}%",
            'errors': self._stats['errors'],
            'unhandled_types': list(self._stats['unhandled_types']),
            'http_requests': self._stats['http_requests']
        }

    def format_cell_text(self, rich_texts: List[Dict]) -> str:
        """Format cell text with proper annotations."""
        formatted = []
        for rt in rich_texts:
            text = rt.get("plain_text", "")
            annotations = rt.get("annotations", {})
            formatted.append(self.annotate_plain_text(text, annotations))
        return " ".join(formatted)

    def validate_table(self, rows: List[List[str]]) -> None:
        """Validate table structure for consistency."""
        if not rows:
            raise TableFormatError("Empty table", None)
            
        col_counts = {len(row) for row in rows}
        if len(col_counts) > 1:
            raise TableFormatError(f"Inconsistent column counts: {col_counts}", None)

    async def handle_table_block(self, block: Dict) -> str:
        """Convert a table block to markdown."""
        try:
            table_data = block.get("table", {})
            rows = []
            
            # Process each row
            for row in table_data.get("rows", []):
                cells = []
                for cell in row.get("cells", []):
                    cell_text = self.format_cell_text(cell)
                    cells.append(cell_text.strip() or " ")  # Ensure empty cells are preserved
                rows.append(cells)
            
            # Validate table structure
            self.validate_table(rows)
            
            if not rows:
                return ""
                
            # Create markdown table
            header = "| " + " | ".join(rows[0]) + " |"
            separator = "| " + " | ".join(["---"] * len(rows[0])) + " |"
            body = "\n".join(f"| {' | '.join(row)} |" for row in rows[1:])
            
            return f"{header}\n{separator}\n{body}"
            
        except Exception as e:
            self.logger.error(f"Failed to process table: {str(e)}")
            if self._stats is not None:
                self._stats['errors'].append({
                    'block_id': block.get('id'),
                    'block_type': 'table',
                    'error': str(e)
                })
            return "<!-- Table processing failed -->"

    async def handle_toggle_block(self, block: Dict, children_content: str = "") -> str:
        """Convert a toggle block to markdown."""
        try:
            content = "".join(text.get("plain_text", "") for text in block["toggle"].get("rich_text", []))
            if not content.strip():
                content = "Toggle"  # Default text for empty toggles
                
            # Format the toggle with HTML details tag
            return f"""<details>
<summary>{content}</summary>

{children_content}
</details>"""
            
        except Exception as e:
            self.logger.error(f"Failed to process toggle: {str(e)}")
            return f"<!-- Toggle processing failed: {str(e)} -->"

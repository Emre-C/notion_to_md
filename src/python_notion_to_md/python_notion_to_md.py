from typing import Dict, List, Optional, Any
import logging
from notion_client import Client

from .utils import md, notion, ConfigurationOptions, MdBlock, CustomTransformer, Annotations
from .utils.exceptions import NotionParseError, UnhandledContentError, EmptyContentError, ValidationError


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
            'unhandled_types': set()
        }

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
        if annotations["bold"]:
            text = md.bold(text)
        if annotations["italic"]:
            text = md.italic(text)
        if annotations["strikethrough"]:
            text = md.strikethrough(text)
        if annotations["code"]:
            text = md.inline_code(text)
        if annotations["color"] and annotations["color"] != "default":
            text = md.color(text, annotations["color"])
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
                "to_do", "toggle", "callout"
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

            # Handle specific block types
            if block_type == "code":
                code_content = "".join(text["plain_text"] for text in block["code"].get("rich_text", []))
                parsed_data = md.code_block(code_content, block["code"].get("language", ""))
                
            elif block_type == "equation":
                parsed_data = md.equation(block["equation"]["expression"])
                
            elif block_type == "divider":
                parsed_data = md.divider()
                
            elif block_type == "image":
                caption = "".join(t["plain_text"] for t in block["image"].get("caption", []))
                url = (
                    block["image"]["file"]["url"]
                    if block["image"]["type"] == "file"
                    else block["image"]["external"]["url"]
                )
                parsed_data = await md.image(
                    caption or "image",
                    url,
                    self.config["convert_images_to_base64"]
                )

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
                rows = []
                for row in block.get("table", {}).get("rows", []):
                    cells = []
                    for cell in row.get("cells", []):
                        cell_text = "".join(t["plain_text"] for t in cell)
                        cells.append(cell_text)
                    rows.append(cells)
                parsed_data = md.table(rows)

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

            if self._stats is not None:
                self._stats['successful_blocks'] += 1
            return parsed_data
            
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
        """Convert markdown blocks to string output.
        
        Args:
            md_blocks: List of markdown blocks
            page_identifier: Identifier for the page (default: "parent")
            nesting_level: Current nesting level for indentation
            
        Returns:
            Dict mapping page identifiers to markdown strings
        """
        md_output: Dict[str, str] = {}
        
        for block in md_blocks:
            # Process parent blocks
            if block.get("parent") and block["type"] not in ["toggle", "child_page"]:
                if block["type"] not in ["to_do", "bulleted_list_item", "numbered_list_item", "quote"]:
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    md_output[page_identifier] += f"\n{md.add_tab_space(block['parent'], nesting_level)}\n\n"
                else:
                    md_output[page_identifier] = md_output.get(page_identifier, "")
                    md_output[page_identifier] += f"{md.add_tab_space(block['parent'], nesting_level)}\n"
            
            # Process child blocks
            if block.get("children"):
                if block["type"] in ["synced_block", "column_list", "column"]:
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
        """Generate a summary report of the conversion process.
        
        Returns:
            A formatted string containing conversion statistics and errors
        """
        success_rate = (
            (self._stats['successful_blocks'] / self._stats['total_blocks'] * 100)
            if self._stats['total_blocks'] > 0 else 0
        )
        
        report = [
            "Conversion Report",
            "================",
            f"Total blocks processed: {self._stats['total_blocks']}",
            f"Successfully converted: {self._stats['successful_blocks']} ({success_rate:.1f}%)",
            f"Errors encountered: {len(self._stats['errors'])}",
            f"Unhandled block types: {', '.join(self._stats['unhandled_types']) or 'None'}"
        ]
        
        if self._stats['errors']:
            report.extend([
                "\nDetailed Errors",
                "---------------"
            ])
            for error in self._stats['errors']:
                report.append(
                    f"Block {error['block_id']} ({error['block_type']}): "
                    f"{error['error']}"
                )
        
        return "\n".join(report)

    async def page_to_markdown(self, page_id: str, total_pages: Optional[int] = None) -> List[MdBlock]:
        """Convert a Notion page to markdown.
        
        Args:
            page_id: ID of the Notion page
            total_pages: Number of pages to fetch (100 blocks per page)
            
        Returns:
            List of markdown blocks
            
        Raises:
            ValueError: If notion_client is not set
            NotionParseError: If parsing fails
        """
        if not self.notion_client:
            raise ValueError("notion_client is required")
        
        try:
            # Reset stats for new conversion
            self._stats = {
                'total_blocks': 0,
                'successful_blocks': 0,
                'errors': [],
                'unhandled_types': set()
            }
            
            blocks = await notion.get_block_children(self.notion_client, page_id, total_pages)
            result = await self.blocks_to_markdown(blocks)
            
            # Log conversion report
            self.logger.info("\n" + self.generate_conversion_report())
            
            return result
            
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
            'unhandled_types': list(self._stats['unhandled_types'])
        }

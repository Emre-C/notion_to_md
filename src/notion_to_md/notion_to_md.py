from typing import Dict, List, Optional, Any
import logging
from notion_client import Client

from .utils import md, notion, ConfigurationOptions, MdBlock, CustomTransformer, Annotations


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
            max_concurrent_requests=5
        )
        self.config = config or default_config
        self.custom_transformers: Dict[str, Optional[CustomTransformer]] = {}
        
        # Setup logging
        self.logger = logging.getLogger("notion2md")
        self.logger.setLevel(logging.INFO)

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
        return text

    async def block_to_markdown(self, block: Dict) -> str:
        """Convert a single block to markdown."""
        if not isinstance(block, dict) or "type" not in block:
            return ""
            
        block_type = block.get("type")
        if not isinstance(block_type, str):
            return ""
        if block_type not in self.VALID_BLOCK_TYPES:
            raise ValueError(f"Invalid block type: {block_type}")
            
        transformer = self.custom_transformers.get(block_type)
        if transformer is not None:
            result = transformer(block)
            if isinstance(result, str):
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
            parsed_data = md.code_block(parsed_data, block["code"].get("language", ""))
            
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
            
        elif block_type == "table":
            table_rows = []
            for row in block.get("table", {}).get("rows", []):
                cells = []
                for cell in row.get("cells", []):
                    cell_text = "".join(t["plain_text"] for t in cell)
                    cells.append(cell_text)
                table_rows.append(cells)
            parsed_data = md.table(table_rows)
            
        elif block_type == "child_page":
            if self.config["parse_child_pages"]:
                title = block["child_page"].get("title", "")
                parsed_data = md.heading2(title) if not self.config["separate_child_page"] else title
                
        elif block_type == "synced_block":
            parsed_data = await self.handle_synced_block(block)
            
        elif block_type == "child_database":
            if not self.config["parse_child_pages"]:
                return ""
            title = block["child_database"].get("title", "Child Database")
            return md.heading3(title)
            
        elif block_type == "table_of_contents":
            return md.divider()
            
        elif block_type == "audio":
            audio_block = block["audio"]
            caption = "".join([t["plain_text"] for t in audio_block.get("caption", [])])
            url = audio_block.get("file", {}).get("url", "")
            return md.link(caption or "audio", url)
            
        elif block_type == "embed":
            embed_block = block["embed"]
            caption = "".join([t["plain_text"] for t in embed_block.get("caption", [])])
            url = embed_block.get("url", "")
            return md.link(caption or "embed", url)
            
        elif block_type == "link_preview":
            preview_block = block["link_preview"]
            url = preview_block.get("url", "")
            return md.link("link_preview", url)
            
        elif block_type == "breadcrumb":
            return md.divider()  # Simple representation for breadcrumb

        return parsed_data

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

    async def page_to_markdown(self, page_id: str, total_pages: Optional[int] = None) -> List[MdBlock]:
        """Convert a Notion page to markdown.
        
        Args:
            page_id: ID of the Notion page
            total_pages: Number of pages to fetch (100 blocks per page)
            
        Returns:
            List of markdown blocks
        """
        if not self.notion_client:
            raise ValueError("notion_client is required")
            
        blocks = await notion.get_block_children(self.notion_client, page_id, total_pages)
        return await self.blocks_to_markdown(blocks)

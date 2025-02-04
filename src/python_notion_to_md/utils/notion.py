from typing import List, Dict, Optional
import logging
from notion_client import Client
from .types import ListBlockChildrenResponseResults

logger = logging.getLogger(__name__)

async def get_block_children(
    notion_client: Client,
    block_id: str, 
    total_pages: Optional[int] = None
) -> List[Dict]:
    """Get all children blocks of a block."""
    blocks = []
    cursor = None
    
    while True:
        response = await notion_client.blocks.children.list(
            block_id=block_id,
            start_cursor=cursor,
            page_size=100
        )
        
        blocks.extend(response.get("results", []))
        
        if not response.get("has_more", False) or (total_pages and len(blocks) >= total_pages * 100):
            break
            
        cursor = response.get("next_cursor")
    
    return blocks

def update_numbered_list_indices(blocks: ListBlockChildrenResponseResults) -> None:
    """Update sequential indices for numbered list items."""
    numbered_list_index = 0
    
    for block in blocks:
        if block.get("type") == "numbered_list_item":
            numbered_list_index += 1
            block["numbered_list_item"] = block.get("numbered_list_item", {})
            block["numbered_list_item"]["number"] = numbered_list_index
        else:
            numbered_list_index = 0

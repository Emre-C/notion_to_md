from typing import List, Dict, Optional, Any
import logging
from notion_client import Client
from notion_client.errors import APIResponseError
from utils.types import ListBlockChildrenResponseResults
from tenacity import retry, wait_exponential, stop_after_attempt

# Configure logging
logger = logging.getLogger(__name__)

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3)
)
async def get_block_children(
    notion_client: Client,
    block_id: str, 
    total_page: Optional[int] = None
) -> ListBlockChildrenResponseResults:
    """Fetch all child blocks for a given block ID with pagination support.
    
    Args:
        notion_client: Authenticated Notion client
        block_id: ID of the block to fetch children for
        total_page: Maximum number of pages to fetch (100 blocks per page)
        
    Returns:
        List of child blocks
        
    Raises:
        APIResponseError: If API request fails after retries
        ValueError: If block_id is invalid
    """
    if not block_id or not isinstance(block_id, str):
        raise ValueError("block_id must be a non-empty string")

    result: ListBlockChildrenResponseResults = []
    page_count = 0
    start_cursor = None

    try:
        while True:
            response = await notion_client.blocks.children.list(
                start_cursor=start_cursor,
                block_id=block_id,
                page_size=100
            )
            
            if not isinstance(response, dict) or "results" not in response:
                logger.error(f"Unexpected API response structure for block {block_id}")
                raise APIResponseError("Invalid API response structure")
                
            result.extend(response["results"])
            logger.debug(f"Fetched {len(response['results'])} blocks for block {block_id}")
            
            start_cursor = response.get("next_cursor")
            page_count += 1
            
            if not start_cursor or (total_page is not None and page_count >= total_page):
                break

    except APIResponseError as e:
        logger.error(f"Failed to fetch blocks for {block_id}: {str(e)}")
        raise

    update_numbered_list_indices(result)
    return result

def update_numbered_list_indices(blocks: ListBlockChildrenResponseResults) -> None:
    """Update sequential indices for numbered list items.
    
    Args:
        blocks: List of blocks to process
        
    Note:
        Modifies blocks in place, adding numbers to numbered_list_item blocks
    """
    numbered_list_index = 0
    
    for block in blocks:
        if not isinstance(block, dict):
            logger.warning(f"Skipping invalid block: {block}")
            continue
            
        if block.get("type") == "numbered_list_item":
            numbered_list_index += 1
            block["numbered_list_item"] = block.get("numbered_list_item", {})
            block["numbered_list_item"]["number"] = numbered_list_index
        else:
            numbered_list_index = 0

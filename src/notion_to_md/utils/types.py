from typing import TypedDict, List, Dict, Optional, Union, Literal, Any, Callable

class ConfigurationOptions(TypedDict):
    separate_child_page: bool
    convert_images_to_base64: bool
    parse_child_pages: bool
    api_retry_attempts: int
    api_rate_limit_delay: float
    max_concurrent_requests: int

CustomTransformer = Callable[[Dict[str, Any]], Optional[Union[str, bool]]]

class SyncedBlock(TypedDict):
    synced_from: Optional[Dict[str, str]]
    
class ChildDatabase(TypedDict):
    title: str

# class MdBlock(TypedDict):
#     type: str
#     block_id: str
#     parent: str
#     children: List['MdBlock']

MdBlock = Dict[str, Any]

class Annotations(TypedDict):
    bold: bool
    italic: bool
    strikethrough: bool
    underline: bool
    code: bool
    color: str

class Text(TypedDict):
    type: Literal["text"]
    text: Dict[str, Union[str, Dict[str, str]]]
    annotations: Annotations
    plain_text: str
    href: Optional[str]

class Equation(TypedDict):
    type: Literal["equation"]
    equation: Dict[str, str]
    annotations: Annotations
    plain_text: str
    href: None

class CalloutIcon(TypedDict, total=False):
    type: Literal["emoji", "external", "file"]
    emoji: Optional[str]
    external: Optional[Dict[str, str]]
    file: Optional[Dict[str, str]]

BlockType = Literal[
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item", "quote",
    "to_do", "toggle", "code", "image", "video", "file",
    "pdf", "bookmark", "callout", "synced_block", "table",
    "column_list", "column", "link_preview", "link_to_page",
    "equation", "divider", "table_of_contents", "child_page",
    "child_database", "breadcrumb", "template", "unsupported"
]

# These TypedDicts remain here for possible future usage
class ListBlockChildrenResponseResult(TypedDict, total=False):
    synced_block: Dict[str, Any]
    child_database: Dict[str, Any]
    audio: Dict[str, Any]
    video: Dict[str, Any]
    pdf: Dict[str, Any]
    
ListBlockChildrenResponseResults = List[MdBlock]

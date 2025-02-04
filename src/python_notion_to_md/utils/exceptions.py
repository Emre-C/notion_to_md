"""
Exception hierarchy for the Notion to Markdown converter.

Base Exception:
- NotionParseError: Base class for all exceptions in this module

Specific Exceptions:
- UnhandledContentError: Raised when encountering a block type that is not supported
- EmptyContentError: Raised when a page or block has no content to convert
- ValidationError: Raised when input data fails validation
- TableFormatError: Raised when table data cannot be properly formatted
"""

class NotionParseError(Exception):
    """Base exception class for all Notion to Markdown conversion errors."""
    pass

class UnhandledContentError(NotionParseError):
    """Raised when encountering a block type that is not supported.
    
    Attributes:
        block_type (str): The type of block that could not be handled
        block_data (dict): The raw block data for debugging
    """
    def __init__(self, block_type: str, block_data: dict = None):
        self.block_type = block_type
        self.block_data = block_data
        super().__init__(f"Unhandled block type: {block_type}")

class EmptyContentError(NotionParseError):
    """Raised when a page or block has no content to convert.
    
    Attributes:
        page_id (str): ID of the empty page
        message (str): Description of why the content is considered empty
    """
    def __init__(self, page_id: str, message: str):
        self.page_id = page_id
        super().__init__(f"Empty content for page {page_id}: {message}")

class ValidationError(NotionParseError):
    """Raised when input data fails validation.
    
    Attributes:
        field (str): The field that failed validation
        message (str): Description of the validation error
    """
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error in {field}: {message}")

class TableFormatError(NotionParseError):
    """Raised when table data cannot be properly formatted.
    
    Attributes:
        message (str): Description of the formatting error
        table_data (dict): The raw table data for debugging
    """
    def __init__(self, message: str, table_data: dict = None):
        self.table_data = table_data
        super().__init__(f"Table formatting error: {message}")

class UnsupportedFeatureError(NotionParseError):
    """Raised when a feature is not fully supported or has known limitations."""
    def __init__(self, message: str, block=None, feature_name: str = None, limitation_details: str = None):
        super().__init__(message, block)
        self.feature_name = feature_name
        self.limitation_details = limitation_details 
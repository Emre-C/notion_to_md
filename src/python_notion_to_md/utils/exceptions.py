"""Custom exceptions for notion-to-md conversion."""

class NotionParseError(Exception):
    """Base exception for all parsing errors."""
    def __init__(self, message: str, block=None):
        super().__init__(message)
        self.block_id = block.get('id') if block else None
        self.block_type = block.get('type') if block else None
        self.raw_data = block

class UnhandledContentError(NotionParseError):
    """Raised when content type isn't properly handled."""
    pass

class EmptyContentError(NotionParseError):
    """Raised when expected content is empty or invalid."""
    pass

class ValidationError(NotionParseError):
    """Raised when content fails validation checks."""
    pass

class UnsupportedFeatureError(NotionParseError):
    """Raised when a feature is not fully supported or has known limitations."""
    def __init__(self, message: str, block=None, feature_name: str = None, limitation_details: str = None):
        super().__init__(message, block)
        self.feature_name = feature_name
        self.limitation_details = limitation_details 
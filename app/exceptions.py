class UnsupportedFormatError(Exception):
    """Raised when an uploaded file is not a supported format or exceeds size limits."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ExtractionError(Exception):
    """Raised when the LLM extraction fails to produce a valid result."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class DocumentProcessingError(Exception):
    """Raised when an upstream LLM service call fails (network, auth, rate limit)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

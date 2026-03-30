# Document Handling & Validation

> **Status: COMPLETE** ✅

## Overview

Implement secure file validation and conversion before any LLM call is made. This layer is the first line of defense: it rejects unsupported file types, enforces size limits, and converts raw upload bytes into the typed inputs BAML requires. Validating on magic bytes (not filename extension) prevents trivially bypassing the check by renaming a `.txt` to `.pdf`.

## Requirements

- Create `app/services/document.py` with the following responsibilities:
  - Define `SUPPORTED_MIME_TYPES: dict[str, str]` mapping magic-byte signatures to MIME type strings
  - Supported formats: `application/pdf`, `image/png`, `image/jpeg`, `image/webp`, `image/tiff`
  - `detect_mime_type(content: bytes) -> str | None` — inspect the first 16 bytes for known magic byte signatures; return the MIME type string or `None` if unrecognized
  - `validate_and_convert(content: bytes, filename: str) -> tuple[str, "Image | Pdf"]` — detect MIME type, raise `UnsupportedFormatError` if not supported or file exceeds configured size limit, return `(mime_type, baml_input)` tuple
  - Size check must use `settings.max_file_size_mb` from `app/config.py`; raise `UnsupportedFormatError` with a message stating the limit
- Magic byte signatures to detect:
  | Format | Offset | Bytes (hex) |
  |---|---|---|
  | PDF | 0 | `25 50 44 46` (`%PDF`) |
  | PNG | 0 | `89 50 4E 47 0D 0A 1A 0A` |
  | JPEG | 0 | `FF D8 FF` |
  | WEBP | 0+8 | bytes 0–3 = `52 49 46 46` (`RIFF`), bytes 8–11 = `57 45 42 50` (`WEBP`) |
  | TIFF LE | 0 | `49 49 2A 00` |
  | TIFF BE | 0 | `4D 4D 00 2A` |
- `UnsupportedFormatError` (defined in `app/exceptions.py`) must carry a `detail: str` message that describes what was wrong — e.g. `"Unsupported file type. Accepted formats: PDF, PNG, JPEG, WEBP, TIFF"` or `"File exceeds maximum size of 10 MB"`
- Conversion to BAML inputs:
  ```python
  from baml_py import Image, Pdf
  import base64

  b64 = base64.b64encode(content).decode()
  if mime_type == "application/pdf":
      return Pdf.from_base64("application/pdf", b64)
  else:
      return Image.from_base64(mime_type, b64)
  ```
- The endpoint (Phase 5) will call `await file.read()` to get raw bytes and pass them directly to `validate_and_convert` — this function operates on `bytes`, not on `UploadFile`, so it is easily unit-tested without HTTP machinery

## CRITICAL: Do not trust the `content_type` from `UploadFile`

`UploadFile.content_type` comes from the `Content-Type` header, which is set by the client and is trivially spoofable. Always detect the MIME type from the file's actual bytes:

```python
# WRONG — trusts client-supplied header
if file.content_type != "application/pdf":
    raise UnsupportedFormatError(...)

# CORRECT — inspects actual bytes
content = await file.read()
mime_type = detect_mime_type(content)
if mime_type is None:
    raise UnsupportedFormatError(...)
```

## Notes

- Do not use the `python-magic` library (requires `libmagic` system dependency which makes Docker setup fragile); manual magic byte inspection is simpler and has no runtime dependencies
- TIFF support is worth including since some scan-to-email workflows produce TIFF files; it costs nothing extra to detect
- The `content` bytes returned from `await file.read()` are consumed; the `UploadFile` seek pointer is at the end after this call — there is no need to seek back since validation and conversion happen in one pass
- Empty file check: if `len(content) == 0`, raise `UnsupportedFormatError("Uploaded file is empty")`

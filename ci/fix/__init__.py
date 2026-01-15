"""Fix generation and application module."""

from .inference import infer_source_file
from .extractor import extract_code_from_response, extract_diff_from_response, extract_file_path_from_diff
from .patcher import apply_patch, validate_diff, generate_patch_filename

__all__ = [
    "infer_source_file",
    "extract_code_from_response",
    "extract_diff_from_response",
    "extract_file_path_from_diff",
    "apply_patch",
    "validate_diff",
    "generate_patch_filename",
]

"""Knowledge sources package for RepoBrain."""

from src.knowledge.references import ExplicitReference, extract_explicit_references
from src.knowledge.documents import MarkdownDocumentRecord, DocumentIngestionEngine
from src.knowledge.comments import CommentRecord, CommentIngestionEngine

__all__ = [
    "ExplicitReference",
    "extract_explicit_references",
    "MarkdownDocumentRecord",
    "DocumentIngestionEngine",
    "CommentRecord",
    "CommentIngestionEngine",
]

import hashlib
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.exceptions import DocumentProcessingError
from src.core.types import DocumentChunk, DocumentMetadata, DocumentType
from src.infrastructure.vector_store import VectorStoreService
from src.rag.chunker import DocumentChunker
from src.rag.embeddings import EmbeddingService


class DocumentProcessor(LoggerMixin):
    """Service for processing and indexing financial documents."""

    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
        chunker: DocumentChunker,
    ) -> None:
        self._settings = settings
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._chunker = chunker

    async def process_pdf(
        self,
        pdf_content: bytes,
        metadata: DocumentMetadata,
    ) -> tuple[str, int]:
        """Process a PDF document and index its chunks."""
        file_hash = hashlib.sha256(pdf_content).hexdigest()

        try:
            text, tables = self._extract_pdf_content(pdf_content)

            if not text.strip():
                raise DocumentProcessingError(
                    message="No text content extracted from PDF",
                    document_id=metadata.document_id,
                )

            chunk_metadata = {
                "company": metadata.company,
                "ticker": metadata.ticker,
                "document_type": metadata.document_type.value,
                "reference_date": metadata.reference_date.isoformat(),
            }

            if tables:
                chunks = self._chunker.chunk_with_tables(
                    document_id=metadata.document_id,
                    text=text,
                    tables=tables,
                    metadata=chunk_metadata,
                )
            else:
                chunks = self._chunker.chunk_document(
                    document_id=metadata.document_id,
                    text=text,
                    metadata=chunk_metadata,
                )

            if not chunks:
                raise DocumentProcessingError(
                    message="No chunks generated from document",
                    document_id=metadata.document_id,
                )

            chunks_with_embeddings = await self._generate_embeddings(chunks)

            indexed_count = await self._vector_store.upsert_chunks(chunks_with_embeddings)

            self.logger.info(
                "document_processed",
                document_id=metadata.document_id,
                chunks_created=len(chunks),
                chunks_indexed=indexed_count,
            )

            return file_hash, indexed_count

        except DocumentProcessingError:
            raise
        except Exception as e:
            self.logger.exception(
                "document_processing_error",
                document_id=metadata.document_id,
                error=str(e),
            )
            raise DocumentProcessingError(
                message=f"Failed to process document: {str(e)}",
                document_id=metadata.document_id,
            )

    def _extract_pdf_content(
        self,
        pdf_content: bytes,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Extract text and tables from PDF."""
        text_parts: list[str] = []
        tables: list[dict[str, Any]] = []

        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(f"\n--- Página {page_num} ---\n{page_text}")

                page_tables = page.extract_tables()
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) > 1:
                        tables.append(
                            {
                                "page_number": page_num,
                                "table_index": table_idx,
                                "data": table,
                                "markdown": self._table_to_markdown(table),
                            }
                        )

        return "\n".join(text_parts), tables

    def _table_to_markdown(self, table: list[list[Any]]) -> str:
        """Convert table data to markdown format."""
        if not table:
            return ""

        lines = []

        header = table[0]
        header_line = "| " + " | ".join(str(cell or "") for cell in header) + " |"
        separator = "| " + " | ".join("---" for _ in header) + " |"
        lines.append(header_line)
        lines.append(separator)

        for row in table[1:]:
            row_line = "| " + " | ".join(str(cell or "") for cell in row) + " |"
            lines.append(row_line)

        return "\n".join(lines)

    async def _generate_embeddings(
        self,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        """Generate embeddings for chunks."""
        texts = [chunk.content for chunk in chunks]
        embeddings = await self._embedding_service.embed_texts(texts)

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = embedding

        return chunks

    async def process_text(
        self,
        text: str,
        metadata: DocumentMetadata,
    ) -> tuple[str, int]:
        """Process plain text document and index its chunks."""
        file_hash = hashlib.sha256(text.encode()).hexdigest()

        try:
            chunk_metadata = {
                "company": metadata.company,
                "ticker": metadata.ticker,
                "document_type": metadata.document_type.value,
                "reference_date": metadata.reference_date.isoformat(),
            }

            chunks = self._chunker.chunk_document(
                document_id=metadata.document_id,
                text=text,
                metadata=chunk_metadata,
            )

            if not chunks:
                raise DocumentProcessingError(
                    message="No chunks generated from text",
                    document_id=metadata.document_id,
                )

            chunks_with_embeddings = await self._generate_embeddings(chunks)
            indexed_count = await self._vector_store.upsert_chunks(chunks_with_embeddings)

            return file_hash, indexed_count

        except DocumentProcessingError:
            raise
        except Exception as e:
            raise DocumentProcessingError(
                message=f"Failed to process text: {str(e)}",
                document_id=metadata.document_id,
            )

    async def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        return await self._vector_store.delete_by_document_id(document_id)

    def detect_document_type(self, filename: str, text: str | None = None) -> DocumentType:
        """Detect document type from filename and content."""
        filename_lower = filename.lower()

        type_patterns = {
            DocumentType.BALANCE_SHEET: ["balanço", "balanco", "balance", "bp_"],
            DocumentType.INCOME_STATEMENT: ["dre", "resultado", "income", "demonstração"],
            DocumentType.CASH_FLOW: ["fluxo", "caixa", "cash_flow", "dfc"],
            DocumentType.QUARTERLY_REPORT: ["itr", "trimestral", "quarterly", "3t", "2t", "1t", "4t"],
            DocumentType.ANNUAL_REPORT: ["dfp", "anual", "annual", "12m"],
            DocumentType.EARNINGS_RELEASE: ["release", "earnings", "resultado"],
            DocumentType.RELEVANT_FACT: ["fato_relevante", "fr_", "relevant"],
            DocumentType.PRESENTATION: ["apresenta", "presentation", "investor"],
        }

        for doc_type, patterns in type_patterns.items():
            if any(p in filename_lower for p in patterns):
                return doc_type

        if text:
            text_lower = text[:2000].lower()
            for doc_type, patterns in type_patterns.items():
                if any(p in text_lower for p in patterns):
                    return doc_type

        return DocumentType.OTHER

    def extract_reference_date(
        self,
        filename: str,
        text: str | None = None,
    ) -> datetime:
        """Extract reference date from filename or content."""
        date_patterns = [
            r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})",
            r"(\d{2})[-_]?(\d{2})[-_]?(\d{4})",
            r"([1-4])[tT](\d{4})",
            r"(\d{4})[tT]([1-4])",
        ]

        for pattern in date_patterns[:2]:
            match = re.search(pattern, filename)
            if match:
                try:
                    groups = match.groups()
                    if len(groups[0]) == 4:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    else:
                        return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
                except (ValueError, IndexError):
                    continue

        quarter_match = re.search(r"([1-4])[tT](\d{4})", filename)
        if quarter_match:
            quarter = int(quarter_match.group(1))
            year = int(quarter_match.group(2))
            month = quarter * 3
            return datetime(year, month, 1)

        return datetime.now()

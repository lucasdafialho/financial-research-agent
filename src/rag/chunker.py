import re
from typing import Any
from uuid import uuid4

from src.config.logging import LoggerMixin
from src.config.settings import Settings
from src.core.types import DocumentChunk


class DocumentChunker(LoggerMixin):
    """Service for splitting documents into semantic chunks."""

    SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")
    PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
    TABLE_PATTERN = re.compile(r"(\|[^\n]+\|[\n\r]+)+")
    NUMBER_PATTERN = re.compile(r"R\$\s*[\d.,]+|[\d.,]+\s*%|\d{1,3}(?:\.\d{3})*(?:,\d+)?")

    def __init__(self, settings: Settings) -> None:
        self._chunk_size = settings.rag_chunk_size
        self._chunk_overlap = settings.rag_chunk_overlap

    def chunk_document(
        self,
        document_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """Split a document into chunks with overlap."""
        if not text or not text.strip():
            return []

        text = self._normalize_text(text)
        sections = self._split_into_sections(text)
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for section in sections:
            section_chunks = self._chunk_section(
                section["content"],
                section.get("page_number"),
            )

            for chunk_text in section_chunks:
                if len(chunk_text.strip()) < 50:
                    continue

                chunk = DocumentChunk(
                    chunk_id=str(uuid4()),
                    document_id=document_id,
                    content=chunk_text,
                    page_number=section.get("page_number"),
                    chunk_index=chunk_index,
                    metadata={
                        **(metadata or {}),
                        "section_type": section.get("type", "text"),
                        "has_numbers": bool(self.NUMBER_PATTERN.search(chunk_text)),
                        "char_count": len(chunk_text),
                    },
                )
                chunks.append(chunk)
                chunk_index += 1

        self.logger.info(
            "document_chunked",
            document_id=document_id,
            total_chunks=len(chunks),
            avg_chunk_size=sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0,
        )

        return chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent processing."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_into_sections(self, text: str) -> list[dict[str, Any]]:
        """Split text into logical sections."""
        sections: list[dict[str, Any]] = []

        page_pattern = re.compile(r"(?:^|\n)(?:Página|Page|Pág\.?)\s*(\d+)", re.IGNORECASE)
        pages = page_pattern.split(text)

        if len(pages) > 1:
            current_page = 1
            for i in range(0, len(pages), 2):
                content = pages[i]
                if i + 1 < len(pages):
                    try:
                        current_page = int(pages[i + 1])
                    except ValueError:
                        pass

                if content.strip():
                    section_type = self._detect_section_type(content)
                    sections.append(
                        {
                            "content": content.strip(),
                            "page_number": current_page,
                            "type": section_type,
                        }
                    )
        else:
            paragraphs = self.PARAGRAPH_SPLIT.split(text)
            for para in paragraphs:
                if para.strip():
                    section_type = self._detect_section_type(para)
                    sections.append(
                        {
                            "content": para.strip(),
                            "page_number": None,
                            "type": section_type,
                        }
                    )

        return sections

    def _detect_section_type(self, text: str) -> str:
        """Detect the type of content in a section."""
        if self.TABLE_PATTERN.search(text):
            return "table"

        financial_keywords = [
            "ativo",
            "passivo",
            "patrimônio",
            "receita",
            "despesa",
            "lucro",
            "prejuízo",
            "ebitda",
            "dívida",
            "caixa",
            "fluxo",
        ]
        text_lower = text.lower()
        if any(kw in text_lower for kw in financial_keywords):
            return "financial"

        if text.strip().isupper() and len(text.strip()) < 100:
            return "header"

        return "text"

    def _chunk_section(
        self,
        text: str,
        page_number: int | None,
    ) -> list[str]:
        """Split a section into overlapping chunks."""
        if len(text) <= self._chunk_size:
            return [text]

        sentences = self.SENTENCE_ENDINGS.split(text)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            if current_length + sentence_length > self._chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))

                overlap_text = " ".join(current_chunk)
                if len(overlap_text) > self._chunk_overlap:
                    overlap_sentences: list[str] = []
                    overlap_length = 0
                    for s in reversed(current_chunk):
                        if overlap_length + len(s) > self._chunk_overlap:
                            break
                        overlap_sentences.insert(0, s)
                        overlap_length += len(s)
                    current_chunk = overlap_sentences
                    current_length = overlap_length
                else:
                    current_chunk = []
                    current_length = 0

            current_chunk.append(sentence)
            current_length += sentence_length

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def chunk_with_tables(
        self,
        document_id: str,
        text: str,
        tables: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """Chunk document preserving table structures."""
        chunks = self.chunk_document(document_id, text, metadata)

        for i, table in enumerate(tables):
            table_content = self._format_table(table)
            if table_content:
                chunk = DocumentChunk(
                    chunk_id=str(uuid4()),
                    document_id=document_id,
                    content=table_content,
                    page_number=table.get("page_number"),
                    chunk_index=len(chunks) + i,
                    metadata={
                        **(metadata or {}),
                        "section_type": "table",
                        "table_index": i,
                        "has_numbers": True,
                    },
                )
                chunks.append(chunk)

        return chunks

    def _format_table(self, table: dict[str, Any]) -> str:
        """Format table data as text."""
        if "markdown" in table:
            return table["markdown"]

        if "data" in table:
            rows = table["data"]
            if not rows:
                return ""

            lines = []
            for row in rows:
                line = " | ".join(str(cell) for cell in row)
                lines.append(line)

            return "\n".join(lines)

        return ""

import pytest
from unittest.mock import MagicMock

from src.rag.chunker import DocumentChunker
from src.config.settings import Settings


class TestDocumentChunker:
    """Tests for document chunking."""

    @pytest.fixture
    def chunker(self, test_settings: Settings) -> DocumentChunker:
        return DocumentChunker(test_settings)

    def test_normalize_text(self, chunker: DocumentChunker) -> None:
        """Test text normalization."""
        text = "  Multiple   spaces   and\r\n\r\n\r\nnewlines  "
        normalized = chunker._normalize_text(text)

        assert "  " not in normalized
        assert "\r\n" not in normalized
        assert normalized == "Multiple spaces and\n\nnewlines"

    def test_chunk_document_empty(self, chunker: DocumentChunker) -> None:
        """Test chunking empty document."""
        chunks = chunker.chunk_document("doc-1", "")
        assert len(chunks) == 0

    def test_chunk_document_single_chunk(self, chunker: DocumentChunker) -> None:
        """Test document that fits in single chunk."""
        text = "This is a short document that fits in one chunk."
        chunks = chunker.chunk_document("doc-1", text)

        assert len(chunks) == 1
        assert chunks[0].document_id == "doc-1"
        assert chunks[0].content == text

    def test_chunk_document_multiple_chunks(self, chunker: DocumentChunker) -> None:
        """Test document that requires multiple chunks."""
        sentences = ["This is sentence number {}.".format(i) for i in range(100)]
        text = " ".join(sentences)

        chunks = chunker.chunk_document("doc-1", text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.document_id == "doc-1"
            assert len(chunk.content) > 50

    def test_chunk_with_metadata(self, chunker: DocumentChunker) -> None:
        """Test chunking with metadata."""
        text = "Test document content."
        metadata = {"company": "Petrobras", "ticker": "PETR4"}

        chunks = chunker.chunk_document("doc-1", text, metadata)

        assert len(chunks) == 1
        assert chunks[0].metadata["company"] == "Petrobras"
        assert chunks[0].metadata["ticker"] == "PETR4"

    def test_detect_section_type_table(self, chunker: DocumentChunker) -> None:
        """Test table detection."""
        table_text = "|Col1|Col2|\n|---|---|\n|A|B|"
        section_type = chunker._detect_section_type(table_text)
        assert section_type == "table"

    def test_detect_section_type_financial(self, chunker: DocumentChunker) -> None:
        """Test financial content detection."""
        financial_text = "O lucro líquido foi de R$ 10 bilhões com margem EBITDA de 35%."
        section_type = chunker._detect_section_type(financial_text)
        assert section_type == "financial"

    def test_detect_section_type_text(self, chunker: DocumentChunker) -> None:
        """Test regular text detection."""
        regular_text = "This is just regular text without any special markers."
        section_type = chunker._detect_section_type(regular_text)
        assert section_type == "text"


class TestChunkIndexing:
    """Tests for chunk indexing."""

    @pytest.fixture
    def chunker(self, test_settings: Settings) -> DocumentChunker:
        return DocumentChunker(test_settings)

    def test_chunk_indices_are_sequential(self, chunker: DocumentChunker) -> None:
        """Test that chunk indices are sequential."""
        text = " ".join(["Sentence {}.".format(i) for i in range(50)])
        chunks = chunker.chunk_document("doc-1", text)

        indices = [chunk.chunk_index for chunk in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_ids_are_unique(self, chunker: DocumentChunker) -> None:
        """Test that chunk IDs are unique."""
        text = " ".join(["Sentence {}.".format(i) for i in range(50)])
        chunks = chunker.chunk_document("doc-1", text)

        chunk_ids = [chunk.chunk_id for chunk in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

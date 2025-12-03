from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.dependencies import get_document_processor
from src.api.schemas.responses import DocumentResponse
from src.core.types import DocumentMetadata, DocumentType
from src.rag.processor import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    summary="Upload Document",
    description="Upload a financial document for processing and indexing",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF document to upload"),
    company: str = Form(..., description="Company name"),
    ticker: str = Form(..., description="Stock ticker"),
    document_type: str = Form(..., description="Document type"),
    reference_date: str = Form(..., description="Reference date (YYYY-MM-DD)"),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> DocumentResponse:
    """Upload and process a financial document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    try:
        ref_date = datetime.strptime(reference_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD",
        )

    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        valid_types = [t.value for t in DocumentType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Valid types: {valid_types}",
        )

    document_id = str(uuid4())
    metadata = DocumentMetadata(
        document_id=document_id,
        company=company,
        ticker=ticker.upper(),
        document_type=doc_type,
        reference_date=ref_date,
    )

    try:
        content = await file.read()
        file_hash, chunks_created = await processor.process_pdf(content, metadata)

        return DocumentResponse(
            document_id=document_id,
            company=company,
            ticker=ticker.upper(),
            document_type=document_type,
            reference_date=ref_date,
            chunks_created=chunks_created,
            status="processed",
            message=f"Document processed successfully. {chunks_created} chunks indexed.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}",
        )


@router.delete(
    "/{document_id}",
    summary="Delete Document",
    description="Delete a document and its indexed chunks",
)
async def delete_document(
    document_id: str,
    processor: DocumentProcessor = Depends(get_document_processor),
) -> dict:
    """Delete a document from the index."""
    try:
        success = await processor.delete_document(document_id)

        if success:
            return {
                "status": "deleted",
                "document_id": document_id,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.get(
    "/types",
    summary="List Document Types",
    description="Get list of valid document types",
)
async def list_document_types() -> dict:
    """List all valid document types."""
    return {
        "types": [
            {"value": t.value, "name": t.name}
            for t in DocumentType
        ]
    }

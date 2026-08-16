import logging
import os
from fastapi import APIRouter, UploadFile, status, HTTPException
from fastapi.responses import JSONResponse
from models.enums import ResponseSignal
from routes.schemes.data import ProcessRequest
from services import file_service

logger = logging.getLogger("server.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(project_id: str, file: UploadFile):
    """Validate and upload an educational document to project storage."""
    is_valid, message = file_service.validate_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    try:
        _, file_id = await file_service.save_upload(file, project_id)
        return JSONResponse(
            content={
                "signal": ResponseSignal.FILE_SUCCESSFULLY_VALIDATED.value,
                "file_id": file_id,
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as exc:
        logger.error("Error while uploading file: %s", exc, exc_info=True)
        return JSONResponse(
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@data_router.post("/process/{project_id}")
async def process_endpoint(project_id: str, process_request: ProcessRequest):
    """Extract and split document content into contextual chunks."""
    project_dir = file_service.get_project_directory(project_id)
    file_path = os.path.join(project_dir, process_request.file_id)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {process_request.file_id} not found in project {project_id}",
        )

    try:
        raw_text = file_service.extract_text_from_file(file_path)
        chunks = file_service.chunk_text(
            raw_text,
            chunk_size=process_request.chunk_size,
            overlap_size=process_request.overlap_size,
        )

        if not chunks:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseSignal.PROCESSING_FAILED.value},
            )

        return chunks
    except Exception as exc:
        logger.error("Error while processing file %s: %s", process_request.file_id, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.PROCESSING_FAILED.value},
        )
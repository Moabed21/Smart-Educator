from fastapi import APIRouter, Depends, UploadFile, status, HTTPException
from controllers import DataController, ProjectController, ProcessController
from helpers.config import get_settings, Settings
from fastapi.responses import JSONResponse
from models.enums import ResponseSignal
from .schemes.data import ProcessRequest
import aiofiles
import logging
import os

logger = logging.getLogger('server.error')

data_router = APIRouter(
	prefix="/api/v1/data",
	tags= ["/api/v1/","data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(project_id : str,file: UploadFile,
	app_settings : Settings = Depends(get_settings)):
	# paremeters are: input file, path parameter, env vars

	# because the validation is logic work we seperate it
	# in controllers then call it here
	is_valid, result = DataController().validate_uploaded_file(file=file)

	if not is_valid:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=result
		)
	
	#file_id to the models to know that this file has an id
	file_path, file_id = DataController().generate_unique_filename(
		ori_filename = file.filename,
		project_id   = project_id
	)
	# now we got the path of the file itself

	# ---------------file storing operation---------------------------------
	try:
		async with aiofiles.open(file_path,"wb") as f:
			# wb means open any file in writemode as binary 
			while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
				await f.write(chunk)
	# ----------------------------------------------------------------------
	except Exception as e:
		logger.error(f"error while uploading the file {e}")
		return JSONResponse(
		content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value},
		status_code=status.HTTP_200_OK
	)
	return JSONResponse(
		content = {
			"signal": ResponseSignal.FILE_SUCCESSFULLY_VALIDATED.value,
			"file_id":file_id
			},
		status_code=status.HTTP_200_OK
	)

@data_router.post("/process/{project_id}")
async def process_endpoint(project_id :str, process_request: ProcessRequest):

	file_id = process_request.file_id
	chunk_size = process_request.chunk_size
	overlap_size = process_request.overlap_size

	process_controller= ProcessController(project_id=project_id)

	file_content = process_controller.get_file_content(file_id=file_id)

	file_chunks = process_controller.process_file_content(
		file_content=file_content,
		file_id=file_id,
		chunk_size=chunk_size,
		overlap_size=overlap_size
	)

	if file_chunks is None or len(file_chunks) == 0:
		return JSONResponse(
			status_code=status.HTTP_400_BAD_REQUEST,
			content={
				"signal":ResponseSignal.PROCESSING_FAILED.value
			}
		)
	
	return file_chunks
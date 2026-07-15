from .ProjectController import ProjectController
from .BaseController import BaseController
from models.enums import ResponseSignal
from fastapi import UploadFile
import re
import os

class DataController(BaseController):
	def __init__(self):
		super().__init__()
	
	def validate_uploaded_file(self,file: UploadFile):
		
		if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
			return False, f"{file.content_type}: {ResponseSignal.FILE_NOT_SUPPORTED.value}"
		
		if file.size > self.app_settings.FILE_MAX_SIZE * 1048576:
			return False, f"{file.size}: {ResponseSignal.FILE_SIZE_EXCEEDED.value}"

		return True, ResponseSignal.FILE_SUCCESSFULLY_VALIDATED
	
	def generate_unique_filename(self, ori_filename: str, project_id: str):

		random_key= self.generate_random_string()

		project_path= ProjectController().get_project_path(
			project_id=project_id)

		cleaned_filename= self.get_clean_filename(
			ori_filename=ori_filename)
		
		new_filepath= os.path.join(
			project_path,
			random_key + "_" + cleaned_filename
		)
		# generate the random filename then replace the old path with the new one:)

		while os.path.exists(new_filepath):
			random_key = self.generate_random_string()
			new_filepath = os.path.join(
				project_path,
				random_key + "_" + cleaned_filename
			)
		# if the pathname exists create new one

		return new_filepath, random_key + "_" + cleaned_filename

	def get_clean_filename(self, ori_filename: str):

		cleaned_filename= re.sub(r'[^\w.]','',ori_filename.strip())

		cleaned_filename = cleaned_filename.replace(" ","_")

		return cleaned_filename
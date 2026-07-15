from .BaseController import BaseController
from fastapi import UploadFile
from models.enums import ResponseSignal
import os

class ProjectController(BaseController):
	def __init__(self):
		super().__init__()
	
	def get_project_path(self, project_id: str):
		# create the full path of the file
		project_dir = os.path.join(self.files_dir, project_id)

		# if not exists create it using makedirs cuz 
		# it create the dir and the parent of it if not exist
		if not os.path.exists(project_dir):
			os.makedirs(project_dir)
		
		return project_dir
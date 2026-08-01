from .BaseController import BaseController
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.enums import ProcessingEnum
import asyncio
import os

class ProcessController(BaseController):

    def __init__(self,project_id:str):

        super().__init__()
        self.project_id = project_id

        self.project_path = ProjectController().get_project_path(project_id=project_id)
    
    def get_file_extention(self, filename: str):

        # using splitext to split the text:), then take the last part (extention)
        return os.path.splitext(filename)[-1]

        # if user send a normal text it can be processed easily , but if the file is pdf 
        # or anything else it must be loaded using specific loaders, for this here used langchain

        # idea is easy, give the component the question ,the file and it will do it

        # you may try many solution for a certaion file type to get the best one

        # you may use the same loader for many file types

    def get_file_loader(self, file_id: str):

        file_extention = self.get_file_extention(filename=file_id)
        file_path = os.path.join(
            self.project_path,
            file_id
        )

        if file_extention == ProcessingEnum.TXT.value:

            return TextLoader(file_path,encoding="utf-8")
            # utf-8 for arabic support

        if file_extention == ProcessingEnum.PDF.value:

            return PyMuPDFLoader(file_path)

        # each file type with its certain loader

    async def get_file_content(self, file_id: str):

        loader = self.get_file_loader(file_id=file_id)

        return await asyncio.to_thread(loader.load)

    def process_file_content(self, file_content:list,
        file_id: str, chunk_size:int = 100, overlap_size:int=20):
        # the processing of file is done using loader, which has settings we taken above
        # as parameters
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len
            # len is default way to calculate the split size
            )
        
        file_content_texts= [
            rec.page_content
            for rec in file_content
        ]

        file_content_metadata= [
            rec.metadata
            for rec in file_content
        ]

        chunks = text_splitter.create_documents(
            file_content_texts,
            metadatas = file_content_metadata
        
            #in this way, every chunk of data has the same metadata
        )

        return chunks
from pydantic import BaseModel
from typing import Optional

# schema job is about processing file content ,content extraction,
# validation 

class ProcessRequest(BaseModel):
    file_id: str
    
    chunk_size: Optional[int] = 100
    overlap_size: Optional[int] = 20
    do_reset: Optional[int] = 0

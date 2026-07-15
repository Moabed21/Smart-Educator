from fastapi import FastAPI
from routes import base ,data# Import the module itself

app = FastAPI()

app.include_router(base.base_router)
app.include_router(data.data_router)
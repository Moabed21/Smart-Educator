from contextlib import asynccontextmanager
from helpers.db import create_tables
from fastapi import FastAPI
from routes import base, data
from routes import dataset
from routes import training_pairs
from routes import recommendations_questions

# models must be imported so SQLAlchemy registers them before create_tables() runs
import models.learningOutcome
import models.questions
import models.questionL0Link
import models.evaluationResult

@asynccontextmanager 
async def lifespan(app: FastAPI):
    await create_tables()
    yield  # anything after yield runs on shutdown

app = FastAPI(lifespan=lifespan)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(dataset.dataset_router)
app.include_router(training_pairs.training_pairs_router)
app.include_router(recommendations_questions.rec_questions_router)


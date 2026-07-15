from fastapi import APIRouter, Depends
from helpers.config import get_settings, Settings

# APIrouter is a class that allows the route seperation across files(modules).
base_router = APIRouter(
    # prefix means adding a keyword before every route below
    # ex. the "/" route , afer the prefix below it can only accessed by /api/v2 then /
    prefix="/api/v1",
    #tags for mark every group of routes with specific tag
    tags = ["base"]
)

@base_router.get("/")
    # because we cant continue execution if get_settings fails,
    # we make it as main dependent for the flow
    # we strictly tells that app_settings is from class Settings
async def wel(app_settings : Settings = Depends(get_settings)):

    return {
        "message":app_settings.APP_NAME
    }

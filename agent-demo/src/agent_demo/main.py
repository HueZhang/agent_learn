from fastapi import FastAPI

from agent_demo.config import get_settings
from agent_demo.router import router
from agent_demo.schema import ResponseModel
from agent_demo.service import FeedbackService

app = FastAPI()

@app.on_event("startup")
async def startup():
    setting = get_settings()
    app.state.feedback_service = FeedbackService(setting)


app.include_router(router)



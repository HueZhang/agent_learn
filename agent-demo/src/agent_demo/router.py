from typing import Annotated

from fastapi import APIRouter, Depends, Request

from agent_demo.schema import ResponseModel
from agent_demo.service import FeedbackService

router = APIRouter(tags=["FeedbackAgent"])



def get_feedback_agent(request : Request) -> FeedbackService:
    return request.app.state.feedback_service


ServiceDep = Annotated[FeedbackService, Depends(get_feedback_agent)]

@router.post(
    "/feedback",
    response_model=ResponseModel,
    summary="反馈分类"
)
async def feedback(
    info : str,
    service : ServiceDep
    ) -> ResponseModel:

    return await service.feedback(info)

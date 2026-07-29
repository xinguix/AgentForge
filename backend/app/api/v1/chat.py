from fastapi import APIRouter, HTTPException
from ...schemas.chat import  ChatRequest,ChatResponse
from ...services.chat_service import  ChatService

router = APIRouter(prefix="/chat", tags=["对话"])

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息给Agent,获取AI回答"""
    try:
        result = await ChatService.generate_response(request)
        return ChatResponse(
            answer=result["answer"],
            model=result["model"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM调用失败：{str(e)}")
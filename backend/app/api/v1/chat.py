from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from ...core.database import get_db
from ...schemas.chat import  ChatRequest,ChatResponse
from ...services.chat_service import  ChatService

router = APIRouter(prefix="/chat", tags=["对话"])

#非流式输出
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

#流式输出
@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    SSE流式输出，前端使用EventSource或fetch API读取
    AsyncGenerator的完整写法：AsyncGenerator[YieldType, SendType]
    YieldType:生成器抛出来的东西类型（往外流）
    SendType:外部塞进的东西类型（往里流），此处标记None,表示不需要向里传值
    """
    try:
        #返回StreamingResponse,media_type必须是text/event-stream
        return StreamingResponse(
            ChatService.stream_response(request, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                #禁止缓存
                "Connection": "Keep-alive",
                #保持长连接

                "X-Accel-Buffering": "no",

                #允许跨域（开发环境方便调试）
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流式调用失败：{str(e)}")
        """
        return	正常结束函数	函数彻底销毁，不再保留任何状态	返回一个值，函数结束。
        yield	暂停并挂起函数	函数保留当前所有变量状态（冻结），等待下次调用	返回一个值，但函数没有结束，下次 for 循环可以继续执行。
        raise	主动抛出异常	函数立即中断，不执行后面的代码，直接往外“扔出一个错误”	不返回正常值，而是把错误层层往外抛，直到被 try...except 接住。
        """
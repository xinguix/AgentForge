from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
import os

from ...core.database import get_db
from ...services.document_parser import DocumentParser
from ...services.vector_service import VectorService

router = APIRouter(prefix="/documents", tags=["知识库文档"])

@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
):
    """
    上传并解析文档，返回提取的纯文本内容
    """
    #1.检查文件格式
    allowed_ext = [".pdf", ".md", ".txt", ".docx"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持{allowed_ext}")

    try:
        #2.保存文件
        file_path = await DocumentParser.save_upload_file(file)
        #3.提取文本
        text_content = await DocumentParser.parse_document(file_path)

        chunk_count = await VectorService.index_document(
            db=db,
            file_path=file_path,
            file_name=file.filename,
            content=text_content,
            user_id="default",
            metadata={"upload_time": str(datetime.now())}
        )

        return {
            "filename": file.filename,
            "file_path": file_path,
            "content_preview": text_content[:500],
            "char_count": len(text_content),
            "chunk_count": chunk_count,
            "status": "indexed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败：{str(e)}")
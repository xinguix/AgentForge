from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Dict, List,Any
import asyncio

from ..models.document_chunk import DocumentChunk
from ..core.config import settings

#1.全局单例Embedding 模型（懒加载）
_embedding_model = None

def get_embedding_model():
    """获取本地Embedding 模型单例"""
    global _embedding_model
    if _embedding_model is None:
        #使用CPU加载BGE-small模型
        #注意：首次加载会下载约400MB的模型文件
        _embedding_model = SentenceTransformer('BAAI/bge-small-zh-v1.5', device='cpu')
    return _embedding_model

#2.分块器配置
def get_text_splitter():
    """获取文本分块器"""
    return RecursiveCharacterTextSplitter(
        chunk_size=500,  #每块最多500字符（约150个token）
        chunk_overlap=50,  #重叠50字符，保证上下文连贯
        separators=[
            "\n#", "\n##", "\n###", #优先识别markdown的标题
            "\n\n", "\n", "。", "!","?"," ",""
        ]
    )

#3.核心业务逻辑
class VectorService:

    @staticmethod
    async def index_document(
        db: AsyncSession,
        file_path: str,
        file_name: str,
        content: str,
        user_id: str = "default",
        metadata: Dict[str, Any] = None
    ) -> int:
        """
        将文档内容分块、向量化、存入数据库
        返回：插入的块数量
        """
        #1.分块
        splitter = get_text_splitter()
        chunks = splitter.split_text(content)

        if not chunks:
            return 0

        #2.获取Embedding模型
        model = get_embedding_model()

        #3.批量生成向量（批量编码，速度快）
        # 注意：bge模型输入建议加上“query：” 或 "passage:" 前缀，但索引是用默认即可
        embeddings = model.encode(chunks, convert_to_numpy=True)
        #chunks:这是一个列表，比如【段落1， 段落2】。encode会一次性把这三句话全部算完
        #convert_to_numpy=True 告诉函数返回numpy数组，而不是pytorch张量

        #4.构造数据库对象并批量拆入
        chunk_objs = []
        for i, (chunk_text, embedding_vector) in enumerate(zip(chunks, embeddings)):
        #enumeratr:给配对加上序号i，从0开始，知道这是第几个分块
        #zip(chunks, embeddings):把【“段落1”，“段落2”】和[[0.1,0.2],[0.3,0.4]]按位置配对打包
            chunk_obj = DocumentChunk(
                source_file=file_name,
                user_id=user_id,
                content=chunk_text,
                chunk_metadata=metadata or {"chunk_index": i, "source_path": file_path},
                embedding=embedding_vector.tolist(),  #numpy数组转成python列表
            )
            chunk_objs.append(chunk_obj)

        db.add_all(chunk_objs)
        #add_all：把这些对象打包成一条SQL语句一次性发给PostgreSQL,数据库一次性就能全插进去，速度极快
        await db.commit()
        #将刚才add_all暂存在数据库连接缓存里的数据正式写入硬盘

        return len(chunk_objs)

    @staticmethod
    async def search_similar(
            db: AsyncSession,
            query: str,
            user_id: str = "default",
            top_k: int = 3
    ) -> List[str]:
        """向量检索： 根据用户问题，在知识库中查找最相关的文档片段"""
        # 1.将用户问题向量化
        model = get_embedding_model()
        query_embeddings = model.encode([query], convert_to_numpy=True)[0].tolist()

        # 2.执行pgvector 的余弦相似度搜索
        # 使用<->操作符（余弦距离）
        stmt = select(DocumentChunk).where(
            DocumentChunk.user_id == user_id,
        ).order_by(
            DocumentChunk.embedding.cosine_distance(query_embeddings)
        ).limit(top_k)

        result = await db.execute(stmt)
        chunks = result.scalars().all()
        return [chunk.content for chunk in chunks]
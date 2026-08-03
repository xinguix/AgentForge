import os
import uuid
from pathlib import Path
from typing import List, Optional
import pypdf
import markdown
from docx import Document
from bs4 import BeautifulSoup  #BeautifuSoup: 专门用于解析HTML或XML文档
import re  #提供了一套正则表达式引擎，用于按照特定模式来匹配、查找、替换或分割文本字符串

from ..core.config import settings

class DocumentParser:
    @staticmethod
    async def save_upload_file(upload_file, user_id: str = "default") -> str:
        """
        保存上传的文件到本地，返回文件路径
        """
        #生成唯一文件名，防止重名覆盖
        ext = Path(upload_file.filename).suffix   #suffix:后缀(如.pdf)
        # upload_file.filename:获取原始文件名
        safe_filename = f"{uuid.uuid4()}{ext}"

        #按用户分目录存放（为以后多租户做准备）
        user_dir = Path(settings.upload_dir) / user_id
        #使用/ ：获取拼接路径，得到用户专属子目录（例如./uploads/default）
        user_dir.mkdir(parents=True, exist_ok=True)
        """
        使用pathlib.path.mkdir()方法创建目录：
        parents=True:如果父目录不存在，自动递归创建
        exist_ok=True:如果目录已存在，不抛出FileExistsError,静默跳过 
        """

        file_path = user_dir / safe_filename
        content = await upload_file.read()

        with open(file_path, "wb") as f:
        # 以二进制写入模式（“wb”）打开file_path,使用with语句确保文件写入后自动关闭
            f.write(content)
            #将读取到的二进制内容写入磁盘文件

        return str(file_path)

    @staticmethod
    async def extract_text_from_pdf(file_path: str) -> str:
        """从PDF提取文本"""
        text = ""
        try:
            with open(file_path, "rb") as f:
            #with语句：上下文管理器，用来打开文件。好处：无论是否发生异常，文件都会自动关闭，避免资源泄露
            #open(file_path, "rb"): 以二进制读模式打开文件
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                        #将当前页文本追加到text变量末尾，并加一个换行符
        except Exception as e:
            raise ValueError(f"PDF 解析失败：{str(e)}")

        return text.strip()  #.strip:去掉首尾的空白字符

    @staticmethod
    async def extract_text_form_markdown(file_path: str) -> str:
        """从markdown 提取文本（去除标记符号）"""
        with open(file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        #转化成HTML，再提取纯文本,例如(# 你好)-> (<h1>你好</h1>)
        html = markdown.markdown(md_content)
        soup = BeautifulSoup(html, "html.parser")
        #用BeautifulSoup解析刚才生成的HTML字符串，构建成衣蛾可以方便搜索和遍历的树形结构对象
        text = soup.get_text()
        #get_text()方法会将HTML里所有标签去掉，只留下纯文字内容
        #清理多余行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        #会将\n\s*\n 格式转化为 \n\n的格式  （\s*:中间的空行），作用就是去掉中间的空行
        return text.strip()

    @staticmethod
    async def extract_text_from_txt(file_path: str) -> str:
        """提取TXT文本"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    @staticmethod
    async def extract_text_from_docx(file_path: str) -> str:
        """从Word（.docx）文件中提取纯文本"""
        try:
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            return "\n".join(full_text)
        except Exception as e:
            raise ValueError(f"DOCX 解析失败:{str(e)}")

    @staticmethod
    async def parse_document(file_path: str) -> str:
        """根据文件扩展名自动选择解析器"""
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return await DocumentParser.extract_text_from_pdf(file_path)
        elif ext == ".md":
            return await DocumentParser.extract_text_form_markdown(file_path)
        elif ext == ".txt":
            return await DocumentParser.extract_text_from_txt(file_path)
        elif ext == ".docx":
            return await DocumentParser.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"不支持的文件格式：{ext}")
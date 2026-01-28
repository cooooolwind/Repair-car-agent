from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import json
import asyncio
from agent_backend import run_agent, convert_pdf_to_image

app = FastAPI(title="CarRepair Agent API")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
UPLOAD_DIR = "uploads"
IMAGE_DIR = "image"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[str]] = []


class Message(BaseModel):
    role: str
    content: str


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """聊天接口 - 流式返回"""
    history = request.history if request.history else []

    async def generate():
        try:
            # 调用后端 agent
            for chunk in run_agent(request.message, request.images, history):
                # 将字典转换为 JSON 字符串
                chunk_str = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {chunk_str}\n\n"
        except Exception as e:
            error_chunk = json.dumps({
                "type": "error",
                "content": str(e)
            }, ensure_ascii=False)
            yield f"data: {error_chunk}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """文件上传接口"""
    try:
        # 保存文件
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 如果是 PDF，转换为图片
        if file.filename.lower().endswith('.pdf'):
            image_paths = convert_pdf_to_image(file_path)
            return {
                "success": True,
                "file_path": file_path,
                "image_paths": image_paths,
                "type": "pdf"
            }
        else:
            # 图片文件直接返回路径
            return {
                "success": True,
                "file_path": file_path,
                "image_paths": [file_path],
                "type": "image"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/image/{filename}")
async def get_image(filename: str):
    """获取图片"""
    file_path = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(file_path):
        from fastapi.responses import FileResponse
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
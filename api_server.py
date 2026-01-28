from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import json
import asyncio
from agent_backend import run_agent, convert_pdf_to_image

app = FastAPI(title="CarRepair Agent API")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 🟢 挂载上传和图片目录，让前端可以访问图片
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/image", StaticFiles(directory="image"), name="image")

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

    # 清理图片路径前缀（如果前端传回了完整URL，后端可能只需要本地相对路径）
    # 这里根据你的 backend 逻辑，backend 似乎是直接读文件的，所以要确保传进去的是本地路径
    # 简单的做法：只取最后的文件名或相对路径
    clean_images = []
    if request.images:
        for img in request.images:
            # 如果是完整URL http://.../uploads/xxx.jpg -> uploads/xxx.jpg
            if "uploads/" in img:
                clean_images.append(f"uploads/{os.path.basename(img)}")
            elif "image/" in img:
                clean_images.append(f"image/{os.path.basename(img)}")
            else:
                clean_images.append(img)

    async def generate():
        try:
            # 调用后端 agent
            for chunk in run_agent(request.message, clean_images, history):
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
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 🟢 如果是 PDF，转换为图片
        if file.filename.lower().endswith('.pdf'):
            image_paths = convert_pdf_to_image(file_path)
            # 返回给前端的必须是可以访问的 Web 路径 (加 / 前缀)
            web_image_paths = [f"/{path}".replace("\\", "/") for path in image_paths]
            return {
                "success": True,
                "file_path": file_path,
                "image_paths": web_image_paths,
                "type": "pdf"
            }
        else:
            # 图片文件
            return {
                "success": True,
                "file_path": f"/{file_path}".replace("\\", "/"),
                "image_paths": [f"/{file_path}".replace("\\", "/")],
                "type": "image"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
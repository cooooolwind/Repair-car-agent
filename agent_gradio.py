import gradio as gr
import agent_backend as backend
import os

# --- CSS 样式 ---
custom_css = """
.gradio-container { background-color: white !important; }
footer {display: none !important;}
.bubble-wrap { background-color: #f9f9f9; border-radius: 12px; }

#input-card-group {
    background: white;
    border-radius: 24px !important;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08) !important;
    border: 1px solid rgba(0, 0, 0, 0.03) !important;
    padding: 10px !important;
    margin-top: 20px;
    transition: box-shadow 0.3s ease;
}
#input-card-group:hover { box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12) !important; }

#chat-input textarea {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 16px !important;
}
#chat-input { background-color: transparent !important; border: none !important; }
.upload-button { background-color: transparent !important; border: none !important; }
"""

# --- 处理函数 (增加 state 参数) ---
def agent_response(user_input, history, state):
    """
    state: 这是 gr.State 对象，存储后端的 messages 列表
    """
    if user_input is None: user_input = {}
    text = user_input.get("text", "")
    files = user_input.get("files", [])
    
    raw_file_path = files[0] if files else None
    
    # PDF/图片处理
    final_image_paths = []
    
    if raw_file_path:
        file_ext = os.path.splitext(raw_file_path)[1].lower()
        if file_ext == '.pdf':
            converted_paths = backend.convert_pdf_to_image(raw_file_path)
            if converted_paths:
                final_image_paths = converted_paths
                if not text: text = "请分析这份文档的内容。"
        else:
            final_image_paths = [raw_file_path]

    if history is None: history = []
        
    # --- 👇 这里是修改后的部分 👇 ---
    is_pdf = raw_file_path and raw_file_path.lower().endswith('.pdf')

    if final_image_paths:
        if is_pdf:
            # PDF 模式：仅显示文字，隐藏图片
            display_content = text if text else f"📄 已接收 PDF 文档 ({len(final_image_paths)} 页)"
            history.append({"role": "user", "content": display_content})
        else:
            # 图片模式：显示图片和文字
            for img_path in final_image_paths:
                history.append({"role": "user", "content": f"![]({img_path})"})
            if text: 
                history.append({"role": "user", "content": text})
    elif text:
        history.append({"role": "user", "content": text})
    # --- 👆 修改结束 👆 ---
    
    history.append({"role": "assistant", "content": "🤖 Agent 正在启动..."})
    
    
    full_process_log = ""
    final_answer = ""
    prompt_text = text if text else ("请分析这些图片并执行操作。" if final_image_paths else "")
    
    if not prompt_text:
        yield history, None, full_process_log, gr.update(visible=True), state
        return

    # --- 🌟 调用后端 (传入 state) ---
    # 注意：如果 state 是 None，初始化为空列表
    current_backend_history = state if state is not None else []
    
    generator = backend.run_agent(prompt_text, final_image_paths, current_backend_history)
    
    status_display = "🤖 正在处理中..." 
    
    # 🌟 临时变量，用于接收后端返回的新状态
    new_backend_history = current_backend_history 
    
    for step in generator:
        step_type = step.get("type")
        content = step.get("content")
        
        if step_type == "thought":
            status_display = "🧠 正在思考下一步..."
            full_process_log += f"🧠 **思考**: {content}\n\n"
        elif step_type == "tool_start":
            tool_name = content.split('(')[0] if '(' in content else content
            status_display = f"🛠️ 正在调用工具: {tool_name}..."
            full_process_log += f"🛠️ **工具**: `{content}`\n\n"
        elif step_type == "observation":
            status_display = "👀 正在分析结果..."
            full_process_log += f"👀 **观察**:\n{content}\n\n"
        elif step_type == "result":
            final_answer = content
            full_process_log += f"✅ **结果**: {content}\n\n"
        
        # 🌟 监听状态更新事件
        elif step_type == "update_state":
            new_backend_history = content # 拿到后端整理好的新历史
            # 不把这个显示在日志里

        # 更新 UI
        if final_answer:
            history[-1]["content"] = final_answer
        else:
            history[-1]["content"] = status_display
        
        # 🌟 Yield 必须包含 state (作为第5个返回值)
        yield history, None, full_process_log, gr.update(visible=True), new_backend_history


# --- 构建界面 ---
with gr.Blocks(title="智能修车助手") as demo:
    
    # 🌟 1. 定义状态存储组件 (不可见)
    backend_state = gr.State([]) 

    with gr.Column(elem_id="main-container"):
        gr.HTML("""
        <div style="text-align: center; margin-top: 40px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: center; gap: 10px; color: #4e6af3; margin-bottom: 10px;">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                <span style="font-weight: 500; font-size: 1.2rem;">CarRepair Agent</span>
            </div>
            <h1 style="font-size: 2rem; font-weight: 700; color: #333;">今天有什么可以帮到你？</h1>
        </div>
        """)

    chatbot = gr.Chatbot(
        label="", 
        show_label=False,
        height=400,
        avatar_images=(None, "https://img.icons8.com/color/48/robot-2.png"),
        elem_id="chatbot"
    )

    with gr.Group(elem_id="input-card-group"):
        with gr.Row(equal_height=True):
            chat_input = gr.MultimodalTextbox(
                elem_id="chat-input",
                interactive=True,
                file_types=["image", ".pdf"],
                placeholder="输入指令或上传照片/PDF手册...",
                show_label=False,
                scale=9, 
                container=False 
            )
            
    with gr.Accordion("🧠 思考过程", open=False, visible=False) as process_acc:
        process_display = gr.Markdown("...")

    # 🌟 绑定事件：增加了 backend_state 的输入和输出
    chat_input.submit(
        fn=agent_response, 
        inputs=[chat_input, chatbot, backend_state], # 输入 state
        outputs=[chatbot, chat_input, process_display, process_acc, backend_state] # 输出更新后的 state
    )

# --- agent_gradio.py 底部修改 ---

if __name__ == "__main__":
    # 确保 image 文件夹存在（防止刚启动时报错）
    if not os.path.exists("image"):
        os.makedirs("image")

    demo.queue().launch(
        server_name="127.0.0.1", 
        server_port=6006,
        css=custom_css,          
        theme=gr.themes.Soft(),
        # 🌟 关键修改：允许访问 image 文件夹
        allowed_paths=["./image"] 
    )
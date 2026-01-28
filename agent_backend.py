import re
from openai import OpenAI
import os
import base64
from pdf2image import convert_from_path

# --- 配置 ---
# ⚠️⚠️⚠️ 请确保你的 API Key 正确
API_KEY = "sk-5eb60c1091ba459aa9246ea714db371c" 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 🌟 核心修改：使用视觉模型 Qwen-VL
MODEL_ID = "qwen3-vl-plus" 

AGENT_SYSTEM_PROMPT = """
你是一个智能修车拧螺丝助手。你的任务是分析用户的请求（可能包含图片和pdf），并使用可用工具一步步地解决问题。

# 可用工具:
- `get_point()`: 模拟视觉系统，返回螺丝的坐标。
- `Arm_move(x: int, y: int)`: 移动机械臂到指定位置。
- `Hand_move(type: str)`: 移动机械手，type=‘1’表示向上拧紧，type=‘0’表示向下拧松。

# 行动格式:
你的回答必须严格遵循以下格式。首先是你的思考过程，然后是你要执行的具体行动，每次回复只输出一对Thought-Action：
Thought: [这里是你的思考过程和下一步计划]
Action: 你决定采取的行动，必须是以下格式之一:
- `function_name(arg_name="arg_value")`:调用一个可用工具。
- `Finish[最终答案]`:当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在Action:字段后使用 Finish[最终答案] 来输出最终答案。

请开始吧！
"""

# --- 工具函数 ---
def get_point() -> str:
    return "系统定位反馈：在坐标 (X:200, Y:150) 处发现待处理螺丝孔位。"


def Arm_move(x,y) -> str:
    x,y=200,150
    return "已移动机械臂到指定位置。"

def Hand_move(type: str) -> str:
    val = str(type).strip()
    if val == "1":
        return "机械手状态：已向上移动并拧紧。"
    elif val == "0":
        return "机械手状态：已向下移动归位。"
    else:
        return f"错误：未知类型 {type}。"

available_tools = {
    "get_point": get_point,
    "Arm_move": Arm_move,
    "Hand_move": Hand_move, 
}
# --- 新增：PDF 转图片辅助函数 ---
def convert_pdf_to_image(pdf_path):
    """
    将 PDF 的所有页面转换为图片，并保存到本地 image 文件夹
    """
    try:
        # 1. 定义保存目录
        save_dir = "image"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)  # 如果文件夹不存在，自动创建

        # 转换 PDF
        images = convert_from_path(pdf_path)
        
        saved_paths = []
        if images:
            # 获取 PDF 的文件名（不带路径和后缀），用于给图片命名
            # 例如: /tmp/xxx/manual.pdf -> manual
            pdf_filename = os.path.basename(pdf_path)
            base_name = os.path.splitext(pdf_filename)[0]
            
            # 循环保存每一页
            for i, img in enumerate(images):
                # 2. 拼接保存路径: image/文件名_page_0.jpg
                image_filename = f"{base_name}_page_{i}.jpg"
                save_path = os.path.join(save_dir, image_filename)
                
                img.save(save_path, 'JPEG')
                saved_paths.append(save_path)
                
            print(f"📄 PDF 已转换 {len(saved_paths)} 页图片，保存在: {save_dir}")
            return saved_paths 
        else:
            return []
    except Exception as e:
        print(f"❌ PDF 转换失败: {e}")
        return []


# --- 辅助函数：图片转 Base64 ---
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- LLM 客户端 ---
class OpenAICompatibleClient:
    def __init__(self, model, api_key, base_url):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, messages):
        """
        直接接收 messages 列表，支持多模态格式
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM 调用错误: {e}"

llm = OpenAICompatibleClient(model=MODEL_ID, api_key=API_KEY, base_url=BASE_URL)

# --- 核心 Agent 逻辑 ---
def run_agent(user_text, image_paths=None, history_state=None):
    """
    history_state: 这是一个列表，存储了之前轮次的 [UserMsg, AsstMsg, UserMsg, AsstMsg...]
    """
    # 1. 准备图片列表
    if image_paths:
        if isinstance(image_paths, str): target_images = [image_paths]
        elif isinstance(image_paths, list): target_images = image_paths
        else: target_images = []
    else:
        target_images = []

    # 2. 构建【当前】用户的消息对象
    current_user_content = [{"type": "text", "text": user_text}]
    valid_image_count = 0
    for img_path in target_images:
        base64_image = encode_image(img_path)
        if base64_image:
            current_user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
            valid_image_count += 1
    
    current_user_message = {'role': 'user', 'content': current_user_content}
    
    yield {"type": "log", "content": f"收到请求: {user_text} [含 {valid_image_count} 图]"}

    # 3. 构建【工作记忆】(Working Memory)
    # 工作记忆 = System Prompt + 历史记忆 + 当前用户消息
    # 我们不在 history_state 里存 System Prompt，防止重复
    
    if history_state is None:
        history_state = []
        
    # messages 是发给大模型的完整列表
    messages = [{'role': 'system', 'content': AGENT_SYSTEM_PROMPT}] + history_state + [current_user_message]

    # 4. 开始 ReAct 循环
    final_answer = ""
    
    while True: 
        llm_output = llm.generate(messages)
        
        # 截断处理
        match = re.search(r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)', llm_output, re.DOTALL)
        if match: llm_output = match.group(1).strip()
            
        yield {"type": "thought", "content": llm_output}
        
        # 将思考过程加入临时上下文，让模型知道自己刚才想了什么
        messages.append({'role': 'assistant', 'content': llm_output})

        # 解析 Finish
        finish_match = re.search(r"Finish\[(.*)\]", llm_output, re.DOTALL)
        if finish_match:
            final_answer = finish_match.group(1)
            yield {"type": "result", "content": final_answer}
            break

        # 解析 Action
        action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
        if not action_match:
            # 没解析出Action，可能直接说话了
            final_answer = llm_output
            yield {"type": "result", "content": final_answer} 
            break
            
        action_str = action_match.group(1).strip()
        
        if action_str.startswith("Finish"):
            final_answer = re.match(r"Finish\[(.*)\]", action_str).group(1)
            yield {"type": "result", "content": final_answer}
            break

        # 执行工具
        try:
            tool_name = re.search(r"(\w+)\(", action_str).group(1)
            args_content = re.search(r"\((.*)\)", action_str).group(1).strip()
            kwargs = {}
            if args_content:
                pairs = re.findall(r'(\w+)=["\']?([^"\',\s]+)["\']?', args_content)
                if pairs: kwargs = dict(pairs)
                elif tool_name == "Arm_move": kwargs = {"type": args_content}

            if tool_name in available_tools:
                observation = available_tools[tool_name](**kwargs)
            else:
                observation = f"错误: 工具 '{tool_name}' 不存在"
        except Exception as e:
            observation = f"执行错误: {e}"

        yield {"type": "observation", "content": observation}
        messages.append({'role': 'user', 'content': f"Observation: {observation}"})

    # 5. 任务结束，更新长期记忆
    # 为了节省 Token，我们不把中间的 Thought/Observation 存入长期记忆
    # 我们只存：1. 用户刚才说的话 2. Agent 最终的回答
    
    if final_answer:
        new_history = history_state + [
            current_user_message,
            {'role': 'assistant', 'content': final_answer}
        ]
        # 发送一个特殊事件，通知前端更新状态
        yield {"type": "update_state", "content": new_history}
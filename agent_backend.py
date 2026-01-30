import re
import sys
from openai import OpenAI
import os
import base64
from pdf2image import convert_from_path
from func_caller import MockFuncCaller

# --- 配置 ---
API_KEY = "sk-5eb60c1091ba459aa9246ea714db371c"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_ID = "qwen3-vl-plus"

AGENT_SYSTEM_PROMPT = """
你是一个智能修车拧螺丝助手。你的任务是分析用户的请求（可能包含图片和pdf），并使用可用工具一步步地解决问题。

# 可用工具:
- `get_point()`: 模拟视觉系统，返回螺丝有几个。
- `goto_poi(name: str)`: 移动维修小车到指定的对应name地点，每一个地点上有一个螺丝，参数name可以是2
- `Arm_move(type: str)`: 移动机械手，type=‘1’表示向上拧紧，type=‘0’表示向下拧松。


# 行动格式:
你的回答必须严格遵循以下格式。首先是你的思考过程，然后是你要执行的具体行动，每次回复只输出一对Thought-Action：
Thought: [这里是你的思考过程和下一步计划]
Action: 你决定采取的行动，必须是以下格式之一:
- `function_name(arg_name="arg_value")`:调用一个可用工具。
- `Finish[最终答案]`:当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在Action:字段后使用 Finish[最终答案] 来输出最终答案。

请开始吧！
"""

func_caller = MockFuncCaller()

# --- 工具函数 ---
def get_point() -> str:
    return func_caller.get_point()

def goto_poi(name: str) -> str:
    return func_caller.goto_poi(name)

def Arm_move(type: str) -> str:
    return func_caller.arm_move(type)

available_tools = {
    "get_point": get_point,
    "Arm_move": Arm_move,
    "goto_poi":goto_poi,
}


def convert_pdf_to_image(pdf_path):
    try:
        save_dir = "image"
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        images = convert_from_path(pdf_path)
        saved_paths = []
        if images:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            for i, img in enumerate(images):
                save_path = os.path.join(save_dir, f"{base_name}_page_{i}.jpg")
                img.save(save_path, 'JPEG')
                saved_paths.append(save_path)
            return saved_paths
        return []
    except Exception as e:
        print(f"❌ PDF 转换失败: {e}")
        return []


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


class OpenAICompatibleClient:
    def __init__(self, model, api_key, base_url):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_stream(self, messages):
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": False}
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"LLM 调用错误: {e}"


llm = OpenAICompatibleClient(model=MODEL_ID, api_key=API_KEY, base_url=BASE_URL)


def run_agent(user_text, image_paths=None, history_state=None):
    if image_paths:
        if isinstance(image_paths, str):
            target_images = [image_paths]
        elif isinstance(image_paths, list):
            target_images = image_paths
        else:
            target_images = []
    else:
        target_images = []

    current_user_content = [{"type": "text", "text": user_text}]
    for img_path in target_images:
        try:
            base64_image = encode_image(img_path)
            if base64_image:
                current_user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
        except Exception as e:
            print(f"图片读取失败: {e}")

    current_user_message = {'role': 'user', 'content': current_user_content}
    if history_state is None: history_state = []
    messages = [{'role': 'system', 'content': AGENT_SYSTEM_PROMPT}] + history_state + [current_user_message]

    final_answer = ""
    step_count = 0

    while step_count < 10:
        step_count += 1
        llm_output = ""
        buffer = ""  # 🟢 智能缓冲区
        yield {"type": "thought_start", "content": ""}

        is_action_detected = False

        # 🟢 智能流式循环
        for chunk in llm.generate_stream(messages):
            # 将新字符加入 buffer
            buffer += chunk

            # 如果已经检测到 Action，剩下的全部静默接收，不推给前端
            if is_action_detected:
                llm_output += chunk
                continue

            # 检查 buffer 是否包含停止词 "Action" 或 "Finish"
            # 这里我们检测 "Action" 即可，不用等到冒号，防止 Action 单词本身泄露
            if "Action" in buffer or "Finish" in buffer:
                # 找到停止词的位置
                stop_index = -1
                if "Action" in buffer:
                    stop_index = buffer.index("Action")
                elif "Finish" in buffer:
                    stop_index = buffer.index("Finish")

                # 将停止词之前的内容推给前端
                if stop_index > 0:
                    safe_part = buffer[:stop_index]
                    yield {"type": "thought_stream", "content": safe_part}

                # 剩下的内容归入 llm_output，并标记停止流式输出
                llm_output += buffer
                is_action_detected = True
                buffer = ""  # 清空 buffer

            else:
                # 还没有完全检测到停止词。
                # 检查 buffer 结尾是否可能是停止词的前缀 (例如 "A", "Ac", "Act"...)
                # 只有确认 *不是* 停止词前缀的内容，才推给前端

                # 简单的处理方式：保留最后 6 个字符 (Action 的长度)
                # 如果 buffer 很长，就把前面安全的推出去
                if len(buffer) > 10:
                    safe_part = buffer[:-10]
                    yield {"type": "thought_stream", "content": safe_part}
                    buffer = buffer[-10:]
                    llm_output += safe_part
                else:
                    # buffer 太短，可能正在生成 "Action"，先扣住不发
                    pass

        # 循环结束，把 buffer 里剩余的非 Action 内容推出去（如果 Action 没出现）
        if not is_action_detected and buffer:
            yield {"type": "thought_stream", "content": buffer}
            llm_output += buffer
        elif is_action_detected:
            # 如果 detected，buffer 已经被加到 llm_output 或者清空了，不需要额外操作
            pass

        # 将完整的输出加入历史
        messages.append({'role': 'assistant', 'content': llm_output})

        # --- 解析逻辑 ---

        # 1. 优先解析 Finish
        finish_match = re.search(r"Finish\[(.*?)\]", llm_output, re.DOTALL)
        if not finish_match:
            finish_match = re.search(r"Action:\s*Finish[:\s]+(.*)", llm_output, re.DOTALL)

        if finish_match:
            final_answer = finish_match.group(1).strip()
            yield {"type": "result", "content": final_answer}
            break

        # 2. 解析 Action
        action_match = re.search(r"Action:\s*`?([a-zA-Z0-9_]+)\((.*)\)`?", llm_output, re.DOTALL)

        if not action_match:
            # 如果没有找到 Action 格式，但也没有 Finish
            if "Action:" not in llm_output:
                # 可能是纯对话，把 Thought 去掉后直接显示
                cleaned = re.sub(r"Thought:.*?(?=\n|$)", "", llm_output, flags=re.DOTALL).strip()
                final_answer = cleaned if cleaned else llm_output
                yield {"type": "result", "content": final_answer}
                break
            else:
                observation = "系统提示：无法解析 Action 格式，请检查。"
        else:
            tool_name = action_match.group(1).strip()
            args_str = action_match.group(2).strip()

            # 🟢 增强参数解析：支持位置参数 200, 150 和关键字参数 x=200
            kwargs = {}
            args_list = []

            if args_str:
                # 简单粗暴的解析策略
                try:
                    # 尝试把 "200, 150" split
                    parts = [p.strip() for p in args_str.split(",")]
                    for p in parts:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            kwargs[k.strip()] = v.strip().strip("'\"")
                        else:
                            args_list.append(p.strip().strip("'\""))
                except:
                    pass

            yield {"type": "tool_start", "content": f"{tool_name}({args_str})"}

            if tool_name in available_tools:
                try:
                    # 混合调用
                    observation = available_tools[tool_name](*args_list, **kwargs)
                except Exception as e:
                    observation = f"工具执行异常: {e}"
            else:
                observation = f"错误: 工具 '{tool_name}' 不存在"

        yield {"type": "observation", "content": observation}
        messages.append({'role': 'user', 'content': f"Observation: {observation}"})

    if final_answer:
        new_history = history_state + [current_user_message, {'role': 'assistant', 'content': final_answer}]
        yield {"type": "update_state", "content": new_history}
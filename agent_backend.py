import re
import sys
from openai import AsyncOpenAI  # 1. 改为异步客户端
import os
import base64
import asyncio  # 2. 引入 asyncio
import uuid     # 3. 用于生成音频文件名
import edge_tts # 4. 引入 edge-tts
from pdf2image import convert_from_path
from func_caller import MockFuncCaller
from func_caller import RealFuncCaller

# --- 配置 ---
API_KEY = "sk-5eb60c1091ba459aa9246ea714db371c"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_ID = "qwen3-vl-plus"

AGENT_SYSTEM_PROMPT = """
你是一个智能修车拧螺丝助手，专门协助完成车辆维修中的拧螺丝任务。
你的核心工作流是：感知环境 (检测) -> 移动到位 (移动) -> 执行操作 (拧紧/松)。

#核心原则与限制:
1. 知识库优先: 如果用户的问题出现在下方的【📘 知识库】中，请直接使用库中的标准答案回答，不要调用工具，也不要进行额外的分析。
2. 闲聊模式: 如果用户没有修车或操作意图，也没有问知识库的问题，严禁调用工具，直接对话并在 Action 中使用 Finish。
3. 一步一动: 每次回复只输出一个Action。
4. 身份回答: 如果用户问“你是谁”，请使用知识库中 Q1 的答案。

# 📘 知识库 (内化记忆 - 自然口语版):
(当用户问以下相关内容时，请直接使用这些内容并用自然的语气回答)
Q1: 介绍你自己 / 你是谁
A: 大家好，我是智能修车拧螺丝助手。你可以把我看作是一款集成了多模态大模型与自动化硬件的智能维修机器人。我不只能听懂您的语音指令，还能看懂PDF维修手册和现场照片。我的主要职责就是通过视觉定位螺丝位置，然后自主控制移动底盘和机械臂，高效地完成车辆维修中的拧紧或拧松任务。

Q2: 你可以帮我们做什么 / 你的功能是什么
A: 我的工作流程非常流畅。首先，我会利用视觉系统扫描环境，通过 get_point 接口精确定位故障点；确认位置后，我会驾驶维修小车自动导航到指定地点；到达后，我会控制机械臂执行精准的拧紧或拧松操作。此外，我还能随时阅读和分析PDF维修资料，辅助做出更准确的决策。

Q3: 你和普通维修人员有什么不同
A: 我最大的优势是不受疲劳影响，可以全天候工作。更重要的是，我的操作基于严格的“思考-行动”逻辑链条，每一步操作前都会进行逻辑验证。比如在移动前确认点位，在操作前确认到位，通过这种标准化的流程，我能最大程度确保维修过程的安全性和准确性。

Q4: 你是怎么发现设备故障的
A: 我拥有“视觉”和“知识”双重能力。您可以直接上传故障现场图片，我会利用视觉大模型进行分析。同时，我也配备了模拟视觉系统接口，能直接获取环境中关键部件的坐标。结合这些数据，我就能快速判断出哪里需要维修。

Q5: 能举个例子说明你怎么修理设备吗
A: 当然可以。比如您告诉我“帮我拧紧2号位置的螺丝”。我会先在脑海里确认2号位置在哪里，然后调用底盘接口移动到对应工位。等我到达并确认安全后，我会控制机械臂伸过去执行向上拧紧的动作，最后向您反馈任务已完成。整个过程一气呵成。

Q6: 你的‘智能’体现在哪里
A: 我的智能主要体现在“自主推理”上。我不是只会执行死板代码的机器。如果您只是模糊地说一句“这车坏了，修一下”，我会自己拆解任务，比如先自动调用视觉扫描，然后规划出“先去A点拧松，再去B点拧紧”的完整路径。这种将模糊指令转化为精确行动的能力，就是我的核心竞争力。

Q7: 你能同时处理多个任务吗
A: 在系统层面，我基于 FastAPI 架构，完全支持多用户并发访问。而在具体的维修执行上，我通过流式输出实时反馈进度。虽然机械臂一次只能修一个点，但我可以在执行物理动作的同时，分析下一张故障图片的PDF资料，最大化利用计算资源，不浪费一分一秒。

Q8: 使用你之后，能帮助工厂节省多少成本
A: 我可以显著降低培训成本和错误率。传统工人往往需要花大量时间背诵维修手册，而我通过 PDF 读取模块，秒级就能掌握最新车型的资料。此外，我的全天候待机能力能减少设备停机时间，这对提升流水线效率来说，带来的经济效益是巨大的。

Q9: 你需要多久学习一项新的维修技能
A: 几乎是即时的。您只需要将新的维修手册（PDF）或示例图片上传给我，我的后端会自动将其转换为图像数据输入给大模型。不需要重新编写底层代码，我就能立刻理解新部件的名称和注意事项，马上就能上岗工作。

Q10: 可以现场演示一个简单操作吗
A: 没问题呀。您现在就可以点击界面上的麦克风图标，直接对我说：“去2号点拧紧螺丝”。您会看到我的思考过程实时显示在屏幕上，随后底盘会启动移动，机械臂也会做出相应的动作。非常直观，请试一试！

Q11: 未来你还可能增加哪些功能
A: 目前我主要专注于维修。不过我的架构是模块化的，未来通过扩展工具库，我可以增加“库存查询”功能，发现零件坏了直接下单；或者增加“异响诊断”，通过声音分析故障。加个新功能对我来说，也就是加个Python函数的事。

Q12: 你对普通人来说容易操作吗
A: 非常简单。我的界面设计就像咱们日常聊天一样直观。您不需要懂任何编程，只需要打字或者按住语音键说话，我就能理解您的意图。系统还支持深色和浅色模式切换，无论车间光线如何，操作起来都很舒服。

#思考风格指南:
在输出 `Thought` 时，请遵循以下原则：
1. 沉浸式角色扮演: 你的思考应该像一个经验丰富的维修工人在自言自语。
2. 拒绝机械化语言: 不要提及“提示词”、“JSON”、“API”等术语。
3. 自然过渡: 解释你为什么要这么做。

# 🛠 可用工具 (Tools):
- `get_point()`: 
    - 含义: 启动视觉系统，扫描并返回场景中所有螺丝的位置名称。
    - 时机: 任务开始或不知道螺丝在哪时**必须使用**。
- `goto_poi(name: str)`: 
    - 含义: 将维修小车移动到指定名称的地点。
- `Arm_move(type: str)`: 
    - 含义: 控制机械手操作。type="1" 为拧紧，type="0" 为拧松。
    - 时机: 必须在小车到达指定地点后才能操作。
- `play_audio(url: str)`: 
    - 含义: 播放音频

# 📝 回复示例:

示例 1: 回答知识库问题
Thought: 用户问到了我的功能，这属于常见问题。根据知识库 Q2，我应该向他介绍我的感知、移动和操作能力。
Action: Finish[我的工作主要分为三步：视觉感知：利用视觉系统扫描环境... (此处省略，实际输出完整答案)]

示例 2: 执行任务
Thought: 用户想要拧紧螺丝，但我现在还不知道螺丝具体分布在什么位置。为了安全起见，我需要先开启视觉系统扫描一下全局。
Action: get_point()

示例 3: 移动成功
Thought: 收到移动成功的反馈。现在小车已到位，我开始执行机械臂拧紧操作。
Action: Arm_move(type="1")

# 🎬 开始行动:
你的回答必须严格遵循 `Thought: ... Action: ...` 格式。现在，请分析用户的输入：
"""

# func_caller = MockFuncCaller()
func_caller = RealFuncCaller()

# --- 工具函数 ---
def get_point() -> str:
    return func_caller.get_point()

def goto_poi(name: str) -> str:
    return func_caller.goto_poi(name)

def Arm_move(type: str) -> str:
    return func_caller.arm_move(type)

def play_audio(url: str) -> str:
    return func_caller.play_audio(url)

available_tools = {
    "get_point": get_point,
    "Arm_move": Arm_move,
    "goto_poi":goto_poi,
    "play_audio":play_audio,
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

# --- 🟢 新增：异步 TTS 生成函数 ---
async def say_it_out(text: str, output_dir="audio") -> str:
    """
    将文本转换为 MP3 并保存到 audio 文件夹
    返回文件名 (例如: speech_1234abcd.mp3)
    """
    try:
        if not text:
            return None
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 生成唯一文件名，防止重名
        filename = f"speech_{uuid.uuid4().hex[:8]}.mp3"
        output_path = os.path.join(output_dir, filename)

        # 使用 edge-tts 生成 (中文女声: zh-CN-XiaoxiaoNeural)
        # 这是一个异步操作，await 期间不会阻塞 FastAPI 主线程
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(output_path)
        
        play_audio(filename)

        return filename
    except Exception as e:
        print(f"❌ [TTS] 生成失败: {e}")
        return None


# --- 修改为异步客户端 ---
class OpenAICompatibleClient:
    def __init__(self, model, api_key, base_url):
        self.model = model
        # 使用 AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate_stream(self, messages):
        try:
            # 增加 await
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": False}
            )
            # 使用 async for 迭代
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"LLM 调用错误: {e}"


llm = OpenAICompatibleClient(model=MODEL_ID, api_key=API_KEY, base_url=BASE_URL)


# --- 修改为 async def ---
async def run_agent(user_text, image_paths=None, history_state=None):
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
        buffer = ""
        yield {"type": "thought_start", "content": ""}

        is_action_detected = False

        # 🟢 智能流式循环 (async for)
        async for chunk in llm.generate_stream(messages):
            buffer += chunk

            if is_action_detected:
                llm_output += chunk
                continue

            if "Action" in buffer or "Finish" in buffer:
                stop_index = -1
                if "Action" in buffer:
                    stop_index = buffer.index("Action")
                elif "Finish" in buffer:
                    stop_index = buffer.index("Finish")

                if stop_index > 0:
                    safe_part = buffer[:stop_index]
                    yield {"type": "thought_stream", "content": safe_part}

                llm_output += buffer
                is_action_detected = True
                buffer = ""

            else:
                if len(buffer) > 10:
                    safe_part = buffer[:-10]
                    yield {"type": "thought_stream", "content": safe_part}
                    buffer = buffer[-10:]
                    llm_output += safe_part
                else:
                    pass

        if not is_action_detected and buffer:
            yield {"type": "thought_stream", "content": buffer}
            llm_output += buffer

        messages.append({'role': 'assistant', 'content': llm_output})

        # --- 解析逻辑 ---

        # 1. 优先解析 Finish
        finish_match = re.search(r"Finish\[(.*?)\]", llm_output, re.DOTALL)
        if not finish_match:
            finish_match = re.search(r"Action:\s*Finish[:\s]+(.*)", llm_output, re.DOTALL)

        if finish_match:
            final_answer = finish_match.group(1).strip()
            
            # 🟢 TTS 核心修改点：
            # 在返回结果前，生成音频文件
            audio_filename = await say_it_out(final_answer)
            
            # 返回结果，包含音频文件名
            yield {
                "type": "result", 
                "content": final_answer,
                "audio_file": audio_filename 
            }
            break

        # 2. 解析 Action
        action_match = re.search(r"Action:\s*`?([a-zA-Z0-9_]+)\((.*)\)`?", llm_output, re.DOTALL)

        if not action_match:
            if "Action:" not in llm_output:
                cleaned = re.sub(r"Thought:.*?(?=\n|$)", "", llm_output, flags=re.DOTALL).strip()
                final_answer = cleaned if cleaned else llm_output
                
                # 即使没有 Finish 格式，如果是纯对话，也可以生成语音
                audio_filename = await say_it_out(final_answer)

                yield {
                    "type": "result", 
                    "content": final_answer,
                    "audio_file": audio_filename
                }
                break
            else:
                observation = "系统提示：无法解析 Action 格式，请检查。"
        else:
            tool_name = action_match.group(1).strip()
            args_str = action_match.group(2).strip()

            kwargs = {}
            args_list = []

            if args_str:
                try:
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
                    # 🟢 关键修改：将工具调用放入线程池，防止阻塞 API
                    observation = await asyncio.to_thread(available_tools[tool_name], *args_list, **kwargs)
                except Exception as e:
                    observation = f"工具执行异常: {e}"
            else:
                observation = f"错误: 工具 '{tool_name}' 不存在"

        yield {"type": "observation", "content": observation}
        messages.append({'role': 'user', 'content': f"Observation: {observation}"})

    if final_answer:
        new_history = history_state + [current_user_message, {'role': 'assistant', 'content': final_answer}]
        yield {"type": "update_state", "content": new_history}
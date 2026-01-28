# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RepairAgent is a Python-based AI assistant for car repair guidance. It uses a vision-language model (Alibaba's Qwen-VL) to analyze repair manual images and PDFs, then guides users through repair procedures using simulated robotic arm control.

**Tech Stack**: Python, Gradio (web UI), OpenAI-compatible API client

## Development Commands

**Install dependencies** (not yet tracked in requirements.txt):
```bash
pip install gradio openai pdf2image
```

**Run the application**:
```bash
python agent_gradio.py
```

The Gradio interface runs on `http://127.0.0.1:6006` by default.

## Architecture

The system consists of two main files:

### `agent_backend.py`
Core agent logic implementing a ReAct (Reason + Act) loop:
- **`OpenAICompatibleClient`**: Custom client for Alibaba's Qwen-VL API
- **`run_agent()`**: Main agent loop that reasons, selects tools, and executes actions
- **Tools**:
  - `get_point()`: Simulates visual detection of screw coordinates
  - `Arm_move()`: Controls robotic arm movement (x, y, z coordinates)
  - `Hand_move()`: Controls robotic hand (tighten/loosen operations)

### `agent_gradio.py`
Gradio web interface providing:
- Multimodal chat UI (text + images + PDFs)
- Streaming responses with collapsible thought process display
- Conversation state management
- PDF-to-image conversion for repair manual analysis

## Data Flow

1. User inputs text and uploads files (images/PDFs) via Gradio UI
2. PDFs are converted to images using `pdf2image`
3. Agent runs ReAct loop: analyze problem → select tool → execute action → observe result
4. Tool results and reasoning are streamed back to user in real-time
5. Conversation history is maintained for context

## Configuration

**API Configuration** (currently hardcoded in `agent_backend.py`):
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Model: `qwen3-vl-plus`
- API key: Stored in code (should be moved to environment variables)

**Server Configuration** (in `agent_gradio.py`):
- Host: `127.0.0.1`
- Port: `6006`

## Key Implementation Details

### ReAct Pattern
The agent uses a reasoning-acting loop where it:
1. **Observes**: Analyzes current state (user input + images)
2. **Thinks**: Decides next action using the LLM
3. **Acts**: Executes tool (get_point, Arm_move, Hand_move)
4. **Repeats**: Until the repair task is complete

### Multimodal Processing
- Images are base64-encoded for API transmission
- PDFs are converted to images before processing
- The vision-language model can interpret repair manual diagrams

### Tool Execution
- Tools are simulated (no actual robotic hardware connected)
- Each tool returns descriptive results about the action taken
- Tool outputs are fed back to the LLM for decision-making

## Known Issues

- **Security**: API key is hardcoded in source (line 9 of `agent_backend.py`)
- **No error handling**: API failures or timeouts are not handled gracefully
- **No input validation**: Tool parameters are not validated before execution
- **Missing dependencies**: No `requirements.txt` file for dependency management
- **No tests**: No test framework or unit tests configured

// API 配置
const API_BASE_URL = 'http://127.0.0.1:8000';

// 状态管理
let chatHistory = [];
let uploadedImages = [];
let isProcessing = false;

// DOM 元素
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const fileInput = document.getElementById('fileInput');
const previewImages = document.getElementById('previewImages');
const messagesContainer = document.getElementById('messages');
const welcomeScreen = document.getElementById('welcomeScreen');
const chatContainer = document.getElementById('chatContainer');
const themeToggle = document.getElementById('themeToggle');
const scrollButton = document.getElementById('scrollButton');
const appLogo = document.querySelector('.logo');

// 主题切换
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const sunIcon = themeToggle.querySelector('.sun-icon');
    const moonIcon = themeToggle.querySelector('.moon-icon');
    if (theme === 'dark') {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
    }
}

function adjustTextareaHeight() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

function checkInputState() {
    const hasText = messageInput.value.trim().length > 0;
    const hasImages = uploadedImages.length > 0;
    sendButton.disabled = !hasText && !hasImages || isProcessing;
}

// 重置回到主页
function resetToHome() {
    document.body.classList.remove('chat-active');
    chatContainer.classList.remove('active');
    if (welcomeScreen) welcomeScreen.classList.remove('hidden');

    chatHistory = [];
    uploadedImages = [];
    isProcessing = false;

    messagesContainer.innerHTML = '';
    previewImages.innerHTML = '';
    messageInput.value = '';
    fileInput.value = '';

    adjustTextareaHeight();
    checkInputState();
}

// 文件上传
async function handleFileUpload(files) {
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const previewId = `preview-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            addPreviewImage(file, previewId, true);

            const response = await fetch(`${API_BASE_URL}/api/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                if (data.type === 'pdf') {
                    uploadedImages.push(...data.image_paths);
                } else {
                    uploadedImages.push(data.file_path);
                }
                removePreviewImage(previewId);
                if (data.type === 'pdf') {
                    data.image_paths.forEach((imgPath, index) => {
                        addPreviewImageFromPath(imgPath, `pdf-${Date.now()}-${index}`);
                    });
                } else {
                    addPreviewImageFromPath(data.file_path, `img-${Date.now()}`);
                }
            }
        } catch (error) {
            console.error('上传失败:', error);
            alert('文件上传失败，请重试');
            removePreviewImage(previewId);
        }
    }
    checkInputState();
}

function addPreviewImage(file, id, isLoading = false) {
    const reader = new FileReader();
    reader.onload = (e) => {
        createPreviewElement(e.target.result, id);
    };
    reader.readAsDataURL(file);
}

function addPreviewImageFromPath(path, id) {
    const fullPath = path.startsWith('http') || path.startsWith('/') ? path : `${API_BASE_URL}/${path}`;
    createPreviewElement(fullPath, id);
}

function createPreviewElement(src, id) {
    const div = document.createElement('div');
    div.className = 'preview-image';
    div.id = id;
    div.innerHTML = `
        <img src="${src}" alt="Preview">
        <button class="preview-image-remove" onclick="removePreviewImage('${id}')">✕</button>
    `;
    previewImages.appendChild(div);
}

function removePreviewImage(id) {
    const element = document.getElementById(id);
    if (element) element.remove();
}

// 发送消息
async function sendMessage() {
    const text = messageInput.value.trim();
    if ((!text && uploadedImages.length === 0) || isProcessing) return;

    if (!document.body.classList.contains('chat-active')) {
        document.body.classList.add('chat-active');
        setTimeout(() => {
            chatContainer.classList.add('active');
        }, 300);
    }

    addMessage('user', text, uploadedImages);

    messageInput.value = '';
    messageInput.style.height = 'auto';
    const currentImages = [...uploadedImages];
    uploadedImages = [];
    previewImages.innerHTML = '';
    isProcessing = true;
    checkInputState();

    const assistantMessageId = addMessage('assistant', '', [], true);
    const thinkingProcessId = `thinking-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text || '请分析这些图片',
                history: chatHistory, // 发送当前历史
                images: currentImages
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamData(data, assistantMessageId, thinkingProcessId);
                    } catch (e) { console.error('解析失败:', e); }
                }
            }
        }

        // 🔴 删除：不要在这里手动 push chatHistory，等待后端 update_state
        // chatHistory.push({ role: 'user', content: text });

    } catch (error) {
        console.error('发送失败:', error);
        updateMessage(assistantMessageId, '抱歉，发生了错误。请重试。');
    } finally {
        isProcessing = false;
        checkInputState();
    }
}

function handleStreamData(data, messageId, thinkingId) {
    const type = data.type;
    const content = data.content;

    switch (type) {
        case 'thought_start':
            if (!hasThinkingProcessElement(thinkingId)) addThinkingProcess(messageId, thinkingId);
            appendThinkingStep(thinkingId, '🧠 思考', '');
            break;

        case 'thought_stream':
            if (!hasThinkingProcessElement(thinkingId)) addThinkingProcess(messageId, thinkingId);
            appendThinkingText(thinkingId, content);
            break;

        case 'tool_start':
            appendThinkingStep(thinkingId, '🛠️ 调用工具', content);
            break;

        case 'observation':
            appendThinkingStep(thinkingId, '👀 观察结果', content);
            break;

        case 'result':
            updateMessage(messageId, content);
            // 🔴 删除：不要在这里手动 push chatHistory
            // chatHistory.push({ role: 'assistant', content: content });
            break;

        // 🟢 新增：接收后端同步的完整历史记录（包含图片和正确顺序）
        case 'update_state':
            chatHistory = content;
            console.log("✅ 历史记录已同步，长度:", chatHistory.length);
            break;

        case 'error':
            updateMessage(messageId, `❌ 错误: ${content}`);
            break;
    }
}

function addMessage(role, text, images = [], isLoading = false) {
    const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.id = messageId;

    const avatar = role === 'user' ? '👤' : '🤖';
    let imagesHTML = '';
    if (images.length > 0) {
        imagesHTML = '<div class="message-images">';
        images.forEach(imgPath => {
            const src = imgPath.startsWith('/') || imgPath.startsWith('http') ? imgPath : `${API_BASE_URL}/${imgPath}`;
            imagesHTML += `<img src="${src}" alt="Uploaded" class="message-image">`;
        });
        imagesHTML += '</div>';
    }

    const loadingHTML = isLoading ? '<div class="typing-indicator"><span></span><span></span><span></span></div>' : '';
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${imagesHTML}
            <div class="message-bubble">${text}${loadingHTML}</div>
        </div>
    `;
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageId;
}

function updateMessage(messageId, text) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const bubble = messageDiv.querySelector('.message-bubble');
        const indicator = bubble.querySelector('.typing-indicator');
        if (indicator) indicator.remove();
        bubble.innerText = text || '';
        scrollToBottom();
    }
}

function addThinkingProcess(messageId, thinkingId) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;

    if (document.getElementById(thinkingId)) return;

    const content = messageDiv.querySelector('.message-content');
    const thinkingDiv = document.createElement('div');
    // 默认关闭 (不加 open 类)
    thinkingDiv.className = 'thinking-process';
    thinkingDiv.id = thinkingId;
    thinkingDiv.innerHTML = `
        <div class="thinking-header" onclick="toggleThinking('${thinkingId}')">
            <span>🧠 思考过程</span>
            <svg class="thinking-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        <div class="thinking-content" id="${thinkingId}-content"></div>
    `;
    const bubble = messageDiv.querySelector('.message-bubble');
    if (bubble) {
        content.insertBefore(thinkingDiv, bubble);
    } else {
        content.appendChild(thinkingDiv);
    }
}

function hasThinkingProcessElement(thinkingId) { return document.getElementById(thinkingId) !== null; }

function appendThinkingStep(thinkingId, icon, content) {
    const thinkingContent = document.getElementById(`${thinkingId}-content`);
    if (thinkingContent) {
        const step = document.createElement('div');
        step.className = 'thinking-step';
        step.innerHTML = `<span class="thinking-step-icon">${icon}</span><span class="step-text">${content}</span>`;
        thinkingContent.appendChild(step);
        thinkingContent.scrollTop = thinkingContent.scrollHeight;
    }
}

function appendThinkingText(thinkingId, text) {
    const thinkingContent = document.getElementById(`${thinkingId}-content`);
    if (thinkingContent) {
        const steps = thinkingContent.getElementsByClassName('thinking-step');
        if (steps.length === 0) {
            appendThinkingStep(thinkingId, '🧠 思考', '');
        }
        const lastStep = steps[steps.length - 1];
        const textSpan = lastStep.querySelector('.step-text');
        if (textSpan) {
            textSpan.innerText += text;
        } else {
            lastStep.innerText += text;
        }
        thinkingContent.scrollTop = thinkingContent.scrollHeight;
    }
}

function toggleThinking(thinkingId) {
    const thinkingDiv = document.getElementById(thinkingId);
    if (thinkingDiv) thinkingDiv.classList.toggle('open');
}

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function handleScroll() {
    const scrollY = window.scrollY;
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    if (scrollY + windowHeight < documentHeight - 200) {
        scrollButton.classList.add('visible');
    } else {
        scrollButton.classList.remove('visible');
    }
}

messageInput.addEventListener('input', () => { adjustTextareaHeight(); checkInputState(); });
messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
sendButton.addEventListener('click', sendMessage);
fileInput.addEventListener('change', (e) => { if (e.target.files.length > 0) { handleFileUpload(e.target.files); } e.target.value = ''; });
themeToggle.addEventListener('click', toggleTheme);
scrollButton.addEventListener('click', scrollToBottom);
window.addEventListener('scroll', handleScroll);

if (appLogo) {
    appLogo.addEventListener('click', (e) => {
        e.preventDefault();
        resetToHome();
    });
}

document.body.addEventListener('dragover', (e) => { e.preventDefault(); });
document.body.addEventListener('drop', (e) => {
    e.preventDefault();
    const files = [];
    for (const item of e.dataTransfer.items) {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            if (file.type.startsWith('image/') || file.name.endsWith('.pdf')) {
                files.push(file);
            }
        }
    }
    if (files.length > 0) handleFileUpload(files);
});

initTheme();
checkInputState();
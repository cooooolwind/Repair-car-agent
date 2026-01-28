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

// 输入框自动调整高度
function adjustTextareaHeight() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

// 检查输入状态
function checkInputState() {
    const hasText = messageInput.value.trim().length > 0;
    const hasImages = uploadedImages.length > 0;
    sendButton.disabled = !hasText && !hasImages || isProcessing;
}

// 文件上传处理
async function handleFileUpload(files) {
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            // 显示上传中状态
            const previewId = `preview-${Date.now()}`;
            addPreviewImage(file, previewId, true);

            const response = await fetch(`${API_BASE_URL}/api/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                if (data.type === 'pdf') {
                    // PDF 转换后的图片
                    uploadedImages.push(...data.image_paths);
                } else {
                    // 普通图片
                    uploadedImages.push(data.file_path);
                }

                // 更新预览
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

// 添加预览图片
function addPreviewImage(file, id, isLoading = false) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const div = document.createElement('div');
        div.className = 'preview-image';
        div.id = id;
        div.innerHTML = `
            <img src="${e.target.result}" alt="Preview">
            <button class="preview-image-remove" onclick="removePreviewImage('${id}')">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;
        previewImages.appendChild(div);
    };
    reader.readAsDataURL(file);
}

function addPreviewImageFromPath(path, id) {
    const div = document.createElement('div');
    div.className = 'preview-image';
    div.id = id;
    div.innerHTML = `
        <img src="${path}" alt="Preview">
        <button class="preview-image-remove" onclick="removePreviewImage('${id}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    `;
    previewImages.appendChild(div);
}

function removePreviewImage(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

// 发送消息
async function sendMessage() {
    const text = messageInput.value.trim();

    if ((!text && uploadedImages.length === 0) || isProcessing) return;

    // 隐藏欢迎屏幕，显示聊天
    welcomeScreen.classList.add('hidden');
    chatContainer.classList.add('active');

    // 添加用户消息
    addMessage('user', text, uploadedImages);

    // 清空输入
    messageInput.value = '';
    messageInput.style.height = 'auto';
    const currentImages = [...uploadedImages];
    uploadedImages = [];
    previewImages.innerHTML = '';
    isProcessing = true;
    checkInputState();

    // 添加助手消息占位符
    const assistantMessageId = addMessage('assistant', '', [], true);
    const thinkingProcessId = `thinking-${Date.now()}`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text || '请分析这些图片',
                history: chatHistory,
                images: currentImages
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let thinkingProcess = '';
        let hasThinkingProcess = false;

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
                    } catch (e) {
                        console.error('解析失败:', e);
                    }
                }
            }
        }

        // 保存到历史记录
        chatHistory.push({
            role: 'user',
            content: text
        });

    } catch (error) {
        console.error('发送失败:', error);
        updateMessage(assistantMessageId, '抱歉，发生了错误。请重试。');
    } finally {
        isProcessing = false;
        checkInputState();
    }
}

// 处理流式数据
function handleStreamData(data, messageId, thinkingId) {
    const type = data.type;
    const content = data.content;

    switch (type) {
        case 'thought':
            // 显示思考过程
            if (!hasThinkingProcessElement(thinkingId)) {
                addThinkingProcess(messageId, thinkingId);
            }
            appendThinkingStep(thinkingId, '🧠 思考', content);
            break;

        case 'observation':
            appendThinkingStep(thinkingId, '👀 观察', content);
            break;

        case 'result':
            // 显示最终结果
            updateMessage(messageId, content);
            // 更新历史记录
            chatHistory.push({
                role: 'assistant',
                content: content
            });
            break;

        case 'error':
            updateMessage(messageId, `❌ 错误: ${content}`);
            break;
    }
}

// 添加消息
function addMessage(role, text, images = [], isLoading = false) {
    const messageId = `msg-${Date.now()}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.id = messageId;

    const avatar = role === 'user' ? '👤' : '🤖';

    let imagesHTML = '';
    if (images.length > 0) {
        imagesHTML = '<div class="message-images">';
        images.forEach(imgPath => {
            imagesHTML += `<img src="${imgPath}" alt="Uploaded" class="message-image">`;
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

// 更新消息
function updateMessage(messageId, text) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const bubble = messageDiv.querySelector('.message-bubble');
        bubble.innerHTML = text;
        scrollToBottom();
    }
}

// 添加思考过程
function addThinkingProcess(messageId, thinkingId) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;

    const content = messageDiv.querySelector('.message-content');

    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'thinking-process open';
    thinkingDiv.id = thinkingId;
    thinkingDiv.innerHTML = `
        <div class="thinking-header" onclick="toggleThinking('${thinkingId}')">
            <svg class="thinking-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"/>
            </svg>
            🧠 思考过程
        </div>
        <div class="thinking-content" id="${thinkingId}-content"></div>
    `;

    content.appendChild(thinkingDiv);
}

function hasThinkingProcessElement(thinkingId) {
    return document.getElementById(thinkingId) !== null;
}

// 添加思考步骤
function appendThinkingStep(thinkingId, icon, content) {
    const thinkingContent = document.getElementById(`${thinkingId}-content`);
    if (thinkingContent) {
        const step = document.createElement('div');
        step.className = 'thinking-step';
        step.innerHTML = `<span class="thinking-step-icon">${icon}</span>${content}`;
        thinkingContent.appendChild(step);
    }
}

// 切换思考过程显示
function toggleThinking(thinkingId) {
    const thinkingDiv = document.getElementById(thinkingId);
    if (thinkingDiv) {
        thinkingDiv.classList.toggle('open');
    }
}

// 滚动到底部
function scrollToBottom() {
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: 'smooth'
    });
}

// 滚动按钮
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

// 事件监听
messageInput.addEventListener('input', () => {
    adjustTextareaHeight();
    checkInputState();
});

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendButton.addEventListener('click', sendMessage);

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files);
    }
    // 清空 input 以允许重复上传同一文件
    e.target.value = '';
});

themeToggle.addEventListener('click', toggleTheme);

scrollButton.addEventListener('click', scrollToBottom);

window.addEventListener('scroll', handleScroll);

// 建议卡片点击
document.querySelectorAll('.suggestion-card').forEach(card => {
    card.addEventListener('click', () => {
        const prompt = card.getAttribute('data-prompt');
        messageInput.value = prompt;
        checkInputState();
        messageInput.focus();
    });
});

// 拖拽上传
document.body.addEventListener('dragover', (e) => {
    e.preventDefault();
});

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
    if (files.length > 0) {
        handleFileUpload(files);
    }
});

// 初始化
initTheme();
checkInputState();

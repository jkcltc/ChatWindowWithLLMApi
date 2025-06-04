# ChatWindowWithLLMApi
 
基于 PyQt5 的大型语言模型（LLM）聊天窗口，专为角色扮演交互和token消耗量优化，具备增强的长上下文记忆能力。  
代码是学习中写的，正在平屎山。
![image](https://github.com/user-attachments/assets/1d806bc2-d9ac-4803-8ac1-71722b877a59)

## ✨ 功能特性
 
- **长上下文优化**  
  通过自迭代摘要技术，  
  将 4 万+ 字的对话内容压缩至 4-6 千字后发送至 API，AI 仍能保留截断点之前的记忆。  
  显著节省长篇角色扮演场景中的 token 消耗。  
 
- **角色扮演状态栏**  
  内置角色状态栏，启用后自动添加至对话界面。状态可由用户、AI 或根据对话进程动态更新。  
 
- **主线剧情生成器**  
  快速生成世界观和剧情线，支持自定义剧情。推荐使用轻量级 AI（免费/本地运行）进行节点更新，以最小化 API token 消耗。  
 
- **本地与在线模型支持**  
  支持来自 Ollama 的本地模型  
  支持来自 Deepseek、百度、Siliconflow、腾讯的 API 模型  
 
- **多模态生成**  
  支持对话过程中同步生成 **文本** 和 **图像**  
  *(需使用 [Novita API](https://www.novita.ai/))* 
 
- **轻松部署**  
  自动安装依赖项 - 仅需 Python 即可运行  
  *(建议使用虚拟环境)*
 
## 🚀 快速上手
 
### 环境要求
- Python 3.9+（低版本可能兼容，但未测试）
- Novita API 密钥（用于图像生成）
 
### 安装步骤
```bash
# 克隆仓库
git clone https://github.com/jkcltc/ChatWindowWithLLMApi.git
```
###启用语音合成（TTS）  
- 将 chatapi_tts_server.py 和 start_chatapi_tts_server.bat 移动至 CosyVoice 安装目录
- 准备音频文件并重命名为 2342.wav，放置于 CosyVoice 安装目录
- 在主窗口中编辑 TTS 设置（Ctrl+Q 打开设置，左侧标签页第 3 页）

# ChatWindowWithLLMApi

A PYQT5-based LLM chat window optimized for role-playing interactions, with enhanced long-context memory capabilities.

## ✨ Features

- **Long-context Optimization**  
  By using self-iterative summarization,  
  After truncating 40+k of words of dialogue to 4-6k words and sending them to the API, the AI can still retain memories from before the truncation point.  
  Significantly saving tokens during extended role-playing scenarios with lengthy plots.  

- **Role Play Status Bar:**  
  The built-in character status bar will automatically be added to the conversation once enabled and mounted. Status can be updated by the user, AI, or dynamically as the dialogue progresses.  
﻿
- **Main Story Generator**:  
  Rapidly generates worlds and storylines using AI. Supports custom plots. Lightweight AI (free/local-run) is recommended for node updates to minimize API token consumption.  

- **Local & Online models**:  
  Support local models from ollama.  
  Support api models from Deepseek, Baidu, Siliconflow, Tensent.  

- **Multimodal Generation**  
  Supports synchronous **text generation** and **image generation** during conversations  
  *(Requires [Novita API](https://www.novita.ai/))* 

- **Easy Setup**  
  Automatic dependency installation - just Python required to run  
  *(Recommended to use in virtual environment)*

## 🚀 Quick Start

### Prerequisites
- Python 3.9+（lower versions might work, not tested yet)
- Novita API key (for image generation)

### Installation
```bash
# Clone repository
git clone https://github.com/jkcltc/ChatWindowWithLLMApi.git
```

### Enable tts
-  move chatapi_tts_server.py & start_chatapi_tts_server.bat to where you install cosyvoice
-  prepare a audio and remane it as '2342.wav' to where you install cosyvoice
-  edit the tts setting in the mainwindow(ctrl+q, check left tab, page 3)


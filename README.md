# ChatWindowWithLLMApi
 
基于 PyQt5 的大型语言模型（LLM）聊天窗口，专为角色扮演交互和token消耗量优化，具备增强的长上下文记忆能力。  
代码是学习中写的，正在平屎山。
| 主界面 | 功能界面 |
| ---- | ---- |
| ![image](https://github.com/user-attachments/assets/de0f9941-ac15-4a04-8395-8657833c9d18) | ![image](https://github.com/user-attachments/assets/ae804710-bb81-4c3c-991e-ece9861da15e) |
| 主线创建 | 状态栏 |
| ![image](https://github.com/user-attachments/assets/8929c332-75f1-4f87-92ec-dcccfa347baf) | ![image](https://github.com/user-attachments/assets/1ed9c2d8-0eb3-4ef4-a130-9747c159b66f) |


## ✨ 功能特性
 
- **基于自迭代摘要的长上下文优化**  
  通过无感知的自迭代摘要，将过去的聊天内容总结后植入当前对话。使AI能获取对话截断点之前的记忆。  
  显著节省长篇角色扮演场景中的 token 消耗。  
  也可以用在对话超出模型上下文token限制的情况。  

- **模型库轮转**  
  支持自行指定数个模型，轮流回复当前对话，优化回复风格同质化问题。  

- **对话并发汇流**  
  支持同时向多个模型并发消息，通过预设工作流转化为单一回复。  
  工作流分为多层次，可利用各模型自身优势特性。  

- **对话用量分析**  
  预设了分析窗口，可以查看token使用量和对话字数。  

- **角色扮演状态栏**  
  内置角色状态栏，启用后将状态字段植入对话。状态可由用户、AI 或根据对话进程自动更新。  
 
- **主线剧情生成器**  
  由AI快速生成世界观和剧情线，支持自定义剧情。推荐使用轻量级 AI（免费/本地运行）进行节点更新，以最小化 API token 消耗。  
 
- **本地与在线模型支持**  
  支持来自 Ollama 的本地模型  
  支持兼容 Openai 标准的API  
  内置了deepseek、百度、硅基流动、腾讯的Openai兼容API支持  
 
- **基于对话的多模态生成**  
  支持在对话中同步生成聊天背景。支持自定义生成或自行指定背景。  
  *(生成功能需使用第三方图像生成API [Novita API](https://www.novita.ai/))*  
  *其他提供商 in plan*  
  *头像生成 in plan*

- **工具调用**  
  预设了文件调用，python解释器和系统时间工具。  
  推荐搭配pyautogui使用。  
 
## 🚀 安装
 
### 环境要求  
- Python 3.9+（低版本可能兼容，但未测试）  
- Novita API 密钥（非必要，仅用于图像生成）  
 
### 安装步骤  
- 安装python 3.9及以上的任意版本  
```bash
# 克隆仓库
git clone https://github.com/jkcltc/ChatWindowWithLLMApi.git
```
- 双击Chatapi 0.25.*.py，会过一遍库校验，弹出安装窗口时点击确定。  

### 启用语音合成（TTS）
#### cosyvoice2
- 将 chatapi_tts_server.py 和 start_chatapi_tts_server.bat 移动至 CosyVoice 安装目录
- 准备音频文件并重命名为 2342.wav，放置于 CosyVoice 安装目录
- 在主窗口中编辑 TTS 设置（Ctrl+Q 打开设置，左侧标签页第 3 页）

# ChatWindowWithLLMApi

A PYQT5-based LLM chat window optimized for role-playing interactions, with enhanced long-context memory capabilities.

## ✨ Features

- **Long-context Optimization**  
  By using self-iterative summarization,  
  After truncating 40+k of words of dialogue to 4-6k words(example) and sending them to the API, the AI can still retain memories from before the truncation point.  
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


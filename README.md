# ChatWindowWithLLMApi
 
基于 PyQt5 的大型语言模型聊天窗口，为角色扮演沉浸感和token消耗量优化，为长篇角色扮演提供记忆力增强方案。  

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
  - 背景  
    支持在对话中同步生成聊天背景。支持自定义生成或自行指定背景。  
    支持Novita,百度，硅基流动文生图  
  
  - 头像  
    支持自行指定或由AI基于当前对话生成头像
> 通用支持 in plan  

- **工具调用**  
  预设了文件调用，python解释器和系统时间工具。  
  推荐搭配pyautogui使用。  
 
## 🚀 安装
 
### 环境要求  
- Python 3.9+（低版本可能兼容，但未测试）  
- LLM Api 
- Text-to-Image API  （可选）
 
### 安装步骤  
- 安装python 3.9及以上的任意版本  
```bash
# 克隆仓库
git clone https://github.com/jkcltc/ChatWindowWithLLMApi.git
```
- 双击Chatapi 0.25.*.py，会过一遍库校验，弹出安装窗口时点击确定。  

### 语音合成（TTS）
#### cosyvoice2
- 将 chatapi_tts_server.py 和 start_chatapi_tts_server.bat 移动至 CosyVoice 安装目录
- 准备音频文件并重命名为 2342.wav，放置于 CosyVoice 安装目录
- 在主窗口中编辑 TTS 设置（Ctrl+Q 打开设置，左侧标签页第 3 页）

#### edge   
- 已支持  

#### sovits  
- in plan  

# ChatWindowWithLLMApi

A large-scale language model chat window based on PyQt5, optimized for role-playing immersion and token consumption, providing memory enhancement solutions for long form role-playing.   

## ✨ Features  

- **Long-Context Optimization via Self-Iterative Summarization**  
  Automatically summarizes past conversations and integrates them into the current dialogue without user awareness. Enables the AI to retain memories beyond dialogue truncation points.  
  Significantly saves tokens in long-form role-playing scenarios.  
  Also applicable when dialogues exceed the model's token limit.  

- **Model Library Rotation**  
  Supports custom specification of multiple models that take turns replying to conversations, mitigating homogenization of response styles.  

- **Convergence of Concurrent Dialogues**  
  Enables simultaneous messaging to multiple models, merging responses into a single reply through predefined workflows.  
  Workflows feature multi-tier structures that leverage each model’s specialized strengths.  

- **Dialogue Usage Analytics**  
  Includes a dedicated analytics window to display token consumption and conversation word count.  

- **Role-Playing Status Bar**  
  Built-in status bar embeds state fields into dialogues. States can be updated by users, the AI, or automatically based on dialogue progress.  

- **Main Plot Generator**  
  Rapidly generates worldviews and storylines via AI, supporting customized plots. Recommends lightweight AIs (free/local) for node updates to minimize API token consumption.  

- **Local & Online Model Support**  
  Supports local models via Ollama  
  Supports OpenAI-compatible APIs  
  Includes built-in compatibility with APIs from DeepSeek, Baidu, SiliconFlow, and Tencent  

- **Dialogue-Driven Multimodal Generation**  
  - **Backgrounds**  
    Synchronously generates chat backgrounds during conversations. Supports custom generation or manual background specification.  
    Integrates with Novita, Baidu, and SiliconFlow’s text-to-image generators.  
  
  - **Avatars**  
    Supports manual selection or AI-driven avatar generation based on dialogues  
    > *Universal support in planning phase*  

- **Tool Calls**  
  Preconfigured tools include file access, Python interpreters, and system time checks.  
  Recommended for use with `pyautogui`.  

## 🚀 Installation  

### Environment Requirements  
- Python 3.9+ (lower versions may work but untested)  
- LLM API  
- Text-to-Image API (optional)  

### Installation Steps  
- Install Python 3.9 or later  
```bash  
# Clone repository  
git clone https://github.com/jkcltc/ChatWindowWithLLMApi.git  
```  
- Double-click `Chatapi 0.25.*.py`. It will perform dependency verification – click "OK" when the installation popup appears.  

### Text-to-Speech (TTS)  
#### cosyvoice2  
- Move `chatapi_tts_server.py` and `start_chatapi_tts_server.bat` to the CosyVoice installation directory  
- Prepare an audio file named `2342.wav` and place it in the CosyVoice installation directory  
- Configure TTS settings in the main window (Press `Ctrl+Q` > Settings > Third tab on the left)  

#### Edge & Sovits  
- *In planning phase*  


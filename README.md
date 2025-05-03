# ChatWindowWithLLMApi

A PYQT5-based LLM chat window optimized for role-playing interactions, with enhanced long-context memory capabilities.

## ✨ Features

- **Long-context Optimization**  
  Maintains coherent character memory for role-playing chats up to ~40,000 Chinese characters

- **Multimodal Generation**  
  Supports automatic **text generation** and **image generation** during conversations  
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

## enable tts
-  move chatapi_tts_server.py & start_chatapi_tts_server.bat to where you install cosyvoice
-  prepare a audio and remane it as '2342.wav' to where you install cosyvoice
-  edit the tts setting in the mainwindow(ctrl+q, check left tab, page 3)


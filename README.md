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

## Enable tts
-  move chatapi_tts_server.py & start_chatapi_tts_server.bat to where you install cosyvoice
-  prepare a audio and remane it as '2342.wav' to where you install cosyvoice
-  edit the tts setting in the mainwindow(ctrl+q, check left tab, page 3)


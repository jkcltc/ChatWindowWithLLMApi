import sys
sys.path.append('third_party/Matcha-TTS')
from flask import Flask, request, jsonify
from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from cosyvoice.utils.file_utils import load_wav
import torchaudio
from pydub import AudioSegment
from pydub.playback import play
import threading
import queue
import time,os

app = Flask(__name__)

# 初始化语音合成模型
cosyvoice = CosyVoice2('pretrained_models/CosyVoice2-0.5B', load_jit=False, load_trt=False, fp16=False)
print('Model initialization finished')

save_path = 'tts_results/'

def play_sound(file):
    sound = AudioSegment.from_file(file, format="wav")
    sound.export("temp.mp3", format="mp3")
    sound = AudioSegment.from_file(r'temp.mp3', format="mp3")
    play(sound)

audio_queue = queue.Queue()

# 播放线程的函数
def audio_player_thread():
    while True:
        if not audio_queue.empty():
            audio_path = audio_queue.get()  # 从队列中获取音频文件路径
            play_sound(audio_path)  # 播放音频
            audio_queue.task_done()  # 标记队列任务完成
        else:
            time.sleep(0.1)  # 如果队列为空，稍作等待

# 启动播放线程
player_thread = threading.Thread(target=audio_player_thread, daemon=True)
player_thread.start()

@app.route('/tts', methods=['POST'])
def handle_tts_request():
    """处理TTS请求的HTTP端点"""
    try:
        data = request.json
        text = data.get('text', '')
        prompt = data.get('prompt', '博士，怎么了？啊，我没事，只是有点累。这两份档案一会儿麻烦你审核一下了，有许多新干员加入了罗德岛，我们可不能让他们失望。')
        function_type = data.get('function', 'zero-shot')
        audio=data.get('audio', '2342.wav')
        
        # 触发语音合成
        start_trans(text, prompt, function_type,audio)
        
        return jsonify({
            "status": "success",
            "message": "Request is being processed"
        }), 202
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def start_trans(text, prompt, function_type,audio='2342.wav'):
    """启动语音转换"""
    try:
        # 加载提示语音（根据实际情况调整路径）
        prompt_speech_16k = load_wav(audio, 16000)
        
        # 根据功能类型选择合成方式
        if function_type == 'zero-shot':
            generator = cosyvoice.inference_zero_shot(text, prompt, prompt_speech_16k, stream=False)
        elif function_type == 'cross_lingual':
            generator = cosyvoice.inference_cross_lingual(text, prompt_speech_16k, stream=False)
        elif function_type == 'instruct':
            generator = cosyvoice.inference_instruct2(text, prompt, prompt_speech_16k, stream=False)
        else:
            raise ValueError("Invalid function type")

        
        # 生成并保存音频
        for i, result in enumerate(generator):
            filename = os.path.join(save_path, get_useable_filename(text))
            torchaudio.save(filename, result['tts_speech'], cosyvoice.sample_rate)
            audio_queue.put(filename)

    except Exception as e:
        print(f"Error in speech synthesis: {e}")
        raise

def get_useable_filename(filename):
    """获取可用的文件名"""
    unsupported_chars = ["\n",'<', '>', ':', '"', '/', '\\', '|', '?', '*','{','}',',','.','，','。',' ','!','！']
    for char in unsupported_chars:
        filename = filename.replace(char, '')
    filename = filename.rstrip(' .')
    filename = filename[:10] if len(filename) > 10 else filename
    return f"{filename}_{int(time.time())}.wav"

if __name__ == '__main__':
    # 启动Flask服务
    app.run(host='127.0.0.1', port=5000, threaded=True)
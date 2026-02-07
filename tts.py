# tts.py
import os
from gtts import gTTS

def generate_audio(text, output_path="static/audio/output.mp3"):
    try:
        # Optimization: Check if file already exists to reuse it (caching)
        # Since the message is static, we don't need to call gTTS every time.
        if os.path.exists(output_path):
            print(f"⏩ Using cached TTS file: {output_path}")
            return output_path

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate audio using Google Text-to-Speech
        tts = gTTS(text=text, lang='en')
        tts.save(output_path)
        
        print(f"✅ TTS Generated: {output_path}")
        return output_path
    except Exception as e:
        print("❌ TTS Error:", e)
        return None

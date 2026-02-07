# transcribe.py — using FasterWhisper instead of ElevenLabs

import os
from werkzeug.utils import secure_filename
from faster_whisper import WhisperModel

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load the model once when the file is imported
model = WhisperModel("tiny", compute_type="auto")  # you can also use "small"

def transcribe_audio_file(audio_file):
    filename = secure_filename(audio_file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    audio_file.save(file_path)

    try:
        print("🔊 Transcribing with FasterWhisper:", file_path)
        segments, info = model.transcribe(file_path, beam_size=5, language="en")

        # Combine all segment texts
        transcription = " ".join(segment.text.strip() for segment in segments)
        print("✅ Transcription:", transcription)
        return transcription or "No text found"

    except Exception as e:
        print("❌ Error:", e)
        return "Transcription failed"

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            print("🧹 File cleaned up.")

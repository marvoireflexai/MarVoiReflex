"""Offline speech adapters: optional Moonshine, Silero VAD, Whisper fallback."""
import os,threading,unicodedata
from pathlib import Path
from app_paths import bundle_root

def normalized(text):
    return ''.join(c for c in text if unicodedata.category(c)[0] not in 'PZ').casefold()

def speech_present(audio):
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    if len(audio)<8000:return True
    return bool(get_speech_timestamps(audio,VadOptions(threshold=.40,min_speech_duration_ms=120,min_silence_duration_ms=350,speech_pad_ms=250)))

class MoonshineAdapter:
    def __init__(self):
        self.model=None;self.stream=None;self.key=None;self.seconds=0;self.lock=threading.RLock()
    def load(self):
        if self.model:return True
        path=Path(os.environ.get('MARVOI_MOONSHINE_DIR',str(bundle_root()/'assets/asr/moonshine-zh-tiny-streaming')))
        if not (path/'streaming_config.json').is_file():return False
        try:
            from moonshine_voice import Transcriber,ModelArch
            self.model=Transcriber(path,model_arch=ModelArch.TINY_STREAMING,options={'max_tokens_per_second':'13.0'})
            return True
        except Exception:return False
    @staticmethod
    def text(transcript):
        return ''.join(line.text for line in transcript.lines).strip()
    def reset(self):
        with self.lock:
            if self.stream:
                try:self.stream.close()
                except Exception:pass
            self.stream=None;self.key=None;self.seconds=0
    def partial(self,key,audio):
        with self.lock:
            if not self.load():return None
            if key!=self.key:
                self.reset();self.stream=self.model.create_stream(update_interval=.5);self.stream.start();self.key=key
            self.seconds+=len(audio)/16000
            if self.seconds>22:
                self.reset();raise ValueError('Audio stream limit exceeded')
            self.stream.add_audio(audio.tolist(),16000)
            return self.text(self.stream.update_transcription())
    def final(self,audio):
        with self.lock:
            self.reset()
            if not self.load():return None
            return self.text(self.model.transcribe_without_streaming(audio.tolist(),16000))
    def close(self):
        self.reset()
        with self.lock:
            if self.model:
                try:self.model.close()
                except Exception:pass
                self.model=None

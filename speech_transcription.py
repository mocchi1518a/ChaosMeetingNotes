from dotenv import load_dotenv
import logging, verboselogs
from time import sleep, strftime, localtime
from datetime import datetime
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)
import os
import threading

# 環境変数を読み込む
load_dotenv()
API_KEY = os.getenv("DG_API_KEY")

# グローバル変数
transcript_buffer = []
buffer_lock = threading.Lock()
file_counter = 0

# ログ保存ディレクトリの作成
start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_directory = os.path.join("logs", start_time)
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

def main():
    try:
        # Deepgramクライアントの設定
        deepgram = DeepgramClient(api_key=API_KEY)
        
        dg_connection = deepgram.listen.live.v("1")

        def on_message(self, result, **kwargs):
            global transcript_buffer
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            words = result.channel.alternatives[0].words
            if words:
                speaker_info = words[0].speaker if hasattr(words[0], 'speaker') else "unknown"
            else:
                speaker_info = "unknown"
            timestamp = strftime("%Y-%m-%d %H:%M:%S", localtime())
            with buffer_lock:
                transcript_buffer.append(f"{timestamp} Speaker {speaker_info}: {sentence}\n")
            print(f"{timestamp} Speaker {speaker_info}: {sentence}")

        def on_metadata(self, metadata, **kwargs):
            print(f"\n\n{metadata}\n\n")

        def on_speech_started(self, speech_started, **kwargs):
            print(f"\n\n{speech_started}\n\n")

        def on_utterance_end(self, utterance_end, **kwargs):
            print(f"\n\n{utterance_end}\n\n")

        def on_error(self, error, **kwargs):
            print(f"\n\n{error}\n\n")

        def write_buffer_to_file():
            global transcript_buffer, file_counter
            while True:
                sleep(20)  # 20秒ごとにバッファを書き込む
                with buffer_lock:
                    if transcript_buffer:
                        filename = os.path.join(log_directory, f"log_{file_counter:04d}.txt")
                        with open(filename, "a", encoding='utf-8') as log_file:
                            log_file.writelines(transcript_buffer)
                        file_counter += 1
                        transcript_buffer = []

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-2",
            punctuate=True,
            language="ja",
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            diarize=True
        )
        dg_connection.start(options)

        # バッファ書き込みスレッドを開始
        writer_thread = threading.Thread(target=write_buffer_to_file)
        writer_thread.daemon = True
        writer_thread.start()

        # マイクロフォンストリームをデフォルトの入力デバイスで開く
        microphone = Microphone(dg_connection.send)

        # マイクロフォンを開始
        microphone.start()

        # 録音が終了するまで待機
        input("Press Enter to stop recording...\n\n")

        # マイクロフォンが終了するまで待機
        microphone.finish()

        # 終了を示す
        dg_connection.finish()

        print("Finished")

    except Exception as e:
        print(f"Could not open socket: {e}")
        with open(os.path.join(log_directory, "transcription_log.txt"), "a", encoding='utf-8') as log_file:
            log_file.write(f"Could not open socket: {e}\n")

if __name__ == "__main__":
    main()

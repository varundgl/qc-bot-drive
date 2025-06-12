# # src/preprocessing/transcript_generator.py
# import azure.cognitiveservices.speech as speechsdk
# import json
# import re
# import time
# import logging

# logger = logging.getLogger(__name__)

# class TranscriptGenerator:
#     def __init__(self, speech_key: str, speech_region: str):
#         self.speech_config = speechsdk.SpeechConfig(
#             subscription=speech_key,
#             region=speech_region
#         )
#         self.speech_config.request_word_level_timestamps = True
#         self.speech_config.output_format = speechsdk.OutputFormat.Detailed

#     def transcribe_audio(self, audio_file_path: str, output_text_file: str):
#         audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
#         speech_recognizer = speechsdk.SpeechRecognizer(
#             speech_config=self.speech_config, 
#             audio_config=audio_config
#         )

#         all_results = []
#         done = False

#         def handle_final_result(evt):
#             if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
#                 result_json = json.loads(evt.result.json)
#                 if 'NBest' in result_json and result_json['NBest']:
#                     words = result_json['NBest'][0].get('Words', [])
#                     all_results.extend(words)

#         def stop_cb(evt):
#             nonlocal done
#             done = True

#         speech_recognizer.recognized.connect(handle_final_result)
#         speech_recognizer.session_stopped.connect(stop_cb)
#         speech_recognizer.canceled.connect(stop_cb)

#         speech_recognizer.start_continuous_recognition()
#         start_time = time.time()
#         while not done and time.time() - start_time < 1800:  # 30 min timeout
#             time.sleep(0.5)
#         speech_recognizer.stop_continuous_recognition()

#         # Process and save results
#         with open(output_text_file, "w", encoding="utf-8") as f:
#             f.write("start_time\tend_time\tspeaker\ttranscript\n")
#             current_sentence = []
#             current_start = None
#             current_end = None

#             for word in all_results:
#                 word_start = word['Offset'] / 10000000
#                 word_end = word_start + (word['Duration'] / 10000000)
#                 word_text = word['Word']

#                 if not current_sentence:
#                     current_start = word_start
#                     current_end = word_end
#                     current_sentence.append(word_text)
#                     continue

#                 # Sentence boundary detection
#                 time_gap = word_start - current_end
#                 is_punctuation = re.match(r'^[.!?]+$', word_text)

#                 if time_gap > 1.5 or is_punctuation:
#                     sentence_text = " ".join(current_sentence)
#                     f.write(f"{current_start:.2f}\t{current_end:.2f}\tSPEAKER\t{sentence_text}\n")
#                     current_sentence = [word_text]
#                     current_start = word_start
#                     current_end = word_end
#                 else:
#                     current_sentence.append(word_text)
#                     current_end = word_end

#             if current_sentence:
#                 sentence_text = " ".join(current_sentence)
#                 f.write(f"{current_start:.2f}\t{current_end:.2f}\tSPEAKER\t{sentence_text}\n")

#         logger.info(f"Transcript saved to {output_text_file}")
#         return len(all_results) > 0


import time
import re
import os
from faster_whisper import WhisperModel

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class TranscriptGenerator:
    def __init__(self, model_size="base.en", compute_type="int8"):
        start_load = time.time()
        self.model = WhisperModel(model_size, compute_type=compute_type)
        self.model_load_time = time.time() - start_load

    def transcribe_audio(self, audio_file_path: str, output_text_file: str):
        print(os.path.abspath(audio_file_path))
        start_transcribe = time.time()
        segments, info = self.model.transcribe(audio_file_path, word_timestamps=True, beam_size=5)
        transcription_time = time.time() - start_transcribe

        all_words = []
        for segment in segments:
            if segment.words:
                all_words.extend(segment.words)

        with open(output_text_file, "w", encoding="utf-8") as f:
            f.write("start_time\tend_time\tspeaker\ttranscript\n")

            current_sentence = []
            current_start = None
            current_end = None

            for word in all_words:
                word_start = word.start
                word_end = word.end
                word_text = word.word.strip()

                if not current_sentence:
                    current_sentence.append(word_text)
                    current_start = word_start
                    current_end = word_end
                    continue

                # Check sentence boundary
                time_gap = word_start - current_end
                is_punctuation = re.match(r'^[.!?]+$', word_text)

                if time_gap > 1.5 or is_punctuation:
                    sentence = " ".join(current_sentence)
                    f.write(f"{current_start:.2f}\t{current_end:.2f}\tSPEAKER\t{sentence}\n")
                    current_sentence = [word_text]
                    current_start = word_start
                    current_end = word_end
                else:
                    current_sentence.append(word_text)
                    current_end = word_end

            if current_sentence:
                sentence = " ".join(current_sentence)
                f.write(f"{current_start:.2f}\t{current_end:.2f}\tSPEAKER\t{sentence}\n")

        file_written = os.path.exists(output_text_file) and os.path.getsize(output_text_file) > 100  # >100 bytes means not just header

        if not all_words:
            print("⚠️ No words recognized by the model.")
        if file_written:
            print(f"✅ Transcript saved to {output_text_file}")
        else:
            print(f"❌ Transcript file is empty or only contains header: {output_text_file}")

        return file_written


# if __name__ == "__main__":
#     tg = TranscriptGenerator()
#     audio_path = r"../../audios/Conditional Formatting for Automation Friday_ 1 December_ 2023 at 11_58_47 AM_2522_SV.wav"
#     print("Looking for:", os.path.abspath(audio_path))
#     success = tg.transcribe_audio(audio_path, "output_transcript.tsv")
#     print("✅ Transcription complete!" if success else "❌ No transcription produced.")

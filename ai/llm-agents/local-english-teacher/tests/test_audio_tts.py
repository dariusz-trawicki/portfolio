import wave

import numpy as np

from english_teacher.audio import chunk_audio, float_to_int16, to_whisper_input
from english_teacher.tts import read_wav_int16_mono, resolve_backend


def test_to_whisper_input_resamples_and_downmixes():
    # FastRTC delivers int16 shaped (1, n) at 48 kHz
    audio = (np.ones((1, 48000)) * 16384).astype(np.int16)
    x = to_whisper_input(48000, audio)
    assert x.dtype == np.float32
    assert x.ndim == 1
    assert x.shape[0] == 16000
    assert abs(float(np.median(x)) - 0.5) < 0.01


def test_to_whisper_input_stereo():
    audio = np.stack([np.ones(16000), -np.ones(16000)]).astype(np.float32)
    x = to_whisper_input(16000, audio)
    assert x.shape == (16000,)
    assert np.allclose(x, 0.0)


def test_chunk_audio_covers_everything():
    audio = np.arange(25000, dtype=np.int16)
    chunks = list(chunk_audio(10000, audio, chunk_seconds=1.0))
    assert [c.shape[0] for _, c in chunks] == [10000, 10000, 5000]
    assert np.array_equal(np.concatenate([c for _, c in chunks]), audio)


def test_float_to_int16_clips():
    out = float_to_int16(np.array([-2.0, 0.0, 2.0]))
    assert out.tolist() == [-32767, 0, 32767]


def test_read_wav_int16_mono(tmp_path):
    path = tmp_path / "t.wav"
    stereo = np.array([[100, 300], [-100, -300]], dtype=np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(stereo.tobytes())
    sr, samples = read_wav_int16_mono(path)
    assert sr == 22050
    assert samples.tolist() == [200, -200]


def test_resolve_backend():
    assert resolve_backend("auto", system="Darwin") == "say"
    assert resolve_backend("auto", system="Linux") == "piper"
    assert resolve_backend("piper", system="Darwin") == "piper"

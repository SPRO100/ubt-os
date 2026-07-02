"""Тесты чистой логики stock_video_pipeline (без сети и ffmpeg)."""
from ubt_os.pipelines.stock_video import pick_video_files, fallback_keywords
from ubt_os.agents.tts_agent import provider_chain, edge_voice_for


def _pexels(videos):
    return {"videos": videos}


def _file(link, w, h, ftype="video/mp4"):
    return {"link": link, "width": w, "height": h, "file_type": ftype}


def test_pick_video_files_prefers_vertical_mp4():
    resp = _pexels([
        {"video_files": [_file("horiz.mp4", 1920, 1080)]},           # горизонталь — мимо
        {"video_files": [_file("vert_hd.mp4", 1080, 1920),
                         _file("vert_4k.mp4", 2160, 3840)]},          # берём меньший
        {"video_files": [_file("vert2.mp4", 720, 1280)]},
    ])
    urls = pick_video_files(resp, max_clips=5)
    assert urls == ["vert_hd.mp4", "vert2.mp4"]


def test_pick_video_files_respects_limit():
    resp = _pexels([{"video_files": [_file(f"v{i}.mp4", 1080, 1920)]} for i in range(6)])
    assert len(pick_video_files(resp, max_clips=3)) == 3


def test_pick_video_files_skips_low_res_and_non_mp4():
    resp = _pexels([
        {"video_files": [_file("tiny.mp4", 480, 854)]},               # < 960 по высоте
        {"video_files": [_file("stream.m3u8", 1080, 1920, "hls")]},   # не mp4
    ])
    assert pick_video_files(resp, max_clips=5) == []


def test_fallback_keywords_known_and_unknown_vertical():
    assert fallback_keywords("betting") != fallback_keywords("nutra")
    assert fallback_keywords("unknown") == fallback_keywords("nutra")


# ── A35: цепочка провайдеров и выбор голоса edge ──────────

def test_provider_chain_edge_always_present():
    assert provider_chain(None, None) == ["edge"]
    assert provider_chain("http://tts", None) == ["local", "edge"]
    assert provider_chain(None, "key") == ["edge", "elevenlabs"]
    assert provider_chain("http://tts", "key") == ["local", "edge", "elevenlabs"]


def test_edge_voice_detects_language(monkeypatch):
    monkeypatch.delenv("EDGE_TTS_VOICE_RU", raising=False)
    monkeypatch.delenv("EDGE_TTS_VOICE_EN", raising=False)
    assert edge_voice_for("Привет, мир").startswith("ru-RU")
    assert edge_voice_for("Hello world").startswith("en-US")
    # явный edge-голос уважается
    assert edge_voice_for("Привет", "en-GB-SoniaNeural") == "en-GB-SoniaNeural"

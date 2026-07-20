"""Testes do cliente MiniMax Music (sem chamadas de rede reais)."""

import json
from unittest import mock

import pytest

from minimax_music.api import (
    MiniMaxMusicClient,
    MusicAPIError,
    MusicRequest,
)


def _ok_response_hex(audio_hex: str = "deadbeef") -> mock.Mock:
    # Schema atual: data.audio aninhado
    body = {
        "data": {"audio": audio_hex, "status": 2},
        "trace_id": "abc",
        "extra_info": {
            "music_duration": 30000,
            "music_sample_rate": 44100,
            "music_channel": 2,
            "bitrate": 256000,
            "music_size": 4,
        },
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def _ok_response_legacy(audio_hex: str = "deadbeef") -> mock.Mock:
    # Schema legado: audio no top-level
    body = {
        "base_resp": {"status_code": 0, "status_msg": "success"},
        "audio": audio_hex,
        "extra_info": {"music_size": 4},
    }
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def _err_response(status: int, msg: str) -> mock.Mock:
    body = {"base_resp": {"status_code": 1004, "status_msg": msg}}
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def test_generate_returns_audio_bytes():
    client = MiniMaxMusicClient(
        base_url="https://api.minimax.io",
        endpoint="/v1/music_generation",
        api_key="sk-test",
    )
    req = MusicRequest(
        prompt="Test pop",
        lyrics="[Verse]\nhello",
    )
    with mock.patch("minimax_music.api.requests.post",
                    return_value=_ok_response_hex("deadbeef")) as m:
        result = client.generate(req)

    # Payload enviado
    args, kwargs = m.call_args
    assert args[0] == "https://api.minimax.io/v1/music_generation"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
    body = kwargs["json"]
    assert body["model"] == "music-3.0"
    assert body["prompt"] == "Test pop"
    assert body["lyrics"] == "[Verse]\nhello"
    assert body["audio_format"] == "mp3"
    # Resultado
    assert result.audio_bytes == b"\xde\xad\xbe\xef"
    assert result.audio_format == "mp3"
    assert result.sample_rate == 44100


def test_missing_api_key_raises():
    client = MiniMaxMusicClient(
        base_url="https://api.minimax.io",
        endpoint="/v1/music_generation",
        api_key="",
    )
    req = MusicRequest(prompt="x", lyrics_optimizer=True)
    with pytest.raises(MusicAPIError):
        client.generate(req)


def test_user_lyrics_required_when_optimizer_off():
    req = MusicRequest(prompt="x", lyrics="", lyrics_optimizer=False)
    with pytest.raises(MusicAPIError):
        req.to_payload()


def test_instrumental_payload_drops_lyrics():
    req = MusicRequest(prompt="x", is_instrumental=True)
    p = req.to_payload()
    assert p["is_instrumental"] is True
    assert "lyrics" not in p
    assert "lyrics_optimizer" not in p


def test_http_error_raises_with_message():
    client = MiniMaxMusicClient(
        base_url="https://api.minimax.io",
        endpoint="/v1/music_generation",
        api_key="sk-test",
    )
    req = MusicRequest(prompt="x", lyrics_optimizer=True)
    with mock.patch("minimax_music.api.requests.post",
                    return_value=_err_response(401, "invalid key")):
        with pytest.raises(MusicAPIError) as exc:
            client.generate(req)
    assert "401" in str(exc.value)
    assert "invalid key" in str(exc.value)


def test_legacy_top_level_audio_still_works():
    """Compat: resposta no schema antigo (audio no top-level)."""
    client = MiniMaxMusicClient(
        base_url="https://api.minimax.io",
        endpoint="/v1/music_generation",
        api_key="sk-test",
    )
    req = MusicRequest(prompt="x", lyrics_optimizer=True)
    with mock.patch("minimax_music.api.requests.post",
                    return_value=_ok_response_legacy("cafebabe")):
        result = client.generate(req)
    assert result.audio_bytes == b"\xca\xfe\xba\xbe"

"""Testes do cliente de letras (MiniMax-M3)."""

import json
from unittest import mock

import pytest

from minimax_music.lyrics_client import (
    generate_duet_lyrics,
    LyricsAPIError,
    MiniMaxChatClient,
    _user_prompt_for_duet,
)


def _ok_chat_response(content: str = "letra aqui") -> mock.Mock:
    body = {
        "id": "abc",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}}
        ],
    }
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def test_chat_returns_string():
    client = MiniMaxChatClient(
        chat_url="https://api.minimax.io/v1/chat/completions",
        api_key="sk-test",
        model="MiniMax-M3",
    )
    with mock.patch("minimax_music.lyrics_client.requests.post",
                    return_value=_ok_chat_response("olá")) as m:
        out = client.chat(messages=[{"role": "user", "content": "oi"}])
    assert out == "olá"
    # Garante que o client envia reasoning_split=True
    _, kwargs = m.call_args
    assert kwargs["json"].get("reasoning_split") is True


def test_chat_missing_api_key_raises():
    client = MiniMaxChatClient(chat_url="x", api_key="", model="MiniMax-M3")
    with pytest.raises(LyricsAPIError):
        client.chat(messages=[{"role": "user", "content": "oi"}])


def test_chat_http_error_raises():
    r = mock.Mock()
    r.status_code = 401
    r.text = "unauthorized"
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    with mock.patch("minimax_music.lyrics_client.requests.post", return_value=r):
        with pytest.raises(LyricsAPIError) as exc:
            client.chat(messages=[{"role": "user", "content": "x"}])
    assert "401" in str(exc.value)


def test_chat_invalid_payload_raises():
    r = mock.Mock()
    r.status_code = 200
    r.json.return_value = {"choices": []}  # vazio
    r.text = "{}"
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    with mock.patch("minimax_music.lyrics_client.requests.post", return_value=r):
        with pytest.raises(LyricsAPIError):
            client.chat(messages=[{"role": "user", "content": "x"}])


def test_user_prompt_includes_duet_structure():
    p = _user_prompt_for_duet(
        "Sertanejo universitário", "Homem e mulher", "Jovens",
        "primeiro amor no interior",
    )
    assert "Sertanejo universitário" in p
    assert "Homem e mulher" in p
    assert "Jovens" in p
    assert "primeiro amor no interior" in p
    assert "[Verse]" in p
    assert "[Chorus]" in p
    assert "[Bridge]" in p
    # NOVA SINTAXE: nomes de cantores
    assert "Ana:" in p
    assert "Pedro:" in p
    assert "Ana e Pedro" in p
    # Cada linha deve começar com o nome
    p_low = p.lower()
    assert "linha" in p_low
    assert "prefixo" in p_low or "prefixada" in p_low
    # Pede pro M3 não colocar o nome no MEIO da linha
    assert "nao" in p_low or "não" in p
    assert "meio" in p_low


def test_generate_duet_lyrics_calls_chat():
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    fake = "[Verse]\nola\n\n[Chorus]\nai"
    with mock.patch("minimax_music.lyrics_client.requests.post",
                    return_value=_ok_chat_response(fake)):
        out = generate_duet_lyrics(
            client, "Sertanejo universitário", "Homem e mulher", "Jovens",
            "primeiro amor",
        )
    assert "[Verse]" in out
    assert "[Chorus]" in out


def test_generate_duet_lyrics_requires_theme():
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    with pytest.raises(LyricsAPIError):
        generate_duet_lyrics(client, "Pop", "Homem e mulher", "Jovens", "  ")


# --- Metadados do YouTube ---

def test_user_prompt_for_youtube_metadata_includes_contexto():
    from minimax_music.prompts import build_youtube_metadata_prompt
    p = build_youtube_metadata_prompt(
        "Sertanejo universitário", True, "Homem e mulher", "Jovens",
        "primeiro amor no interior",
    )
    assert "Sertanejo universitário" in p
    assert "Homem e mulher" in p
    assert "Jovens" in p or "jovens" in p
    assert "primeiro amor" in p
    # Regras
    p_low = p.lower()
    assert "titulo" in p_low
    assert "descricao" in p_low
    assert "tags" in p_low
    assert "json" in p_low


def test_user_prompt_for_youtube_metadata_with_lyrics_excerpt():
    from minimax_music.prompts import build_youtube_metadata_prompt
    lyrics = (
        "[Verse]\n"
        "Era uma vez numa cidade pequena\n"
        "A chuva de verao chegou\n"
        "Voce apareceu\n"
        "E mudou meu coracao\n"
        "[Chorus]\n"
        "Esse amor chegou\n"
        "Pra sempre"
    )
    p = build_youtube_metadata_prompt(
        "Pop", False, "", "", "amor de verao", lyrics=lyrics,
    )
    # Trecho da letra aparece no prompt
    assert "cidade pequena" in p
    assert "Esse amor chegou" in p


def test_extract_json_directo():
    from minimax_music.lyrics_client import _extract_json
    out = _extract_json('{"title": "ola", "description": "mundo", "tags": ["a", "b"]}')
    assert out["title"] == "ola"
    assert out["tags"] == ["a", "b"]


def test_extract_json_com_lixo_em_volta():
    from minimax_music.lyrics_client import _extract_json
    raw = (
        "Aqui vai o JSON:\n"
        '{"title": "ola", "description": "mundo", "tags": ["a", "b"]}\n'
        "Fim."
    )
    out = _extract_json(raw)
    assert out["title"] == "ola"


def test_extract_json_vazio_levanta():
    from minimax_music.lyrics_client import _extract_json
    with pytest.raises(Exception):
        _extract_json("")


def test_generate_youtube_metadata_sucesso():
    from minimax_music.lyrics_client import generate_youtube_metadata
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    body = {
        "id": "x",
        "choices": [{"message": {"role": "assistant", "content":
            '{"title": "Chuva de Verao", "description": "musica sertaneja", "tags": ["sertanejo", "novo"]}'
        }}],
    }
    r = mock.Mock(status_code=200)
    r.json.return_value = body
    r.text = json.dumps(body)
    with mock.patch("minimax_music.lyrics_client.requests.post", return_value=r):
        data = generate_youtube_metadata(
            client, "Sertanejo universitario", False, "", "", "chuva de verao",
        )
    assert data["title"] == "Chuva de Verao"
    assert "sertaneja" in data["description"]
    assert data["tags"] == ["sertanejo", "novo"]


def test_generate_youtube_metadata_falha_json_invalido():
    from minimax_music.lyrics_client import generate_youtube_metadata
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    body = {
        "id": "x",
        "choices": [{"message": {"role": "assistant", "content": "isso nao e json"}}],
    }
    r = mock.Mock(status_code=200)
    r.json.return_value = body
    r.text = json.dumps(body)
    with mock.patch("minimax_music.lyrics_client.requests.post", return_value=r):
        with pytest.raises(LyricsAPIError):
            generate_youtube_metadata(
                client, "Sertanejo", False, "", "", "x",
            )


def test_strip_think_blocks_removes_reasoning():
    from minimax_music.lyrics_client import _strip_think_blocks
    raw = "<think>\nPensando aqui...\n</think>\n\n[Verse]\nola"
    assert _strip_think_blocks(raw) == "[Verse]\nola"
    # Sem bloco: devolve igual
    assert _strip_think_blocks("[Verse]\nola") == "[Verse]\nola"
    # Com várias tags
    raw2 = "<think>...</think>[Verse]\n1\n<think>outro</think>\n\n[Chorus]\n2"
    assert "[Verse]" in _strip_think_blocks(raw2)
    assert "[Chorus]" in _strip_think_blocks(raw2)
    assert "<think>" not in _strip_think_blocks(raw2)


def test_chat_strips_think_blocks_in_response():
    """M3 devolve <think>...</think> antes da letra; o cliente deve remover."""
    raw = "<think>\nPensando...\n</think>\n\n[Verse]\nola"
    client = MiniMaxChatClient(chat_url="x", api_key="sk", model="M3")
    with mock.patch("minimax_music.lyrics_client.requests.post",
                    return_value=_ok_chat_response(raw)):
        out = client.chat(messages=[{"role": "user", "content": "x"}])
    assert "<think>" not in out
    assert "[Verse]" in out

"""Cliente HTTP para o endpoint `music_generation` do Mavis.

Endpoint oficial (plano global / Token Plan): POST {base}/v1/music_generation
Documentação: https://platform.minimax.io/docs/api-reference/music-generation

Modelo recomendado: music-3.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

import requests

AudioFormat = Literal["mp3", "wav", "pcm"]
SampleRate = Literal[16000, 24000, 32000, 44100]
Bitrate = Literal[32000, 64000, 128000, 256000]


class MusicAPIError(Exception):
    """Erro genérico da API do Mavis."""


@dataclass
class MusicRequest:
    """Parâmetros de uma requisição de geração de música."""

    prompt: str
    lyrics: str = ""                 # vazio se lyrics_optimizer=True ou instrumental
    lyrics_optimizer: bool = False   # se True, a API gera a letra a partir do prompt
    is_instrumental: bool = False
    model: str = "music-3.0"
    sample_rate: SampleRate = 44100
    bitrate: Bitrate = 256000
    audio_format: AudioFormat = "mp3"
    stream: bool = False             # se True, response é hex chunked

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": self.prompt,
            "lyrics": self.lyrics or "",
            "lyrics_optimizer": self.lyrics_optimizer,
            "is_instrumental": self.is_instrumental,
            "sample_rate": self.sample_rate,
            "bitrate": self.bitrate,
            "audio_format": self.audio_format,
            "stream": self.stream,
        }
        # Remove campos irrelevantes para reduzir ruído
        if self.is_instrumental:
            payload.pop("lyrics", None)
            payload.pop("lyrics_optimizer", None)
        if self.is_instrumental and not self.prompt:
            raise MusicAPIError("Para gerar instrumental é necessário 'prompt'.")
        if (not self.is_instrumental
                and not self.lyrics_optimizer
                and not self.lyrics):
            raise MusicAPIError(
                "É necessário fornecer 'lyrics' ou ativar 'lyrics_optimizer'."
            )
        return payload


@dataclass
class MusicResult:
    """Resultado da geração: bytes do áudio + metadados."""

    audio_bytes: bytes
    audio_format: str
    duration_ms: int | None
    sample_rate: int | None
    channels: int | None
    bitrate: int | None
    size_bytes: int | None


class MiniMaxMusicClient:
    """Cliente da API Music do Mavis (api.minimax.io)."""

    def __init__(self, base_url: str, endpoint: str, api_key: str, timeout: int = 240):
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.api_key = api_key
        self.timeout = timeout

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.endpoint}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(self, req: MusicRequest) -> MusicResult:
        """Envia a requisição e devolve os bytes do áudio + metadados.

        Lança `MusicAPIError` em caso de erro HTTP ou payload inválido.
        """
        if not self.api_key:
            raise MusicAPIError(
                "API key não configurada. Defina MINIMAX_API_KEY no .env."
            )

        payload = req.to_payload()
        try:
            resp = requests.post(
                self.url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise MusicAPIError(f"Falha de rede ao chamar a API: {e}") from e

        if resp.status_code >= 400:
            # Tentar extrair mensagem útil do corpo
            detail = resp.text
            try:
                err_json = resp.json()
                detail = (
                    err_json.get("base_resp", {}).get("status_msg")
                    or err_json.get("message")
                    or err_json.get("error")
                    or detail
                )
            except Exception:
                pass
            raise MusicAPIError(
                f"API retornou HTTP {resp.status_code}: {detail}"
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise MusicAPIError(f"Resposta não-JSON da API: {e}") from e

        return self._parse_response(data)

    # ----------------- Parsing da resposta -----------------

    def _parse_response(self, data: dict[str, Any]) -> MusicResult:
        # Validação de status
        base_resp = data.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        if status_code is not None and status_code != 0:
            raise MusicAPIError(
                f"API erro (status_code={status_code}): "
                f"{base_resp.get('status_msg') or 'desconhecido'}"
            )

        # A API pode devolver:
        #   - {"data": {"audio": "<hex>", "status": ...}, "extra_info": {...}, ...}  (atual)
        #   - {"audio": "<hex>", "extra_info": {...}, ...}                            (legado)
        #   - {"audio_url": "https://...", ...}                                       (com output_format=url)
        inner = data.get("data") or {}
        if isinstance(inner, dict):
            audio_url = (
                inner.get("audio_url")
                or inner.get("music_url")
                or data.get("audio_url")
                or data.get("music_url")
            )
            audio_hex = (
                inner.get("audio")
                or inner.get("audio_hex")
                or data.get("audio")
                or data.get("audio_hex")
            )
        else:
            audio_url = data.get("audio_url") or data.get("music_url")
            audio_hex = data.get("audio") or data.get("audio_hex")

        if audio_url and not audio_hex:
            # Baixa o áudio a partir da URL
            try:
                rr = requests.get(audio_url, timeout=self.timeout)
                rr.raise_for_status()
                audio_bytes = rr.content
            except requests.RequestException as e:
                raise MusicAPIError(
                    f"Falha ao baixar áudio da URL retornada: {e}"
                ) from e
        elif audio_hex:
            try:
                audio_bytes = bytes.fromhex(audio_hex)
            except ValueError as e:
                raise MusicAPIError(f"hex de áudio inválido: {e}") from e
        else:
            raise MusicAPIError(
                "Resposta sem 'audio'/'audio_hex' nem 'audio_url'."
            )

        # extra_info pode estar no top-level ou dentro de data
        extra = data.get("extra_info") or {}
        if not extra and isinstance(inner, dict):
            extra = inner.get("extra_info") or {}

        return MusicResult(
            audio_bytes=audio_bytes,
            audio_format=str(extra.get("music_format") or "mp3"),
            duration_ms=extra.get("music_duration"),
            sample_rate=extra.get("music_sample_rate"),
            channels=extra.get("music_channel"),
            bitrate=extra.get("bitrate"),
            size_bytes=extra.get("music_size") or len(audio_bytes),
        )

"""Worker que faz a chamada à API Music em thread separada.

A UI wxPython precisa permanecer responsiva — chamadas HTTP podem levar
vários minutos para gerar uma música. Usamos um thread + wx.CallAfter para
devolver o resultado à thread de UI.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import wx

from .api import MiniMaxMusicClient, MusicAPIError, MusicRequest, MusicResult
from .config import AppSettings
from .lyrics_client import (
    generate_clean_duet_lyrics,
    generate_duet_lyrics,
    LyricsAPIError,
    MiniMaxChatClient,
)
from .prompts import (
    build_prompt_and_lyrics,
    GenerationInput,
    voice_direction,
    _has_structure_tags,
)


@dataclass
class WorkerResult:
    ok: bool
    saved_path: Optional[Path]
    error: Optional[str]
    result: Optional[MusicResult]
    generated_lyrics: Optional[str] = None  # caso o M3 tenha gerado a letra


class GenerationWorker:
    """Dispara uma geração de música em background.

    Para duetos com letra automática, opcionalmente consulta o MiniMax-M3
    (chat completion) para gerar a letra roteirada ANTES de chamar o
    music-3.0. Isso resolve o problema do music-3.0 não respeitar bem
    a alternância de vozes em duetos.
    """

    def __init__(
        self,
        client: MiniMaxMusicClient,
        settings: AppSettings,
        gen_input: GenerationInput,
        request: MusicRequest,
        output_dir: Path,
        filename: str,
        use_m3_for_lyrics: bool = True,
        use_clean_lyrics: bool = True,
    ):
        """use_clean_lyrics: para duetos, gerar letra SEM prefixos
        (sweet spot do music-2.6). Se False, usa prefixos (F:/M:/Ana:/Pedro:)."""
        self._client = client
        self._settings = settings
        self._gen_input = gen_input
        self._request = request
        self._output_dir = output_dir
        self._filename = filename
        self._use_m3_for_lyrics = use_m3_for_lyrics
        self._use_clean_lyrics = use_clean_lyrics

    # ----------------- Execução -----------------

    def start(self, on_done) -> None:
        """Inicia o trabalho. `on_done` será chamado na thread da UI."""
        self._on_done = on_done
        import threading
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        generated_lyrics: Optional[str] = None

        # Plano B para duetos: gerar letra roteirada via M3 antes do music-3.0
        if (
            self._use_m3_for_lyrics
            and self._gen_input.duet_enabled
            and self._gen_input.lyrics_mode == "auto"
            and self._gen_input.lyrics_prompt.strip()
        ):
            print(f"[worker] use_m3_for_lyrics={self._use_m3_for_lyrics} duet={self._gen_input.duet_enabled} "
                  f"mode={self._gen_input.lyrics_mode!r} theme={self._gen_input.lyrics_prompt[:40]!r}...",
                  flush=True)
            try:
                chat = MiniMaxChatClient(
                    chat_url=self._settings.chat_url,
                    api_key=self._settings.api_key,
                    model=self._settings.text_model,
                    timeout=120,
                )
                if self._use_clean_lyrics:
                    # Sweet spot: letra SEM prefixos (music-2.6 respeita
                    # a alternância via tags + voice_direction_clean)
                    generated_lyrics = generate_clean_duet_lyrics(
                        client=chat,
                        style=self._gen_input.style,
                        gender=self._gen_input.duet_gender,
                        age=self._gen_input.duet_age,
                        theme=self._gen_input.lyrics_prompt,
                    )
                else:
                    # Compatibilidade: letra COM prefixos (F:/M:/Ana:/Pedro:)
                    generated_lyrics = generate_duet_lyrics(
                        client=chat,
                        style=self._gen_input.style,
                        gender=self._gen_input.duet_gender,
                        age=self._gen_input.duet_age,
                        theme=self._gen_input.lyrics_prompt,
                    )
                print(f"[worker] M3 gerou {len(generated_lyrics)} chars", flush=True)
            except LyricsAPIError as e:
                self._finish(WorkerResult(
                    False, None, f"Falha ao gerar letra com M3: {e}", None,
                ))
                return
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc(limit=3)
                self._finish(WorkerResult(
                    False, None, f"Erro inesperado no M3: {e}\n{tb}", None,
                ))
                return

            # Re-monta o prompt incluindo a "Voice direction" (a letra
            # agora tem tags [Verse]/[Chorus]/[Bridge]).
            try:
                prompt, _, _, _ = build_prompt_and_lyrics(
                    self._gen_input,
                    override_lyrics=generated_lyrics,
                )
            except ValueError as e:
                self._finish(WorkerResult(False, None, str(e), None))
                return
            self._request = MusicRequest(
                prompt=prompt,
                lyrics=generated_lyrics,
                lyrics_optimizer=False,  # letra já está pronta
                is_instrumental=self._request.is_instrumental,
                model=self._request.model,
            )
            print(f"[worker] request reescrito: lyrics={len(generated_lyrics)} chars, optimizer=False",
                  flush=True)

        # Gera a música
        try:
            result = self._client.generate(self._request)
        except MusicAPIError as e:
            self._finish(WorkerResult(False, None, str(e), None, generated_lyrics))
            return
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc(limit=3)
            self._finish(WorkerResult(
                False, None, f"{e}\n{tb}", None, generated_lyrics,
            ))
            return

        # Salva em disco
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            out_path = self._output_dir / self._filename
            out_path.write_bytes(result.audio_bytes)
        except OSError as e:
            self._finish(WorkerResult(
                False, None, f"Falha ao salvar: {e}", result, generated_lyrics,
            ))
            return

        self._finish(WorkerResult(True, out_path, None, result, generated_lyrics))

    def _finish(self, res: WorkerResult) -> None:
        # Volta para a thread da UI
        wx.CallAfter(self._on_done, res)

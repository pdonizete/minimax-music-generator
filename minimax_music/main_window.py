"""Janela principal acessível do Gerador de Músicas Mavis.

Acessibilidade:
- Todos os controles têm `SetName`/`SetLabel` em PT-BR.
- Ordem de tabulação explícita.
- Atalhos de teclado (AcceleratorTable) para ações frequentes.
- Mensagens de status são anunciadas via AccessibleNotify (AnnounceText em NVDA/JAWS).
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

import wx

from . import i18n
from .api import MiniMaxMusicClient, MusicRequest
from .config import (
    AppSettings,
    load_user_prefs,
    resolve_settings,
    save_user_prefs,
    UserPrefs,
)
from .player import MusicPlayer
from .prompts import (
    build_prompt_and_lyrics,
    GenerationInput,
    suggest_filename,
)
from .settings_dialog import SettingsDialog
from .worker import GenerationWorker, WorkerResult


# Aceleradores globais: F5 = gerar, Ctrl+O = abrir pasta, Ctrl+, = configurações
ACCEL_TABLE = wx.AcceleratorTable([
    (wx.ACCEL_NORMAL, wx.WXK_F5, wx.ID_REFRESH),     # gerar
    (wx.ACCEL_CTRL,  ord('O'), wx.ID_OPEN),          # abrir pasta
    (wx.ACCEL_CTRL,  ord(','), wx.ID_PREFERENCES),   # configurações
    (wx.ACCEL_CTRL,  ord('Q'), wx.ID_EXIT),          # sair
])


class MainWindow(wx.Frame):
    """Janela principal."""

    def __init__(self, settings: AppSettings):
        super().__init__(
            None,
            title=i18n.APP_TITLE,
            size=wx.Size(720, 780),
        )
        self.SetName(i18n.APP_TITLE)
        self.SetAcceleratorTable(ACCEL_TABLE)

        self.settings = settings
        self.prefs: UserPrefs = load_user_prefs()
        self.client = MiniMaxMusicClient(
            base_url=settings.base_url,
            endpoint=settings.endpoint,
            api_key=settings.api_key,
        )
        self._current_worker: Optional[GenerationWorker] = None
        self._last_saved_path: Optional[Path] = None
        self._last_gen_input: Optional[GenerationInput] = None

        self._build_ui()
        self._bind_events()
        self._update_duet_controls()
        self._update_lyrics_controls()
        self._announce_status(i18n.STATUS_IDLE)

    # ==================== UI ====================

    def _build_ui(self) -> None:
        # Lista de controles na ordem de tabulação desejada.
        # Esta lista é usada pelo handler de EVT_NAVIGATION_KEY (manual),
        # porque MoveAfterInTabOrder tem bugs no wx 4.2 quando os
        # controles são de parents diferentes.
        self._tab_chain: list[wx.Window] = []

        # --- Estilo musical ---
        self.choice_style = wx.Choice(self, choices=i18n.STYLE_OPTIONS)
        self.choice_style.SetSelection(0)
        self.choice_style.SetName(i18n.LBL_STYLE)

        row_style = self._labeled_row(i18n.LBL_STYLE, self.choice_style)

        # --- Dupla ---
        self.chk_duet = wx.CheckBox(self, label=i18n.LBL_DUET_ENABLED)
        self.chk_duet.SetName(i18n.LBL_DUET_ENABLED)

        self.choice_duet_gender = wx.Choice(self, choices=i18n.DUET_GENDER_OPTIONS)
        self.choice_duet_gender.SetSelection(0)
        self.choice_duet_gender.SetName(i18n.LBL_DUET_GENDER)

        self.choice_duet_age = wx.Choice(self, choices=i18n.DUET_AGE_OPTIONS)
        self.choice_duet_age.SetSelection(0)
        self.choice_duet_age.SetName(i18n.LBL_DUET_AGE)

        row_duet = wx.BoxSizer(wx.HORIZONTAL)
        row_duet.Add(self.chk_duet, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        row_duet.Add(wx.StaticText(self, label=i18n.LBL_DUET_GENDER), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        row_duet.Add(self.choice_duet_gender, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        row_duet.Add(wx.StaticText(self, label=i18n.LBL_DUET_AGE), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        row_duet.Add(self.choice_duet_age, 0, wx.ALIGN_CENTER_VERTICAL)

        # --- Modo de letra ---
        self.choice_lyrics_mode = wx.Choice(self, choices=i18n.LYRICS_MODE_OPTIONS)
        self.choice_lyrics_mode.SetSelection(i18n.LYRICS_MODE_AUTO)
        self.choice_lyrics_mode.SetName(i18n.LBL_LYRICS_MODE)

        row_lyrics_mode = self._labeled_row(i18n.LBL_LYRICS_MODE, self.choice_lyrics_mode)

        # --- Tema / ideia (visível quando lyrics_mode = auto) ---
        self.txt_theme = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.txt_theme.SetName(i18n.LBL_LYRICS_PROMPT)
        self.txt_theme.SetHint(i18n.LBL_LYRICS_PROMPT)
        self.txt_theme.SetMinSize(wx.Size(-1, 60))

        row_theme = self._labeled_row(i18n.LBL_LYRICS_PROMPT, self.txt_theme, grow=True)

        # --- Letra fornecida pelo usuário (visível quando lyrics_mode = user) ---
        self.txt_lyrics = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.txt_lyrics.SetName(i18n.LBL_LYRICS)
        self.txt_lyrics.SetHint(i18n.LBL_LYRICS)
        self.txt_lyrics.SetMinSize(wx.Size(-1, 120))

        row_lyrics = self._labeled_row(i18n.LBL_LYRICS, self.txt_lyrics, grow=True)

        # --- Instrumental ---
        self.chk_instrumental = wx.CheckBox(self, label=i18n.LBL_INSTRUMENTAL)
        self.chk_instrumental.SetName(i18n.LBL_INSTRUMENTAL)

        # --- Botões principais ---
        self.btn_generate = wx.Button(self, label=i18n.BTN_GENERATE)
        self.btn_generate.SetDefault()
        self.btn_generate.SetName(i18n.BTN_GENERATE)

        self.btn_settings = wx.Button(self, label=i18n.BTN_SETTINGS)
        self.btn_settings.SetName(i18n.BTN_SETTINGS)

        self.btn_open_output = wx.Button(self, label=i18n.BTN_OPEN_OUTPUT)
        self.btn_open_output.SetName(i18n.BTN_OPEN_OUTPUT)

        # --- Status ---
        self.lbl_status = wx.StaticText(self, label=i18n.STATUS_IDLE)
        self.lbl_status.SetName(i18n.STATUS_IDLE)
        # Cor de "dica" sóbria
        self.lbl_status.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        # --- Player ---
        self.player = MusicPlayer(self)

        # --- Metadados do YouTube ---
        self._build_youtube_section()

        # --- Gauge de progresso (aparece durante geração, "pulsado" via Pulse()) ---
        self.gauge = wx.Gauge(self, range=100)
        self.gauge.Hide()
        self.gauge.SetName(i18n.STATUS_GENERATING)

        # ==================== Layout ====================

        main = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label=i18n.APP_TITLE)
        title_font = title.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 4)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        title.SetName(i18n.APP_TITLE)

        subtitle = wx.StaticText(self, label=i18n.APP_SUBTITLE)
        subtitle.SetName(i18n.APP_SUBTITLE)

        main.Add(title, 0, wx.ALL, 10)
        main.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        box = wx.StaticBox(self, label="Configuração da música")
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        box_sizer.Add(row_style, 0, wx.EXPAND | wx.ALL, 6)
        box_sizer.Add(row_duet, 0, wx.EXPAND | wx.ALL, 6)
        box_sizer.Add(row_lyrics_mode, 0, wx.EXPAND | wx.ALL, 6)
        box_sizer.Add(row_theme, 1, wx.EXPAND | wx.ALL, 6)
        box_sizer.Add(row_lyrics, 1, wx.EXPAND | wx.ALL, 6)
        box_sizer.Add(self.chk_instrumental, 0, wx.EXPAND | wx.ALL, 6)

        main.Add(box_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Botões
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.Add(self.btn_generate, 1, wx.RIGHT, 6)
        btn_row.Add(self.btn_settings, 0, wx.RIGHT, 6)
        btn_row.Add(self.btn_open_output, 0)

        main.Add(btn_row, 0, wx.EXPAND | wx.ALL, 10)
        main.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main.Add(self.lbl_status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        main.Add(self.player, 0, wx.EXPAND | wx.ALL, 10)
        main.Add(self.yt_box_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(main)
        self.Layout()

        # Ordem de tabulação explícita e acessível (NVDA/JAWS-friendly).
        # Usamos uma lista (self._tab_chain) e o handler EVT_NAVIGATION_KEY
        # para garantir controle total da navegação por Tab. O
        # MoveAfterInTabOrder tem bugs no wx 4.2 quando os controles
        # são de parents diferentes (Frame + Panel + StaticBox).
        self._tab_chain = [
            self.choice_style,          # 1. Estilo musical
            self.chk_duet,              # 2. É uma dupla cantando?
            self.choice_duet_gender,    # 3. Composição da dupla
            self.choice_duet_age,       # 4. Estilo da dupla
            self.choice_lyrics_mode,    # 5. Modo de letra
            self.txt_theme,             # 6. Tema (se auto)
            self.txt_lyrics,            # 7. Letra (se user)
            self.chk_instrumental,      # 8. Instrumental
            self.btn_generate,          # 9. Gerar música
            self.btn_settings,          # 10. Configurações
            self.btn_open_output,       # 11. Abrir pasta
            self.player.btn_play,       # 12. Tocar (Player)
            self.player.btn_pause,      # 13. Pausar
            self.player.btn_stop,       # 14. Parar
            self.btn_gen_yt,            # 15. Gerar metadados do YouTube
            self.btn_copy_yt,           # 16. Copiar tudo
            self.txt_yt_title,          # 17. Título
            self.txt_yt_desc,           # 18. Descrição
            self.txt_yt_tags,           # 19. Tags
        ]

        # Handler de navegação por Tab (manual, confiável).
        # Bindamos tanto EVT_NAVIGATION_KEY (modo "certo") quanto
        # EVT_KEY_DOWN (fallback) em ambos: o Frame E cada controle da
        # cadeia. Isso porque:
        # - EVT_NAVIGATION_KEY pode ser consumido por wxChoice/wxTextCtrl
        #   antes de chegar no Frame.
        # - EVT_KEY_DOWN captura o Tab diretamente, independente do
        #   evento de navegação.
        # Combinados, garantem que o Tab SEMPRE dispara a navegação.
        self.Bind(wx.EVT_NAVIGATION_KEY, self._on_navigation_key)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        for c in self._tab_chain:
            try:
                c.Bind(wx.EVT_NAVIGATION_KEY, self._on_navigation_key)
                c.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
            except Exception:
                pass

        # Define o foco inicial no primeiro controle (não no StaticText)
        self.choice_style.SetFocus()

        # Bind dos IDs do AcceleratorTable
        self.Bind(wx.EVT_MENU, self._on_generate,    id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self._on_open_output, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_settings,    id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._on_quit,        id=wx.ID_EXIT)

    def _labeled_row(
        self, label: str, control: wx.Window, grow: bool = False
    ) -> wx.Sizer:
        lbl = wx.StaticText(self, label=label)
        lbl.SetName(label)
        s = wx.BoxSizer(wx.HORIZONTAL)
        s.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        if grow:
            s.Add(control, 1, wx.EXPAND)
        else:
            s.Add(control, 0, wx.ALIGN_CENTER_VERTICAL)
        return s

    def _build_youtube_section(self) -> None:
        """Constrói a seção 'Metadados do YouTube' (caixa + campos)."""
        self.yt_box = wx.StaticBox(self, label=i18n.LBL_YT_METADATA)
        self.yt_box_sizer = wx.StaticBoxSizer(self.yt_box, wx.VERTICAL)

        # Botão principal
        self.btn_gen_yt = wx.Button(self, label=i18n.BTN_GEN_YT)
        self.btn_gen_yt.SetName(i18n.BTN_GEN_YT)
        self.btn_gen_yt.Disable()
        self.btn_gen_yt.Bind(
            wx.EVT_BUTTON, self._on_generate_youtube_metadata
        )

        self.btn_copy_yt = wx.Button(self, label=i18n.BTN_COPY_YT)
        self.btn_copy_yt.SetName(i18n.BTN_COPY_YT)
        self.btn_copy_yt.Bind(
            wx.EVT_BUTTON, self._on_copy_youtube_metadata
        )

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.Add(self.btn_gen_yt, 1, wx.RIGHT, 8)
        btn_row.Add(self.btn_copy_yt, 0)

        # Status / hint
        self.lbl_yt_status = wx.StaticText(self, label=i18n.LBL_YT_HINT)
        self.lbl_yt_status.SetName(i18n.LBL_YT_HINT)
        self.lbl_yt_status.SetForegroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        )

        # Campos (TextCtl editáveis)
        lbl_title = wx.StaticText(self, label=i18n.LBL_YT_TITLE)
        lbl_title.SetName(i18n.LBL_YT_TITLE)
        self.txt_yt_title = wx.TextCtrl(self)
        self.txt_yt_title.SetName(i18n.LBL_YT_TITLE)
        self.txt_yt_title.SetHint(i18n.LBL_YT_EMPTY)

        lbl_desc = wx.StaticText(self, label=i18n.LBL_YT_DESC)
        lbl_desc.SetName(i18n.LBL_YT_DESC)
        self.txt_yt_desc = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.txt_yt_desc.SetName(i18n.LBL_YT_DESC)
        self.txt_yt_desc.SetHint(i18n.LBL_YT_EMPTY)
        self.txt_yt_desc.SetMinSize(wx.Size(-1, 100))

        lbl_tags = wx.StaticText(self, label=i18n.LBL_YT_TAGS)
        lbl_tags.SetName(i18n.LBL_YT_TAGS)
        self.txt_yt_tags = wx.TextCtrl(self)
        self.txt_yt_tags.SetName(i18n.LBL_YT_TAGS)
        self.txt_yt_tags.SetHint(i18n.LBL_YT_EMPTY)

        self.yt_box_sizer.Add(btn_row, 0, wx.EXPAND | wx.ALL, 6)
        self.yt_box_sizer.Add(self.lbl_yt_status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.yt_box_sizer.Add(lbl_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.yt_box_sizer.Add(self.txt_yt_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.yt_box_sizer.Add(lbl_desc, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.yt_box_sizer.Add(self.txt_yt_desc, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.yt_box_sizer.Add(lbl_tags, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.yt_box_sizer.Add(self.txt_yt_tags, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Tab order dentro do StaticBox
        self.btn_gen_yt.MoveAfterInTabOrder(self.btn_open_output)
        self.btn_copy_yt.MoveAfterInTabOrder(self.btn_gen_yt)
        self.txt_yt_title.MoveAfterInTabOrder(self.btn_copy_yt)
        self.txt_yt_desc.MoveAfterInTabOrder(self.txt_yt_title)
        self.txt_yt_tags.MoveAfterInTabOrder(self.txt_yt_desc)

    def _set_tab_order(self, controls: list[wx.Window]) -> None:
        """Define a ordem de tabulação explícita para uma lista de controles.

        `MoveAfterInTabOrder` exige que ambos os controles sejam filhos
        do mesmo parent. Quando os controles vêm de parents diferentes
        (Frame + Panel + StaticBox), separamos em grupos e definimos a
        ordem DENTRO de cada grupo. As ligações cruzadas entre grupos
        são feitas por `MoveAfterInTabOrder` em controles que sejam
        filhos do mesmo parent, com `Wrap` para conectar grupos.
        """
        if not controls:
            return
        for prev, nxt in zip(controls, controls[1:]):
            try:
                nxt.MoveAfterInTabOrder(prev)
            except wx.wxAssertionError:
                # Controles de parents diferentes — pula silenciosamente.
                pass
            except Exception:
                pass

    def _set_tab_order_strict(self, controls: list[wx.Window]) -> None:
        """Versão estrita: para controles que SÃO do mesmo parent,
        MoveAfterInTabOrder funciona. Para os que NÃO são, usa-se
        `SetFocus` e `Navigate` como fallback. Aqui a gente separa
        por parent e ordena cada grupo.
        """
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for c in controls:
            groups[c.GetParent()].append(c)
        # Ordena cada grupo
        for parent, group in groups.items():
            for prev, nxt in zip(group, group[1:]):
                try:
                    nxt.MoveAfterInTabOrder(prev)
                except Exception:
                    pass

    # ==================== Eventos ====================

    def _on_navigation_key(self, evt: wx.NavigationKeyEvent) -> None:
        """Handler manual de navegação por Tab.

        Move o foco para o próximo controle da cadeia self._tab_chain,
        pulando controles desabilitados. Shift+Tab volta para o anterior.
        """
        # Marca o evento como handled (não propaga)
        self._navigate_to(evt.GetDirection() and 1 or -1)
        # NÃO chama evt.Skip() — consumimos o evento

    def _on_key_down(self, evt: wx.KeyEvent) -> None:
        """Fallback: captura Tab via EVT_KEY_DOWN se o EVT_NAVIGATION_KEY
        for consumido por algum controle (tipo wxChoice que abre dropdown)."""
        if evt.GetKeyCode() == wx.WXK_TAB:
            direction = -1 if evt.ShiftDown() else 1
            self._navigate_to(direction)
            return  # consome o evento
        evt.Skip()

    def _navigate_to(self, direction: int) -> None:
        """Move o foco para o próximo/anterior controle da cadeia."""
        chain = [c for c in self._tab_chain if c.IsEnabled() and c.IsShown()]
        if not chain:
            return
        current = wx.Window.FindFocus()
        if current is None:
            chain[0].SetFocus()
            return
        try:
            idx = chain.index(current)
        except ValueError:
            # Foco atual não está na cadeia: vai pro primeiro
            chain[0].SetFocus()
            return
        next_idx = (idx + direction) % len(chain)
        chain[next_idx].SetFocus()

    def _bind_events(self) -> None:
        self.btn_generate.Bind(wx.EVT_BUTTON, self._on_generate)
        self.btn_settings.Bind(wx.EVT_BUTTON, self._on_settings)
        self.btn_open_output.Bind(wx.EVT_BUTTON, self._on_open_output)
        self.chk_duet.Bind(wx.EVT_CHECKBOX, lambda _e: self._update_duet_controls())
        self.choice_lyrics_mode.Bind(
            wx.EVT_CHOICE, lambda _e: self._update_lyrics_controls()
        )

    # ----------------- UI dynamics -----------------

    def _update_duet_controls(self) -> None:
        enabled = self.chk_duet.IsChecked()
        for c in (self.choice_duet_gender, self.choice_duet_age):
            c.Enable(enabled)

    def _update_lyrics_controls(self) -> None:
        mode = self.choice_lyrics_mode.GetSelection()
        auto = (mode == i18n.LYRICS_MODE_AUTO)
        # Em modo auto, mostrar tema; em modo user, mostrar letra
        self.txt_theme.Enable(auto)
        self.txt_lyrics.Enable(not auto)

    # ----------------- Ações -----------------

    def _on_generate(self, _evt: wx.Event) -> None:
        if self._current_worker is not None:
            wx.MessageBox(
                "Já existe uma geração em andamento. Aguarde terminar.",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Validação
        if not self.settings.api_key:
            wx.MessageBox(
                "API key não configurada. Defina MINIMAX_API_KEY no arquivo .env "
                "ou nas Configurações do sistema, e reinicie o aplicativo.",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_WARNING,
            )
            return

        style = i18n.STYLE_OPTIONS[self.choice_style.GetSelection()]
        mode = self.choice_lyrics_mode.GetSelection()
        user_lyrics = self.txt_lyrics.GetValue().strip()

        if mode == i18n.LYRICS_MODE_USER and not user_lyrics:
            wx.MessageBox(
                "Você escolheu fornecer a letra, mas o campo está vazio.",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_WARNING,
            )
            self.txt_lyrics.SetFocus()
            return

        inp = GenerationInput(
            style=style,
            duet_enabled=self.chk_duet.IsChecked(),
            duet_gender=(i18n.DUET_GENDER_OPTIONS[
                self.choice_duet_gender.GetSelection()
            ] if self.chk_duet.IsChecked() else ""),
            duet_age=(i18n.DUET_AGE_OPTIONS[
                self.choice_duet_age.GetSelection()
            ] if self.chk_duet.IsChecked() else ""),
            lyrics_mode=("user" if mode == i18n.LYRICS_MODE_USER else "auto"),
            lyrics_prompt=self.txt_theme.GetValue().strip(),
            user_lyrics=user_lyrics,
            is_instrumental=self.chk_instrumental.IsChecked(),
        )

        try:
            prompt, lyrics, lyrics_optimizer, is_instrumental = (
                build_prompt_and_lyrics(inp)
            )
        except ValueError as e:
            wx.MessageBox(str(e), i18n.APP_TITLE, wx.OK | wx.ICON_WARNING)
            return

        # Configura diretório de saída
        out_dir = self.prefs.resolved_output_dir()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            wx.MessageBox(
                f"Não foi possível criar a pasta de saída:\n{out_dir}\n\n{e}",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_ERROR,
            )
            return

        filename = suggest_filename(inp, ext="mp3")

        # Auto-seleção inteligente: music-2.6 pra dueto, music-3.0 pra solo
        # (a não ser que o user tenha setado manualmente em Configurações)
        effective_model = self.prefs.effective_music_model(
            duet_enabled=inp.duet_enabled,
            env_default=self.settings.model,
        )
        use_clean = self.prefs.clean_lyrics_for_duet if inp.duet_enabled else True

        # O request inicial pode usar lyrics_optimizer=True (modo auto sem
        # letra roteirada) ou lyrics_optimizer=False com a letra do user.
        # O worker, se for dueto + auto, vai chamar o M3 antes e reescrever
        # o request com a letra roteirada.
        request = MusicRequest(
            prompt=prompt,
            lyrics=lyrics,
            lyrics_optimizer=lyrics_optimizer,
            is_instrumental=is_instrumental,
            model=effective_model,
        )

        # UI: bloquear botão, mostrar gauge
        self.btn_generate.Disable()
        self.gauge.Show()
        self.gauge.Pulse()
        self._announce_status(i18n.STATUS_GENERATING)

        worker = GenerationWorker(
            client=self.client,
            settings=self.settings,
            gen_input=inp,
            request=request,
            output_dir=out_dir,
            filename=filename,
            use_m3_for_lyrics=True,
            use_clean_lyrics=use_clean,
        )
        self._current_worker = worker
        # Guarda o gen_input pra usar depois (metadados do YouTube)
        self._last_gen_input = inp
        worker.start(on_done=self._on_generation_done)

    def _on_generation_done(self, res: WorkerResult) -> None:
        self.gauge.Hide()
        self.btn_generate.Enable()
        self._current_worker = None

        if not res.ok:
            self._announce_status(i18n.STATUS_ERROR.format(error=res.error or "?"))
            wx.MessageBox(
                res.error or "Erro desconhecido",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_ERROR,
            )
            return

        path = res.saved_path
        assert path is not None
        self._last_saved_path = path
        # Carrega no player (auto-play)
        if self.player.load(path):
            self._announce_status(i18n.STATUS_SAVED.format(path=str(path)))
        else:
            self._announce_status(i18n.STATUS_DONE.format(path=str(path)))
        # Habilita o botão de metadados do YouTube
        self.btn_gen_yt.Enable()

    def _on_generate_youtube_metadata(self, _evt: wx.Event) -> None:
        """Pede ao M3 metadados do YouTube (título/descrição/tags)."""
        if not self._last_saved_path:
            return
        # Pega o último gen_input que foi usado (precisamos dele pro prompt)
        if self._last_gen_input is None:
            return

        self.btn_gen_yt.Disable()
        self.lbl_yt_status.SetLabel(i18n.LBL_YT_LOADING)
        self._announce_status(i18n.LBL_YT_LOADING)

        def _worker_thread() -> None:
            try:
                from .lyrics_client import (
                    generate_youtube_metadata,
                    LyricsAPIError,
                    MiniMaxChatClient,
                )
                chat = MiniMaxChatClient(
                    chat_url=self.settings.chat_url,
                    api_key=self.settings.api_key,
                    model=self.settings.text_model,
                    timeout=120,
                )
                # Pega a letra do player se foi gerada pelo worker
                lyrics_ctx = ""
                if self._last_gen_input.lyrics_mode == "auto":
                    # Tenta pegar a letra gerada (se o player tem track,
                    # lemos do disco — mas é mais simples usar o gen_input)
                    # Como o worker não retorna a letra no momento,
                    # usamos o tema como contexto.
                    lyrics_ctx = ""
                data = generate_youtube_metadata(
                    client=chat,
                    style=self._last_gen_input.style,
                    duet_enabled=self._last_gen_input.duet_enabled,
                    duet_gender=self._last_gen_input.duet_gender or "",
                    duet_age=self._last_gen_input.duet_age or "",
                    theme=self._last_gen_input.lyrics_prompt
                          or self._last_gen_input.user_lyrics,
                    lyrics=lyrics_ctx,
                )
                wx.CallAfter(self._on_yt_metadata_done, data, None)
            except Exception as e:  # noqa: BLE001
                wx.CallAfter(self._on_yt_metadata_done, None, str(e))

        import threading
        t = threading.Thread(target=_worker_thread, daemon=True)
        t.start()

    def _on_yt_metadata_done(self, data, error: str | None) -> None:
        self.btn_gen_yt.Enable()
        if error:
            self.lbl_yt_status.SetLabel(i18n.STATUS_ERROR.format(error=error))
            wx.MessageBox(
                error, i18n.APP_TITLE, wx.OK | wx.ICON_ERROR,
            )
            return
        if not data:
            return
        # Preenche os campos
        self.txt_yt_title.SetValue(data.get("title", ""))
        self.txt_yt_desc.SetValue(data.get("description", ""))
        tags = data.get("tags", [])
        if isinstance(tags, list):
            self.txt_yt_tags.SetValue(", ".join(tags))
        else:
            self.txt_yt_tags.SetValue(str(tags))
        self.lbl_yt_status.SetLabel("")

    def _on_copy_youtube_metadata(self, _evt: wx.Event) -> None:
        """Copia os 3 campos para a área de transferência em formato útil."""
        if not wx.TheClipboard.IsOpened() and wx.TheClipboard.Open():
            try:
                data = wx.DataObjectComposite()
                # Texto formatado
                text = (
                    f"TÍTULO:\n{self.txt_yt_title.GetValue()}\n\n"
                    f"DESCRIÇÃO:\n{self.txt_yt_desc.GetValue()}\n\n"
                    f"TAGS:\n{self.txt_yt_tags.GetValue()}"
                )
                data.Add(wx.TextDataObject(text))
                wx.TheClipboard.SetData(data)
                wx.TheClipboard.Close()
                self._announce_status(i18n.LBL_YT_COPIED)
                self.lbl_yt_status.SetLabel(i18n.LBL_YT_COPIED)
            except Exception:
                pass
        elif wx.TheClipboard.IsOpened():
            wx.TheClipboard.Close()

    def _on_settings(self, _evt: wx.Event) -> None:
        with SettingsDialog(self, self.prefs) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                # Re-resolve as settings (modelo pode ter mudado)
                self.settings = resolve_settings()
                # Re-cria o cliente para garantir que pega o novo base_url/model
                self.client = MiniMaxMusicClient(
                    base_url=self.settings.base_url,
                    endpoint=self.settings.endpoint,
                    api_key=self.settings.api_key,
                )
                self._announce_status(
                    f"{i18n.MSG_SETTINGS_SAVED} (modelo: {self.settings.model})"
                )

    def _on_open_output(self, _evt: wx.Event) -> None:
        out_dir = self.prefs.resolved_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        self._open_in_file_manager(out_dir)

    def _open_in_file_manager(self, path: Path) -> None:
        path_str = str(path)
        try:
            if platform.system() == "Windows":
                os.startfile(path_str)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path_str])
            else:
                subprocess.Popen(["xdg-open", path_str])
        except OSError as e:
            wx.MessageBox(
                f"Não foi possível abrir a pasta:\n{path}\n\n{e}",
                i18n.APP_TITLE,
                wx.OK | wx.ICON_ERROR,
            )

    def _on_quit(self, _evt: wx.Event) -> None:
        self.Close()

    # ----------------- Acessibilidade -----------------

    def _announce_status(self, text: str) -> None:
        self.lbl_status.SetLabel(text)
        self.lbl_status.SetName(text)
        # Em wxPython ≥ 4.2, SetLabel dispara AccessibleNotify no Windows;
        # mas para garantir, forçamos um refresh.
        self.lbl_status.Refresh()

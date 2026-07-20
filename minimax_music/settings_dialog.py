"""Diálogo de configurações (pasta de saída + modelo de música)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import wx

from . import i18n
from .config import (
    default_output_dir,
    KNOWN_MUSIC_MODELS,
    save_user_prefs,
    UserPrefs,
)


class SettingsDialog(wx.Dialog):
    """Diálogo acessível para alterar a pasta de saída e o modelo de música."""

    def __init__(self, parent: wx.Window, current: UserPrefs):
        super().__init__(
            parent,
            title=i18n.DLG_SETTINGS_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.SetName(i18n.DLG_SETTINGS_TITLE)

        self._current_prefs = current
        initial = current.output_dir or str(default_output_dir())
        self._initial_dir = initial

        # ---- Pasta de saída ----
        self.txt_dir = wx.TextCtrl(self, value=initial)
        self.txt_dir.SetName(i18n.LBL_OUTPUT_DIR)
        self.txt_dir.SetToolTip(i18n.LBL_OUTPUT_DIR)

        self.btn_browse = wx.Button(self, label=i18n.BTN_BROWSE)
        self.btn_browse.Bind(wx.EVT_BUTTON, self._on_browse)

        # ---- Modelo de música (avançado) ----
        initial_model = current.music_model or i18n.MUSIC_MODEL_VALUES[0]
        if initial_model not in i18n.MUSIC_MODEL_VALUES:
            initial_model = i18n.MUSIC_MODEL_VALUES[0]
        self.choice_model = wx.Choice(
            self, choices=i18n.MUSIC_MODEL_OPTIONS,
        )
        self.choice_model.SetSelection(
            i18n.MUSIC_MODEL_VALUES.index(initial_model)
        )
        self.choice_model.SetName(i18n.LBL_MUSIC_MODEL)
        self.choice_model.SetToolTip(i18n.LBL_MUSIC_MODEL + " " + i18n.LBL_AUTO_HINT)

        # ---- Checkbox: letra limpa pra dueto ----
        self.chk_clean_lyrics = wx.CheckBox(
            self, label=i18n.LBL_CLEAN_LYRICS,
        )
        self.chk_clean_lyrics.SetValue(current.clean_lyrics_for_duet)
        self.chk_clean_lyrics.SetName(i18n.LBL_CLEAN_LYRICS)
        self.chk_clean_lyrics.SetToolTip(i18n.LBL_CLEAN_LYRICS)

        # ---- Botões ----
        self.btn_save = wx.Button(self, wx.ID_OK, i18n.BTN_SAVE)
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, i18n.BTN_CANCEL)
        self.btn_save.SetDefault()

        # ---- Layout ----
        lbl_dir = wx.StaticText(self, label=i18n.LBL_OUTPUT_DIR)
        lbl_dir.SetName(i18n.LBL_OUTPUT_DIR)
        lbl_model = wx.StaticText(self, label=i18n.LBL_MUSIC_MODEL)
        lbl_model.SetName(i18n.LBL_MUSIC_MODEL)
        lbl_hint = wx.StaticText(self, label=i18n.LBL_AUTO_HINT)
        lbl_hint.SetName(i18n.LBL_AUTO_HINT)
        lbl_hint.SetForegroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        )

        dir_row = wx.BoxSizer(wx.HORIZONTAL)
        dir_row.Add(self.txt_dir, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        dir_row.Add(self.btn_browse, 0, wx.ALIGN_CENTER_VERTICAL)

        model_row = wx.BoxSizer(wx.HORIZONTAL)
        model_row.Add(lbl_model, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        model_row.Add(self.choice_model, 0, wx.ALIGN_CENTER_VERTICAL)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer(1)
        btn_row.Add(self.btn_save, 0, wx.RIGHT, 8)
        btn_row.Add(self.btn_cancel, 0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(lbl_dir, 0, wx.ALL, 8)
        sizer.Add(dir_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(model_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(lbl_hint, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(self.chk_clean_lyrics, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(btn_row, 0, wx.EXPAND | wx.ALL, 8)

        self.SetSizerAndFit(sizer)
        self.SetMinSize(wx.Size(560, 240))
        self.SetSize(wx.Size(680, 260))

        # Ordem de tabulação explícita (acessibilidade)
        self.txt_dir.MoveAfterInTabOrder(lbl_dir)
        self.btn_browse.MoveAfterInTabOrder(self.txt_dir)
        self.choice_model.MoveAfterInTabOrder(self.btn_browse)
        self.chk_clean_lyrics.MoveAfterInTabOrder(self.choice_model)
        self.btn_save.MoveAfterInTabOrder(self.chk_clean_lyrics)
        self.btn_cancel.MoveAfterInTabOrder(self.btn_save)

        self.Bind(wx.EVT_BUTTON, self._on_save, id=wx.ID_OK)

    # ---------------- Handlers ----------------

    def _on_browse(self, _evt: wx.Event) -> None:
        with wx.DirDialog(
            self,
            message=i18n.DLG_CHOOSE_DIR_TITLE,
            defaultPath=self._initial_dir,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.txt_dir.SetValue(dlg.GetPath())

    def _on_save(self, _evt: wx.Event) -> None:
        path = self.txt_dir.GetValue().strip()
        if path and not Path(path).is_dir():
            wx.MessageBox(
                i18n.MSG_INVALID_DIR,
                i18n.DLG_SETTINGS_TITLE,
                wx.OK | wx.ICON_WARNING,
            )
            return
        self._current_prefs.output_dir = path

        # Modelo: salva o value (não o label)
        sel = self.choice_model.GetSelection()
        if sel >= 0 and sel < len(i18n.MUSIC_MODEL_VALUES):
            self._current_prefs.music_model = i18n.MUSIC_MODEL_VALUES[sel]
        else:
            self._current_prefs.music_model = ""

        # Checkbox de letra limpa
        self._current_prefs.clean_lyrics_for_duet = self.chk_clean_lyrics.IsChecked()

        try:
            save_user_prefs(self._current_prefs)
        except OSError as e:
            wx.MessageBox(
                f"Não foi possível salvar: {e}",
                i18n.DLG_SETTINGS_TITLE,
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.EndModal(wx.ID_OK)


def show_settings(parent: wx.Window, prefs: UserPrefs) -> Optional[UserPrefs]:
    """Atalho: mostra o diálogo e devolve as prefs atualizadas (ou None se cancelar)."""
    with SettingsDialog(parent, prefs) as dlg:
        if dlg.ShowModal() == wx.ID_OK:
            return prefs
        return None

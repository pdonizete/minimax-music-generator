# AGENTS.md — minimax-music-generator

> Diretrizes para qualquer agente de código que trabalhe neste projeto.

## Visão geral

App **wxPython 4.2.3** em Python 3.13 que gera músicas usando o endpoint
`POST /v1/music_generation` do Mavis (plano Token Plan, `api.minimax.io`).
Pensado para **acessibilidade com leitores de tela** (NVDA/JAWS) em
português brasileiro.

## Comandos essenciais

```powershell
# Ativar venv (já criada)
.\venv\Scripts\Activate.ps1

# Rodar o app
.\venv\Scripts\python -m minimax_music

# Rodar os testes
.\venv\Scripts\python -m pytest tests/ -v

# Gerar executável
.\venv\Scripts\pyinstaller --noconfirm --clean --windowed --name MavisMusicGenerator --collect-all wx --collect-all requests --add-data ".env.example;." --hidden-import "wx.media" minimax_music\__main__.py
# ou simplesmente:
.\build_exe.bat
```

## Configuração

- **Token:** definido em `.env` (campo `token_minimax` ou `MINIMAX_API_KEY`).
- **Endpoint / modelo:** também no `.env` (`MINIMAX_BASE_URL`,
  `MINIMAX_MUSIC_ENDPOINT`, `MINIMAX_MUSIC_MODEL`).
- **Pasta de saída:** padrão `<Músicas>/minimax-music/`. Alterável pelo
  diálogo **Configurações** da app ou pelo campo `MINIMAX_OUTPUT_DIR`
  no `.env`. Persistência em
  `%APPDATA%\MavisMusicGenerator\config.local.json`.

## Estrutura

```
minimax_music/
├── __main__.py        # entry: python -m minimax_music
├── app.py             # cria wx.App + MainWindow
├── config.py          # .env, paths, UserPrefs
├── api.py             # cliente HTTP Mavis music_generation
├── prompts.py         # presets de estilo + montagem do prompt
├── i18n.py            # strings PT-BR (todas!)
├── player.py          # wx.media.MediaCtrl acessível
├── settings_dialog.py # diálogo acessível
├── main_window.py     # janela principal (tab order explícita)
└── worker.py          # geração em thread separada (wx.CallAfter)
```

## Padrões de código

- **Acessibilidade em primeiro lugar.**
  - Todo controle tem `SetLabel`/`SetName` em PT-BR (centralizado em `i18n.py`).
  - Ordem de tabulação manual via `EVT_NAVIGATION_KEY` (`_on_navigation_key`).
    MoveAfterInTabOrder tem bugs no wx 4.2 quando controles são de
    parents diferentes (Frame + Panel + StaticBox), então usamos uma
    lista explícita `self._tab_chain` e o handler intercepta o Tab.
  - Mensagens de estado usam `SetLabel` + `SetName` + `Refresh` para
    forçar o `AccessibleNotify` no Windows (NVDA/JAWS anunciam).
  - Atalhos globais via `wx.AcceleratorTable`.

- **Threading:** chamadas HTTP **nunca** bloqueiam a UI. `worker.py`
  dispara thread daemon e devolve o resultado com `wx.CallAfter`.

- **Validação:** `MusicRequest.to_payload()` rejeita payloads inválidos
  ANTES de chamar a API (letra vazia sem `lyrics_optimizer`, etc).

- **Tratamento de erro:** `MusicAPIError` é a única exceção esperada;
  o worker captura qualquer outra e devolve em `WorkerResult.error`.

## API Mavis — referência rápida

- `POST {MINIMAX_BASE_URL}/v1/music_generation`
- Header: `Authorization: Bearer <MINIMAX_API_KEY>`
- Modelo recomendado: `music-3.0` (Token Plan, RPM 120)
- Campos úteis: `prompt` (1–2000), `lyrics` (1–3500), `lyrics_optimizer`,
  `is_instrumental`, `sample_rate`, `bitrate`, `audio_format` (mp3/wav/pcm).
- Resposta padrão: `{"audio": "<hex>", "base_resp": {...}, "extra_info": {...}}`
  (também suporta `output_format=url` com `audio_url`).

## Atalho de teclado (acessibilidade)

| Atalho | Ação |
|--------|------|
| **F5** | Gerar música |
| **Ctrl+O** | Abrir pasta de saída |
| **Ctrl+,** | Configurações |
| **Ctrl+Q** | Sair |

## Onde NÃO mexer

- `i18n.py` é a fonte de verdade das strings. Não escrever texto visível
  hardcoded em outros módulos.
- `prompts.py` mantém os presets de estilo (romântica, sertanejo, etc).
  Para adicionar um novo estilo, adicionar entrada em `STYLE_PRESETS`
  E em `i18n.STYLE_OPTIONS`.
- `config.py` é a única coisa que toca `.env`/`config.local.json`.

## Pendências conhecidas

- Player usa `wx.media.MediaCtrl` (Windows Media Player). No Linux/macOS
  o backend default pode não aceitar mp3; nesse caso considerar `pygame`
  como fallback (não implementado).
- PyInstaller gera `dist\MavisMusicGenerator\` (one-dir); one-file precisa
  ajustar `--onedir` vs `--onefile` no `build_exe.bat`.

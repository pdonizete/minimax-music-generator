# Gerador de Músicas Mavis

Aplicativo **wxPython** (Windows) para gerar músicas usando os modelos
de música do **Mavis** (plano Token Plan, `api.minimax.io`).

Pensado para **acessibilidade** com leitores de tela (NVDA/JAWS): todos
os controles têm nomes acessíveis em português, ordem de tabulação
explícita, atalhos de teclado e anúncios de status.

---

## Funcionalidades

- **Geração de música** com:
  - Estilo musical: Romântica, Sertanejo universitário, Sertanejo raiz, Pagode, Pop, Rock.
  - **Dupla cantando** (opcional): composição (homem+mulher, duas mulheres, dois homens) e faixa etária (jovens, adultos, idosos).
  - **Letra**:
    - Gerada automaticamente pelo Mavis a partir de um tema/ideia, **ou**
    - Fornecida pelo próprio usuário.
  - **Modo instrumental** (sem voz).
- **Pipeline inteligente pra duetos:**
  - Quando você marca "É uma dupla cantando?", o app **automaticamente**:
    1. Escolhe `music-2.6` (sweet spot pra duetos — respeita a alternância de vozes)
    2. Pede ao M3 uma **letra limpa** (sem prefixos como `F:`/`M:` ou `Ana:`/`Pedro:` sendo cantados)
    3. Inclui uma `voice_direction` no prompt dizendo ao music-2.6: "no `[Verse]` voz feminina, no `[Chorus]` voz masculina, no `[Bridge]` os dois juntos"
  - Resultado: letra cantada 100% limpa (sem prefixos) + alternância de vozes funcionando.
  - Você pode **forçar `music-3.0`** ou **desligar a letra limpa** em Configurações → "Modelo de música (avançado)".
- **Player integrado** (wx.media.MediaCtrl) com botões Tocar/Pausar/Parar.
- **Salvamento automático** em `<Músicas>/minimax-music/`
  (configurável pelo diálogo de Configurações).
- **Configurações persistidas** em `%APPDATA%\MavisMusicGenerator\config.local.json`.
- **Acessibilidade**:
  - Nomes acessíveis (PT-BR) em todos os controles.
  - Ordem de tabulação explícita.
  - Atalhos: **F5** = Gerar, **Ctrl+O** = Abrir pasta, **Ctrl+,** = Configurações, **Ctrl+Q** = Sair.
  - Anúncios de status (geração concluída, erros, etc).

## Estratégia por modelo

| Cenário | Modelo | Por quê |
|---|---|---|
| Dueto (auto) | `music-2.6` | Obedece instruções de voz via tags estruturais — funciona a alternância |
| Solo / instrumental | `music-3.0` | Mais novo, qualidade superior, RPM maior |
| Dueto forçado em `music-3.0` | `music-3.0` | Funciona, mas tende a cantar tudo com voz feminina (limitação do modelo) |

---

## Configuração

Copie `.env.example` para `.env` na raiz do projeto e preencha:

```ini
token_minimax=sk-cp-seu-token-aqui
MINIMAX_BASE_URL=https://api.minimax.io
MINIMAX_MUSIC_ENDPOINT=/v1/music_generation
MINIMAX_MUSIC_MODEL=music-3.0
MINIMAX_OUTPUT_DIR=
```

> A chave aceita tanto `MINIMAX_API_KEY` quanto `token_minimax`
> (legado, mantido por compatibilidade com o arquivo `.env` que veio
> do projeto). Se ambas existirem, `MINIMAX_API_KEY` tem precedência.

A pasta de saída também pode ser alterada em tempo de execução pela
tela **Configurações** e fica salva em
`%APPDATA%\MavisMusicGenerator\config.local.json`.

---

## Ambiente virtual (venv) — desenvolvimento

```powershell
cd D:\projetos\python\minimax-music-generator
python -m venv venv
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\python -m pip install -r requirements.txt
.\venv\Scripts\python -m minimax_music
```

ou:

```powershell
.\venv\Scripts\python -m minimax_music
```

> **Importante:** use **sempre** `python -m minimax_music` (nunca rode
> `__main__.py` ou `app.py` solto — os imports relativos vão falhar).

---

## Gerar o executável (Windows)

```cmd
build_exe.bat
```

Saída: `dist\MavisMusicGenerator\MavisMusicGenerator.exe`.

O script usa `run_app.py` (na raiz) como entry point do PyInstaller.
**Não usa** `minimax_music\__main__.py` diretamente — isso causaria
`ImportError: attempted relative import with no known parent package`
quando o `.exe` rodasse, porque o PyInstaller executa o entry point
como script solto (sem parent package).

> **Importante:** ao distribuir, coloque o arquivo `.env` (com o token)
> **ao lado do `.exe`**. O app procura primeiro o `.env` na pasta do
> executável e, em seguida, nas variáveis de ambiente do processo.

---

## Estrutura do projeto

```
minimax-music-generator/
├── .env                     # token + endpoint (NÃO versionar)
├── .env.example
├── .gitignore
├── requirements.txt
├── build_exe.bat
├── minimax_music/
│   ├── __init__.py
│   ├── __main__.py          # entry: python -m minimax_music
│   ├── app.py               # cria o wx.App e roda a janela
│   ├── config.py            # .env, paths, preferências
│   ├── api.py               # cliente MiniMax music_generation
│   ├── prompts.py           # presets de estilo + montagem do prompt
│   ├── player.py            # player wx.media.MediaCtrl
│   ├── settings_dialog.py   # diálogo acessível de configurações
│   ├── main_window.py       # janela principal
│   ├── worker.py            # geração em thread separada
│   └── i18n.py              # strings PT-BR
└── tests/                   # testes pytest
```

---

## API MiniMax — referência rápida

- **Endpoint:** `POST https://api.minimax.io/v1/music_generation`
- **Header:** `Authorization: Bearer <token>`
- **Modelo recomendado:** `music-3.0` (Token Plan)
- **Body (campos principais):**
  - `prompt` — descrição do estilo, humor e cenário (até 2000 chars).
  - `lyrics` — letra com tags de estrutura (`[Verse]`, `[Chorus]`, etc).
  - `lyrics_optimizer` — se `true`, o modelo gera a letra a partir do `prompt` (e a letra fornecida é ignorada).
  - `is_instrumental` — se `true`, gera apenas instrumental.
  - `sample_rate`, `bitrate`, `audio_format` — qualidade do MP3/WAV/PCM.

A resposta traz o áudio em **hex** por padrão (o cliente já converte para
bytes e salva em disco). Para uma URL temporária, use `output_format=url`
no payload.

---

## Testes

```powershell
.\venv\Scripts\python -m pytest tests\ -v
```

---

## Licença

Uso pessoal/educacional. O uso da API está sujeito aos termos do
[plano Token Plan do Mavis](https://platform.minimax.io/docs/pricing/overview).

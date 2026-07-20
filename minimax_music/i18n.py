"""Strings de interface (pt-BR) centralizadas para acessibilidade.

Todas as mensagens visíveis ao usuário passam por aqui para que leitores de
tela leiam o texto correto e para que a localização fique em um único ponto.
"""

from __future__ import annotations

# -------- Janela principal --------
APP_TITLE = "Gerador de Músicas Mavis"
APP_SUBTITLE = "Gere músicas com os modelos de música do Mavis"

# -------- Controles principais --------
LBL_STYLE = "Estilo musical:"
LBL_DUET_ENABLED = "É uma dupla cantando?"
LBL_DUET_GENDER = "Composição da dupla:"
LBL_DUET_AGE = "Estilo da dupla:"
LBL_LYRICS_MODE = "Quem escreve a letra?"
LBL_LYRICS_PROMPT = "Tema / ideia da música (usado se o Mavis gerar a letra):"
LBL_LYRICS = "Letra da música (usada se você escrever a sua própria):"
LBL_INSTRUMENTAL = "Gerar apenas instrumental (sem voz)?"
BTN_GENERATE = "Gerar música"
BTN_OPEN_OUTPUT = "Abrir pasta de saída"
BTN_SETTINGS = "Configurações"
BTN_QUIT = "Sair"

# -------- Player --------
LBL_PLAYER = "Player de música"
BTN_PLAY = "Tocar"
BTN_PAUSE = "Pausar"
BTN_STOP = "Parar"
LBL_NO_TRACK = "Nenhuma música carregada."
LBL_TRACK_LOADED = "Música carregada: {filename}"

# -------- Metadados do YouTube --------
LBL_YT_METADATA = "Metadados do YouTube"
BTN_GEN_YT = "Gerar metadados do YouTube"
BTN_COPY_YT = "Copiar tudo"
LBL_YT_TITLE = "Título sugerido:"
LBL_YT_DESC = "Descrição sugerida:"
LBL_YT_TAGS = "Tags sugeridas:"
LBL_YT_HINT = "Clique no botão acima para o Mavis sugerir título, descrição e tags para o YouTube."
LBL_YT_NO_TRACK = "Gere uma música primeiro — depois gere os metadados."
LBL_YT_LOADING = "Gerando metadados do YouTube..."
LBL_YT_COPIED = "Metadados copiados para a área de transferência."
LBL_YT_EMPTY = "(vazio)"

# -------- Diálogo de configurações --------
DLG_SETTINGS_TITLE = "Configurações"
LBL_OUTPUT_DIR = "Pasta onde as músicas serão salvas:"
LBL_MUSIC_MODEL = "Modelo de música (avançado):"
LBL_CLEAN_LYRICS = "Para duetos, usar letra limpa (sem prefixos cantados):"
LBL_AUTO_HINT = "Deixe em branco para auto-selecionar (music-2.6 pra dueto, music-3.0 pra solo)."
BTN_BROWSE = "Escolher pasta…"
BTN_SAVE = "Salvar"
BTN_CANCEL = "Cancelar"
DLG_CHOOSE_DIR_TITLE = "Escolha a pasta de saída das músicas"
MSG_SETTINGS_SAVED = "Configurações salvas."
MSG_INVALID_DIR = "A pasta escolhida é inválida. Selecione uma pasta existente."
MUSIC_MODEL_OPTIONS = [
    "Auto (music-2.6 pra dueto, music-3.0 pra solo)",
    "music-3.0 (recomendado pra solo)",
    "music-2.6 (alternativa, sweet spot pra dueto)",
]
MUSIC_MODEL_VALUES = ["", "music-3.0", "music-2.6"]

# -------- Diálogo "Sobre" --------
DLG_ABOUT_TITLE = "Sobre"
ABOUT_TEXT = (
    "Gerador de Músicas Mavis\n"
    "Versão {version}\n\n"
    "Gera músicas usando os modelos de música do Mavis (api.minimax.io).\n"
    "Interface wxPython com suporte a leitores de tela."
)

# -------- Estilos musicais --------
STYLE_OPTIONS = [
    "Romântica",
    "Sertanejo universitário",
    "Sertanejo raiz",
    "Pagode",
    "Pop",
    "Rock",
]

# -------- Composição da dupla --------
DUET_GENDER_OPTIONS = [
    "Homem e mulher",
    "Duas mulheres",
    "Dois homens",
]

# -------- Estilo (idade) da dupla --------
DUET_AGE_OPTIONS = [
    "Jovens",
    "Adultos",
    "Idosos",
]

# -------- Modo de letra --------
LYRICS_MODE_OPTIONS = [
    "O Mavis gera a letra automaticamente",
    "Eu forneço minha própria letra",
]
LYRICS_MODE_AUTO = 0
LYRICS_MODE_USER = 1

# -------- Status / geração --------
STATUS_IDLE = "Pronto."
STATUS_GENERATING = "Gerando música… isso pode levar alguns minutos."
STATUS_DONE = "Música pronta: {path}"
STATUS_ERROR = "Erro: {error}"
STATUS_SAVED = "Música salva em: {path}"

# -------- Geração de mensagens para leitor de tela --------
def a11y_label(text: str) -> str:
    """Decorator textual: evita labels redundantes para o leitor de tela.

    wxPython por padrão usa o texto do controle como nome acessível. Esta
    função é um gancho caso no futuro seja necessário normalizar/remover
    acentos para anúncios de estado.
    """
    return text

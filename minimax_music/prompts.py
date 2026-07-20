"""Mapeia as escolhas do usuário → prompt + letras para a API Music.

Mantemos os presets em PT-BR (estilos musicais brasileiros) e a API aceita
até 2000 caracteres no `prompt`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


# Tags estruturais reconhecidas pelo music-3.0 (sem prefixo/sufixo).
_STRUCTURE_TAGS = (
    "Intro", "Verse", "Pre Chorus", "Chorus", "Interlude",
    "Bridge", "Outro", "Post Chorus", "Transition", "Break",
    "Hook", "Build Up", "Inst", "Solo",
)


def _has_structure_tags(text: str) -> bool:
    """Retorna True se o texto contém tags estruturais como [Verse] ou [Chorus]."""
    if not text:
        return False
    pattern = r"\[(" + "|".join(_STRUCTURE_TAGS) + r")\]"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _has_voice_prefixes(text: str) -> bool:
    """Detecta se as linhas de letra têm prefixos de voz.

    Aceita: F:, M:, F&M:, F1:, F2:, M1:, M2: ou nomes próprios
    (palavra + dois-pontos no início da linha).
    """
    if not text:
        return False
    # Padrões curtos
    short_pat = re.compile(r"^\s*(F|M|F&M|F1|F2|M1|M2):\s", re.MULTILINE)
    if short_pat.search(text):
        return True
    # Nomes próprios: qualquer palavra (com letra) + ":" + espaço
    # no começo de uma linha, mas só se aparecer várias vezes
    # (pra não confundir com acentos de digitação)
    name_pat = re.compile(r"^\s*[A-Za-z]+\s*:\s", re.MULTILINE)
    matches = name_pat.findall(text)
    return len(matches) >= 4  # Pelo menos 4 linhas com prefixo de nome


@dataclass(frozen=True)
class GenerationInput:
    """Entrada normalizada a partir da UI."""

    style: str                       # ex: "Romântica"
    duet_enabled: bool               # True = dupla cantando
    duet_gender: str = ""            # ex: "Homem e mulher"
    duet_age: str = ""               # ex: "Jovens"
    lyrics_mode: str = ""            # "auto" | "user"
    lyrics_prompt: str = ""          # tema/ideia (modo auto)
    user_lyrics: str = ""            # letra fornecida (modo user)
    is_instrumental: bool = False


# --------------------- Presets de estilo ---------------------

STYLE_PRESETS: dict[str, str] = {
    "Romântica": (
        "Romantic ballad, soft and emotional, smooth vocal delivery, "
        "gentle strings, warm piano chords, mid-tempo, intimate and tender mood"
    ),
    "Sertanejo universitário": (
        "Brazilian sertanejo universitario, modern production, electric guitar, "
        "acoustic guitar, accordion, romantic and youthful vibe, mid-tempo, "
        "polished radio-ready mix, romantic Brazilian sertanejo"
    ),
    "Sertanejo raiz": (
        "Brazilian sertanejo raiz (caipira), acoustic guitar, viola caipira, "
        "rabeca, traditional country feeling, rustic and heartfelt, "
        "Brazilian caipira"
    ),
    "Pagode": (
        "Brazilian pagode, samba groove, cavaco, banjo, tantan, surdo, "
        "warm percussion, party mood, vocal harmonies, joyful and rhythmic"
    ),
    "Pop": (
        "Modern pop, catchy hook, bright synths, polished drums, "
        "radio-ready production, energetic and uplifting mood"
    ),
    "Rock": (
        "Classic rock, electric guitars, driving drums, powerful vocals, "
        "anthemic chorus, high energy, distorted guitars and bass"
    ),
}


# --------------------- Mapeamentos auxiliares ---------------------

# Truque de prompt engineering para o music-3.0: ele tende a interpretar
# "duet" como "voz principal + backing vocals em harmonia" em vez de
# "duas vozes lead distintas". Então:
# 1) NÃO usamos "duet" — usamos "lead vocalist" / "lead vocal" e descrevemos
#    a estrutura de chamada e resposta.
# 2) Nomeamos as vozes pelo gênero (female / male) e indicamos que ambas
#    são "lead" (não backing).
# 3) Descrevemos o que cada uma faz: uma canta o verso, a outra o refrão,
#    e as duas cantam juntas no final. Isso força o modelo a alternar.
GENDER_MAP = {
    "Homem e mulher": (
        "two distinct lead vocals: a clearly audible female lead vocalist "
        "and a clearly audible male lead vocalist, both are primary lead "
        "voices (not backing vocals), the female sings the verses, the male "
        "sings the chorus, and both sing together in the final chorus. "
        "Each voice must be solo and clearly identifiable on its own"
    ),
    "Duas mulheres":  (
        "two distinct lead vocals: two clearly audible female lead "
        "vocalists, both are primary lead voices (not backing vocals), "
        "they alternate singing verses and chorus, each voice must be solo "
        "and clearly identifiable on its own"
    ),
    "Dois homens":    (
        "two distinct lead vocals: two clearly audible male lead "
        "vocalists, both are primary lead voices (not backing vocals), "
        "they alternate singing verses and chorus, each voice must be solo "
        "and clearly identifiable on its own"
    ),
}

AGE_MAP = {
    "Jovens":  "young-sounding voices, fresh and bright tone, youthful energy",
    "Adultos": "adult voices, mature and balanced tone",
    "Idosos":  "older voices, warm, deep, and seasoned tone, experienced singers",
}


# --------------------- Roteiro de vozes (plano B) ---------------------

# Quando o usuário marca "dupla cantando" e fornece uma letra roteirada
# (com [Verse]/[Chorus]/[Bridge]), esta string é injetada no prompt
# para dizer ao music-3.0 QUEM canta CADA seção. Sem isso, ele canta
# tudo com a mesma voz.
def voice_direction(duet_gender: str) -> str:
    """Devolve a string de 'Voice direction' para o prompt.

    Assume que a letra usa as tags padrão (Verse, Chorus, Bridge) E
    NOMES de cantores como prefixo de cada linha (Ana:, Pedro:, Ana e Pedro:)
    — produzidos pelo MiniMax-M3 quando instruído a roteirar a letra.

    O music-2.6 entende nomes próprios como "speaker" e troca a voz por
    eles, sem necessariamente cantar o nome.
    """
    if duet_gender == "Homem e mulher":
        return (
            "Voice direction: this song has two distinct lead vocals — one "
            "female ('Ana') and one male ('Pedro'). Every lyric line begins "
            "with a speaker tag: 'Ana:' = sung by Ana (female voice, solo), "
            "'Pedro:' = sung by Pedro (male voice, solo), 'Ana e Pedro:' = "
            "sung by both together. STRICT rules: lines starting with 'Ana:' "
            "must be sung by a clearly audible female voice ONLY (no male "
            "voice, no harmonies). Lines starting with 'Pedro:' must be sung "
            "by a clearly audible male voice ONLY (no female voice, no "
            "harmonies, no backing vocals from Ana). The speaker tag itself "
            "is a label — it is NOT part of the lyrics being sung. Each voice "
            "must be clearly distinguishable."
        )
    if duet_gender == "Duas mulheres":
        return (
            "Voice direction: this song has two distinct female lead vocals "
            "('Ana' and 'Beatriz'). 'Ana:' = sung by Ana solo. 'Beatriz:' = "
            "sung by Beatriz solo. 'Ana e Beatriz:' = both together. The "
            "speaker tag is NOT part of the sung lyrics. Each voice must be "
            "solo and clearly identifiable on its own."
        )
    if duet_gender == "Dois homens":
        return (
            "Voice direction: this song has two distinct male lead vocals "
            "('Pedro' and 'Lucas'). 'Pedro:' = sung by Pedro solo. 'Lucas:' = "
            "sung by Lucas solo. 'Pedro e Lucas:' = both together. The "
            "speaker tag is NOT part of the sung lyrics. Each voice must be "
            "solo and clearly identifiable on its own."
        )
    return ""


def voice_direction_clean(duet_gender: str) -> str:
    """Devolve a 'voice direction' para letras LIMPAS (sem prefixos).

    Hipótese: o music-2.6 pode fazer a alternância de vozes baseado
    apenas nas tags [Verse]/[Chorus]/[Bridge] e no prompt — sem
    precisar de prefixos nas linhas. Esta é uma versão "limpa" da
    voice direction.
    """
    if duet_gender == "Homem e mulher":
        return (
            "Voice direction: this song has two distinct lead vocals — a "
            "female voice and a male voice. STRICT structure:\n"
            "- Every [Verse] section must be sung by the female voice ONLY "
            "(solo, clearly audible, no male voice, no harmonies from the man).\n"
            "- Every [Chorus] section must be sung by the male voice ONLY "
            "(solo, clearly audible, no female voice, no harmonies from the woman).\n"
            "- The [Bridge] must be sung by BOTH voices together.\n"
            "- The final [Chorus] must be sung by BOTH voices together as a duet.\n"
            "Each voice must be clearly distinguishable. The lyrics have NO "
            "speaker tags — you must rely on the structural tags ([Verse], "
            "[Chorus], [Bridge]) and these instructions to know who sings what."
        )
    if duet_gender == "Duas mulheres":
        return (
            "Voice direction: this song has two distinct female lead vocals. "
            "[Verse] = first female, [Chorus] = second female, [Bridge] and "
            "final [Chorus] = both together. Each voice must be solo and "
            "clearly identifiable on its own."
        )
    if duet_gender == "Dois homens":
        return (
            "Voice direction: this song has two distinct male lead vocals. "
            "[Verse] = first male, [Chorus] = second male, [Bridge] and final "
            "[Chorus] = both together. Each voice must be solo and clearly "
            "identifiable on its own."
        )
    return ""


# --------------------- Letra exemplo (plano B) ---------------------

# Letra em PT-BR sobre o tema "primeiro amor no interior, cidade pequena,
# chuva de verão". Roteirada com tags padrão do music-3.0.
EXAMPLE_DUET_LYRICS = (
    "[Intro]\n"
    "(instrumental)\n"
    "\n"
    "[Verse]\n"
    "Era uma vez numa cidade pequena do interior\n"
    "Sob a chuva de verao, te vi pela primeira vez\n"
    "Seu olhar cruzou o meu naquele instante\n"
    "E o meu coracao disparou sem mais nem menos\n"
    "\n"
    "[Chorus]\n"
    "Esse amor chegou sem avisar\n"
    "E agora eu nao consigo mais te esquecer\n"
    "Cada chuva que cai me faz lembrar\n"
    "Daquele dia em que te vi pela primeira vez\n"
    "\n"
    "[Verse]\n"
    "O perfume da terra molhada\n"
    "Se misturou com seu sorriso no varandao\n"
    "Eu nao sabia o que dizer\n"
    "Mas o seu olhar disse tudo pra mim\n"
    "\n"
    "[Chorus]\n"
    "Esse amor chegou sem avisar\n"
    "E agora eu nao consigo mais te esquecer\n"
    "Cada chuva que cai me faz lembrar\n"
    "Daquele dia em que te vi pela primeira vez\n"
    "\n"
    "[Bridge]\n"
    "E quando a chuva parou\n"
    "E o sol voltou a brilhar\n"
    "Eu soube que era real\n"
    "E que nao ia te perder nunca mais\n"
    "\n"
    "[Chorus]\n"
    "Esse amor chegou sem avisar\n"
    "E agora eu nao consigo mais te esquecer\n"
    "Cada chuva que cai me faz lembrar\n"
    "Daquele dia em que te vi pela primeira vez\n"
    "Esse amor e pra sempre, meu bem"
)

# Versão com prefixos de voz (Ana:/Pedro:/Ana e Pedro:) — usada em
# testes que esperam voice_direction com nomes.
EXAMPLE_DUET_LYRICS_WITH_PREFIXES = (
    "[Verse]\n"
    "Ana: era uma vez numa cidade pequena do interior\n"
    "Ana: sob a chuva de verao, te vi pela primeira vez\n"
    "Ana: seu olhar cruzou o meu naquele instante\n"
    "Ana: e o meu coracao disparou sem mais nem menos\n"
    "\n"
    "[Chorus]\n"
    "Pedro: esse amor chegou sem avisar\n"
    "Pedro: e agora eu nao consigo mais te esquecer\n"
    "Pedro: cada chuva que cai me faz lembrar\n"
    "Pedro: daquele dia em que te vi pela primeira vez\n"
    "\n"
    "[Bridge]\n"
    "Ana e Pedro: e quando a chuva parou\n"
    "Ana e Pedro: e o sol voltou a brilhar\n"
    "Ana e Pedro: eu soube que era real\n"
    "Ana e Pedro: e que nao ia te perder nunca mais\n"
    "\n"
    "[Chorus]\n"
    "Ana e Pedro: esse amor chegou sem avisar\n"
    "Ana e Pedro: e agora eu nao consigo mais te esquecer\n"
    "Ana e Pedro: cada chuva que cai me faz lembrar\n"
    "Ana e Pedro: daquele dia em que te vi pela primeira vez"
)


# --------------------- Função principal ---------------------

def build_prompt_and_lyrics(
    inp: GenerationInput,
    override_lyrics: str | None = None,
) -> tuple[str, str, bool, bool]:
    """Devolve (prompt, lyrics, lyrics_optimizer, is_instrumental).

    - `prompt`: descrição do estilo (até 2000 chars).
    - `lyrics`: letra ou vazia (se lyrics_optimizer).
    - `lyrics_optimizer`: True quando o Mavis deve gerar a letra a partir
      do `lyrics_prompt` (tema/ideia fornecido pelo usuário).
    - `is_instrumental`: True para gerar apenas instrumental.
    - `override_lyrics`: se fornecido, substitui `inp.user_lyrics` (usado
      quando o worker já pediu ao M3 uma letra roteirada antes de chamar
      o music-3.0).

    Ordem de prioridade quando o prompt estoura 2000 chars:
    1. Gênero (essencial — define se há voz feminina)
    2. Idade da dupla
    3. Guarda-chuva "ambas as vozes"
    4. Tema (lyrics_prompt)
    5. Preset de estilo (primeiro a ser cortado se faltar espaço)
    """
    style_preset = STYLE_PRESETS.get(inp.style, "")
    if not style_preset:
        raise ValueError(f"Estilo desconhecido: {inp.style!r}")

    # Coleta com prioridade: gênero/idade/guarda-chuva são essenciais,
    # preset é o primeiro a ser sacrificado.
    essential: list[str] = []
    style_parts: list[str] = [style_preset]

    if inp.duet_enabled:
        if inp.duet_gender:
            essential.append(GENDER_MAP.get(inp.duet_gender, ""))
        if inp.duet_age:
            essential.append(AGE_MAP.get(inp.duet_age, ""))
        # Plano B: se a letra vier roteirada (modo user com tags estruturais
        # OU override_lyrics vindo do M3), adiciona a "Voice direction"
        # dizendo quem canta cada seção.
        effective_lyrics = override_lyrics if override_lyrics else inp.user_lyrics
        if (effective_lyrics
                and _has_structure_tags(effective_lyrics)):
            # Heurística: se a letra tem prefixos de voz (F:/M: ou
            # nomes como Ana:/Pedro:), usa a voice_direction com prefixos.
            # Senão, usa a versão "clean" (só com tags).
            if _has_voice_prefixes(effective_lyrics):
                vd = voice_direction(inp.duet_gender)
            else:
                vd = voice_direction_clean(inp.duet_gender)
            if vd:
                essential.append(vd)
        # Guarda-chuva: nomeia explicitamente "lead vocals" distintos e
        # proíbe backing vocals femininos mascarando a voz masculina.
        essential.append(
            "Crucial: produce two distinct lead vocals (not one lead + "
            "background harmonies). Both lead voices must be clearly "
            "audible, solo, and identifiable — a real man-and-woman duet, "
            "not a solo with harmonies."
        )

    if inp.is_instrumental:
        essential.append("Instrumental only, no vocals, melodic lead instruments")

    # Limpa strings vazias
    essential = [s.strip() for s in essential if s and s.strip()]
    style_parts = [s.strip() for s in style_parts if s and s.strip()]

    # 1) Prompt mínimo SEM o preset de estilo (só essenciais)
    prompt_min = ", ".join(essential)
    if prompt_min:
        prompt_min = prompt_min + "."

    # 2) Tenta encaixar o preset no espaço restante
    limit = 2000
    # Reserva 60 chars para " Theme: ..." se houver tema
    theme_to_add = ""
    if (not inp.is_instrumental
            and inp.lyrics_mode != "user"
            and inp.lyrics_prompt.strip()):
        t = inp.lyrics_prompt.strip()
        # Limita tema a no máx 1/3 do espaço para não dominar
        theme_budget = min(len(t), 600)
        theme_to_add = f" Theme: {t[:theme_budget].rstrip()}."

    remaining = limit - len(prompt_min) - len(theme_to_add)
    if remaining < 100:
        # Sem espaço nem para o preset — usa só essenciais + tema curto
        style_text = ""
    else:
        # Empacota os style_parts até caber
        style_text = ", ".join(style_parts)
        if len(style_text) > remaining:
            style_text = style_text[: max(0, remaining - 3)].rstrip() + "..."

    # Monta o prompt final
    if style_text:
        prompt = f"{style_text}. {prompt_min}".strip()
    else:
        prompt = prompt_min

    if theme_to_add:
        prompt = (prompt + theme_to_add)[:limit]

    # Letras
    lyrics_optimizer = False
    lyrics = ""

    if inp.is_instrumental:
        lyrics = ""
    elif inp.lyrics_mode == "user":
        lyrics = inp.user_lyrics.strip()
        if not lyrics:
            raise ValueError("Você escolheu fornecer a letra, mas ela está vazia.")
    else:  # "auto" / default
        lyrics_optimizer = True

    return prompt, lyrics, lyrics_optimizer, inp.is_instrumental


# --------------------- Sugestão de nome de arquivo ---------------------

def suggest_filename(inp: GenerationInput, ext: str = "mp3") -> str:
    """Nome de arquivo seguro (sem espaços estranhos / acentos) com timestamp."""
    import re
    from datetime import datetime

    parts: list[str] = []
    style_slug = re.sub(r"[^a-zA-Z0-9]+", "_", inp.style.lower()).strip("_")
    if style_slug:
        parts.append(style_slug)
    if inp.duet_enabled:
        parts.append("dueto")
    if inp.is_instrumental:
        parts.append("instrumental")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts.append(stamp)
    base = "_".join(parts) or f"minimax_music_{stamp}"
    return f"{base}.{ext.lstrip('.')}"


# --------------------- Metadados do YouTube ---------------------

def build_youtube_metadata_prompt(
    style: str,
    duet_enabled: bool,
    duet_gender: str,
    duet_age: str,
    theme: str,
    lyrics: str = "",
) -> str:
    """Monta o prompt pedindo ao M3 metadados para o YouTube.

    O M3 retorna um JSON com `title`, `description` e `tags`.
    """
    desc_parts = [f"estilo musical '{style}'"]
    if duet_enabled:
        desc_parts.append(f"dueto ({duet_gender}, {duet_age.lower()})")
    if theme:
        desc_parts.append(f"tema: {theme}")
    contexto = ", ".join(desc_parts)

    letra_excerpt = ""
    if lyrics:
        # Pega as primeiras 6 linhas não-vazias pra dar contexto adicional
        linhas = [l.strip() for l in lyrics.splitlines() if l.strip()]
        letra_excerpt = "\n".join(linhas[:8])

    return (
        f"Voce e um especialista em marketing de musica brasileira no YouTube. "
        f"Gere metadados (titulo, descricao e tags) para uma musica com o "
        f"seguinte contexto:\n\n"
        f"Contexto: {contexto}\n"
        + (f"\nTrecho da letra (pra inspirar o titulo):\n{letra_excerpt}\n" if letra_excerpt else "")
        + f"\nREGRAS:\n"
        f"- TITULO: curto (max 60 caracteres), criativo, menciona o tema "
        f"principal. Pode incluir emojis musicais (max 1). Ex: "
        f"'Chuva de Verao - Sertanejo Universitario' ou 'Primeiro Amor - "
        f"Dueto Sertanejo'.\n"
        f"- DESCRICAO: 2 a 3 paragrafos em portugues brasileiro, calorosa, "
        f"com tom de quem compartilha algo pessoal. Mencione o estilo "
        f"musical, o tema, e a vibe. Termine com um call-to-action "
        f"('inscreva-se', 'deixe seu like', 'comente o que achou'). "
        f"Use no maximo 1000 caracteres.\n"
        f"- TAGS: 8 a 12 tags relevantes, separadas por virgula. Misture "
        f"tags de genero (sertanejo, pagode, pop), de nicho (sertanejo "
        f"universitario, romantico, dueto) e descritivas (musica nova, "
        f"lancamento, AI music, musica brasileira, clipe novo).\n\n"
        f"FORMATO DE SAIDA: responda APENAS com um JSON valido, no formato:\n"
        f'{{"title": "...", "description": "...", "tags": ["...", "...", "..."]}}\n'
        f"Sem nenhum texto antes ou depois do JSON. Sem blocos de codigo."
    )

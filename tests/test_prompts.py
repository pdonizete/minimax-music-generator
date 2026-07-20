"""Testes do mapeamento de escolhas → prompt."""

import pytest

from minimax_music.prompts import (
    build_prompt_and_lyrics,
    EXAMPLE_DUET_LYRICS,
    EXAMPLE_DUET_LYRICS_WITH_PREFIXES,
    GenerationInput,
    _has_structure_tags,
    _has_voice_prefixes,
    suggest_filename,
    voice_direction,
    voice_direction_clean,
)


def test_romantic_style_basic():
    inp = GenerationInput(
        style="Romântica",
        duet_enabled=False,
        lyrics_mode="user",
        user_lyrics="[Verse]\nEu te amo",
    )
    prompt, lyrics, lo, ins = build_prompt_and_lyrics(inp)
    assert "Romantic" in prompt
    assert lyrics == "[Verse]\nEu te amo"
    assert lo is False
    assert ins is False


def test_sertanejo_universitario_duet_young():
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Homem e mulher",
        duet_age="Jovens",
        lyrics_mode="user",
        user_lyrics="[Verse]\nteste",
    )
    prompt, lyrics, _, _ = build_prompt_and_lyrics(inp)
    assert "sertanejo" in prompt.lower()
    # Vozes LEAD distintas (não só "duet", que vira harmony)
    assert "female lead" in prompt.lower()
    assert "male lead" in prompt.lower()
    # Estrutura de chamada/resposta
    assert "verses" in prompt.lower() and "chorus" in prompt.lower()
    # Guarda-chuva: proíbe backing vocals mascarando o lead masculino
    assert "distinct lead vocals" in prompt.lower()
    assert "not one lead" in prompt.lower() or "not a solo" in prompt.lower()
    assert lyrics == "[Verse]\nteste"


def test_two_women_emphasized():
    inp = GenerationInput(
        style="Pagode",
        duet_enabled=True,
        duet_gender="Duas mulheres",
        duet_age="Adultos",
        lyrics_mode="user",
        user_lyrics="[Verse]\nopa",
    )
    prompt, _, _, _ = build_prompt_and_lyrics(inp)
    # Duas vozes LEAD femininas distintas
    assert "two" in prompt.lower() and "female lead" in prompt.lower()
    assert "distinct lead vocals" in prompt.lower()


def test_no_duet_no_gender_fragment():
    inp = GenerationInput(
        style="Pop",
        duet_enabled=False,
        lyrics_mode="user",
        user_lyrics="[Verse]\nola",
    )
    prompt, _, _, _ = build_prompt_and_lyrics(inp)
    # Sem dupla, não devemos ter o guarda-chuva de gênero
    assert "distinct lead vocals" not in prompt.lower()


def test_auto_lyrics_with_theme():
    inp = GenerationInput(
        style="Pop",
        duet_enabled=False,
        lyrics_mode="auto",
        lyrics_prompt="Um amor de verão na praia",
    )
    prompt, lyrics, lo, ins = build_prompt_and_lyrics(inp)
    assert lo is True
    assert lyrics == ""
    assert "summer" in prompt.lower() or "praia" in prompt.lower()


def test_instrumental_requires_prompt():
    inp = GenerationInput(
        style="Rock",
        duet_enabled=False,
        is_instrumental=True,
    )
    prompt, lyrics, lo, ins = build_prompt_and_lyrics(inp)
    assert ins is True
    assert "Instrumental" in prompt


def test_user_lyrics_empty_raises():
    inp = GenerationInput(
        style="Pop",
        duet_enabled=False,
        lyrics_mode="user",
        user_lyrics="",
    )
    with pytest.raises(ValueError):
        build_prompt_and_lyrics(inp)


def test_unknown_style_raises():
    inp = GenerationInput(
        style="Funk",
        duet_enabled=False,
        lyrics_mode="user",
        user_lyrics="x",
    )
    with pytest.raises(ValueError):
        build_prompt_and_lyrics(inp)


def test_prompt_within_2000_chars():
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Duas mulheres",
        duet_age="Adultos",
        lyrics_mode="auto",
        lyrics_prompt="A" * 2500,  # tema absurdamente longo
    )
    prompt, _, _, _ = build_prompt_and_lyrics(inp)
    assert len(prompt) <= 2000


def test_suggest_filename_safe_chars():
    inp = GenerationInput(style="Romântica", duet_enabled=True, is_instrumental=True)
    name = suggest_filename(inp, ext="mp3")
    assert name.endswith(".mp3")
    assert " " not in name
    assert "dueto" in name
    assert "instrumental" in name


# --- Plano B: letra roteirada ---

def test_has_structure_tags_recognizes_brackets():
    assert _has_structure_tags("[Verse]\nola")
    assert _has_structure_tags("[Chorus]\nola")
    assert _has_structure_tags("[Bridge]\nola")
    assert _has_structure_tags("[verse]\nola")  # case-insensitive
    assert not _has_structure_tags("apenas uma frase sem tag")
    assert not _has_structure_tags("")
    assert not _has_structure_tags(None)


def test_voice_direction_for_man_and_woman():
    vd = voice_direction("Homem e mulher").lower()
    assert "female" in vd
    assert "male" in vd
    # Nova sintaxe: nomes de cantores
    assert "ana" in vd
    assert "pedro" in vd
    # A instrução crítica: o male não pode virar harmony
    assert "harmonies" in vd
    assert "solo" in vd
    # Avisa que o nome NÃO deve ser cantado
    assert "not part" in vd or "is not" in vd or "label" in vd


def test_voice_direction_for_two_women():
    vd = voice_direction("Duas mulheres").lower()
    assert "female" in vd
    assert "both" in vd


def test_voice_direction_unknown_gender_returns_empty():
    assert voice_direction("Desconhecido") == ""


def test_plano_b_roteiro_ligado_quando_letra_tem_tags():
    """Com letra roteirada + dupla, o prompt deve ter 'voice direction'."""
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Homem e mulher",
        duet_age="Jovens",
        lyrics_mode="user",
        user_lyrics=EXAMPLE_DUET_LYRICS_WITH_PREFIXES,
    )
    prompt, lyrics, lo, ins = build_prompt_and_lyrics(inp)
    assert lyrics == EXAMPLE_DUET_LYRICS_WITH_PREFIXES
    assert lo is False  # lyrics_optimizer OFF
    assert ins is False
    # Voice direction no prompt
    p = prompt.lower()
    assert "voice direction" in p
    # Com prefixos Ana:/Pedro:, voice_direction com nomes é usada
    assert "ana" in p
    assert "pedro" in p
    # Guarda-chuva mantido
    assert "distinct lead vocals" in p


def test_plano_b_sem_letra_com_tags_nao_adiciona_voice_direction():
    """Sem letra roteirada, NÃO deve entrar a voice direction (gera via optimizer)."""
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Homem e mulher",
        duet_age="Jovens",
        lyrics_mode="auto",
        lyrics_prompt="algum tema",
    )
    prompt, _, lo, _ = build_prompt_and_lyrics(inp)
    assert lo is True  # optimizer ON
    p = prompt.lower()
    # Sem tags na "letra" (vazia), voice direction não entra
    assert "voice direction" not in p


def test_example_duet_lyrics_tem_2_verses_e_3_chorus():
    """Garantir que a letra exemplo tem a estrutura prometida."""
    assert _has_structure_tags(EXAMPLE_DUET_LYRICS)
    # 2 verses + 1 bridge + 3 choruses
    assert EXAMPLE_DUET_LYRICS.count("[Verse]") == 2
    assert EXAMPLE_DUET_LYRICS.count("[Bridge]") == 1
    assert EXAMPLE_DUET_LYRICS.count("[Chorus]") == 3


def test_override_lyrics_liga_voice_direction_no_modo_auto():
    """O worker usa override_lyrics para injetar a letra gerada pelo M3.

    Com override_lyrics (que tem tags) + dupla, o prompt deve ganhar
    'voice direction' mesmo em modo 'auto' (sem lyrics do usuário).
    """
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Homem e mulher",
        duet_age="Jovens",
        lyrics_mode="auto",          # normalmente optimizer=True
        lyrics_prompt="primeiro amor",
        user_lyrics="",              # usuário não forneceu letra
    )
    prompt, _, _, _ = build_prompt_and_lyrics(
        inp, override_lyrics=EXAMPLE_DUET_LYRICS_WITH_PREFIXES,
    )
    p = prompt.lower()
    assert "voice direction" in p
    # Com prefixos Ana:/Pedro:, voice_direction com nomes é usada
    assert "ana" in p
    assert "pedro" in p


def test_has_voice_prefixes_curto():
    assert _has_voice_prefixes("F: ola\nM: mundo")
    assert _has_voice_prefixes("F&M: juntos")
    assert not _has_voice_prefixes("[Verse]\nola")
    assert not _has_voice_prefixes("")


def test_has_voice_prefixes_nome_proprio():
    letra = (
        "[Verse]\n"
        "Ana: era numa cidade pequena\n"
        "Ana: a chuva de verao\n"
        "Ana: voce chegou\n"
        "Ana: e o meu coracao\n"
        "[Chorus]\n"
        "Pedro: vem comigo\n"
        "Pedro: ficar aqui\n"
        "Pedro: o nosso amor\n"
        "Pedro: e pra sempre"
    )
    assert _has_voice_prefixes(letra)


def test_has_voice_prefixes_letra_limpa():
    """Letra SEM prefixos (só tags) não deve ser considerada como tendo prefixos."""
    letra = (
        "[Verse]\n"
        "Era numa cidade pequena\n"
        "A chuva de verao chegou\n"
        "Voce olhou pra mim\n"
        "E o meu coracao disparou"
    )
    assert not _has_voice_prefixes(letra)


def test_voice_direction_clean_explica_via_tags():
    """voice_direction_clean deve instruir o modelo a alternar via tags."""
    vd = voice_direction_clean("Homem e mulher").lower()
    assert "[verse]" in vd
    assert "[chorus]" in vd
    assert "[bridge]" in vd
    assert "female" in vd
    assert "male" in vd
    # Instrução chave: ele deve usar as tags para saber quem canta
    assert "structural tags" in vd or "rely on" in vd or "no speaker tags" in vd


def test_build_prompt_letra_limpa_usa_voice_direction_clean():
    """Se override_lyrics não tem prefixos, deve usar voice_direction_clean."""
    letra_limpa = (
        "[Verse]\n"
        "Era uma vez numa cidade pequena\n"
        "Sob a chuva de verao\n"
        "Voce apareceu\n"
        "E mudou meu coracao\n\n"
        "[Chorus]\n"
        "Vem ficar comigo\n"
        "Aqui do meu lado\n"
        "Nosso amor e grande\n"
        "E eu te amo demais"
    )
    inp = GenerationInput(
        style="Sertanejo universitário",
        duet_enabled=True,
        duet_gender="Homem e mulher",
        duet_age="Jovens",
        lyrics_mode="auto",
        lyrics_prompt="primeiro amor",
    )
    prompt, _, _, _ = build_prompt_and_lyrics(inp, override_lyrics=letra_limpa)
    p = prompt.lower()
    # voice_direction_clean menciona structural tags / no speaker tags
    assert "structural tags" in p or "no speaker tags" in p
    # Mas NÃO menciona "Ana:" / "Pedro:" como speaker (pq a letra não tem)
    assert "ana:" not in p
    assert "pedro:" not in p

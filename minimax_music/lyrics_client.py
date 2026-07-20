"""Cliente para o modelo de texto MiniMax-M3 (chat completion, OpenAI-compatible).

Usado para gerar letras de música roteiradas (com tags [Verse]/[Chorus]/[Bridge])
antes de chamar o music-3.0. Isso resolve o problema do music-3.0
não respeitar bem a alternância de vozes em duetos.
"""

from __future__ import annotations

from typing import Any, Sequence
import re

import requests


_TAGS_RE = re.compile(
    r"<\s*think\s*>.*?<\s*/\s*think\s*>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_think_blocks(text: str) -> str:
    """Remove blocos <think>...</think> do texto (modelos reasoning como M3)."""
    if not text:
        return text
    return _TAGS_RE.sub("", text).strip()


class LyricsAPIError(Exception):
    """Erro do cliente de letras (MiniMax-M3)."""


class MiniMaxChatClient:
    """Cliente do endpoint de chat completion do Mavis (OpenAI-compatible)."""

    def __init__(self, chat_url: str, api_key: str, model: str = "MiniMax-M3",
                 timeout: int = 120):
        self.chat_url = chat_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: Sequence[dict[str, str]],
             max_tokens: int = 1500,
             temperature: float = 0.9) -> str:
        """Envia mensagens e devolve o conteúdo do assistant (string).

        Lança `LyricsAPIError` em caso de erro.
        """
        if not self.api_key:
            raise LyricsAPIError("API key não configurada.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            # M3 é um modelo "reasoning". Com reasoning_split=true, o
            # "pensamento" vai para o campo reasoning_content e o campo
            # content traz só a resposta final (a letra). Sem isso, o
            # thinking sai dentro de <think>...</think> e come os tokens
            # do content — a letra não chega.
            "reasoning_split": True,
        }
        try:
            resp = requests.post(
                self.chat_url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise LyricsAPIError(f"Falha de rede: {e}") from e

        if resp.status_code >= 400:
            raise LyricsAPIError(
                f"HTTP {resp.status_code}: {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except Exception as e:
            raise LyricsAPIError(f"Resposta não-JSON: {e}") from e

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LyricsAPIError(
                f"Resposta sem 'choices[0].message.content': {data!r}"
            ) from e

        if not isinstance(content, str):
            # Em algumas versões do M3, o content pode ser uma lista de partes.
            # Concatena os pedaços textuais, se houver.
            try:
                content = "".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            except Exception as e:
                raise LyricsAPIError(
                    f"Formato inesperado de 'content': {content!r}"
                ) from e

        # Belt-and-suspenders: se o content vier com <think>...</think>
        # (porque reasoning_split não foi respeitado pelo backend, ou o
        # modelo é M2.7/M2.5 que não suporta), removemos aqui também.
        content = _strip_think_blocks(content)

        return content


# --------------------- Prompts para gerar letra roteirada ---------------------

SYSTEM_PROMPT_DUET = (
    "Voce e um letrista profissional brasileiro. Voce escreve letras de "
    "musica em portugues brasileiro, com vocabulario simples, rimado, "
    "cantavel e emocional. Voce segue EXATAMENTE as instrucoes de "
    "estrutura e roteiros de vozes."
)


def _user_prompt_for_duet(
    style: str, gender: str, age: str, theme: str
) -> str:
    """Monta o prompt pedindo uma letra roteirada com NOMES de cantores
    no lugar de prefixos genéricos (F:/M:).

    O music-2.6 lê prefixos como parte da letra (canta "Efe" e "Eme").
    Usar nomes próprios como "Ana:" e "Pedro:" tem chance de ele entender
    como speaker ID em vez de conteúdo cantado.
    """
    # Quem canta cada seção
    if gender == "Homem e mulher":
        verse_name = "Ana"   # voz feminina
        chorus_name = "Pedro"  # voz masculina
        both_label = "Ana e Pedro"
    elif gender == "Duas mulheres":
        verse_name = "Ana"
        chorus_name = "Beatriz"
        both_label = "Ana e Beatriz"
    elif gender == "Dois homens":
        verse_name = "Pedro"
        chorus_name = "Lucas"
        both_label = "Pedro e Lucas"
    else:
        verse_name = "Ana"
        chorus_name = "Pedro"
        both_label = "Ana e Pedro"

    age_desc = {
        "Jovens": "linguagem jovem, fresca, simples",
        "Adultos": "linguagem adulta, equilibrada",
        "Idosos": "linguagem madura, sabia, com mais ponderacao",
    }.get(age, "")

    return (
        f"Escreva uma letra de musica completa em portugues brasileiro, "
        f"no estilo '{style}', com o tema/ideia: '{theme}'.\n\n"
        f"Esta musica e cantada em DUETO ({gender}, {age}). "
        f"{age_desc.capitalize() if age_desc else ''}.\n\n"
        f"REGRAS OBRIGATORIAS (siga EXATAMENTE):\n"
        f"- Estrutura, nesta ordem:\n"
        f"  [Intro] (uma linha: '(instrumental)')\n"
        f"  [Verse] (4 linhas, cada uma prefixada com '{verse_name}:')\n"
        f"  [Chorus] (4 linhas, cada uma prefixadas com '{chorus_name}:')\n"
        f"  [Verse] (4 linhas, cada uma prefixadas com '{verse_name}:')\n"
        f"  [Chorus] (4 linhas, cada uma prefixadas com '{chorus_name}:')\n"
        f"  [Bridge] (4 linhas, cada uma prefixada com '{both_label}:')\n"
        f"  [Chorus] (final, 4 a 6 linhas, prefixadas com '{both_label}:')\n\n"
        f"FORMATO DE CADA LINHA (CRUCIAL):\n"
        f"- Toda linha de letra DEVE comecar com o nome do cantor "
        f"seguido de dois-pontos e um espaco. Exemplo:\n"
        f"  {verse_name}: Era numa cidade pequena do interior\n"
        f"  {verse_name}: A chuva de verao trouxe o nosso amor\n"
        f"  {chorus_name}: Vem, pega na minha mao\n"
        f"  {both_label}: O verao vai voltar e a chuva vai molhar\n"
        f"- Os nomes significam: '{verse_name}:' = linha cantada por {verse_name} "
        f"(voz feminina). '{chorus_name}:' = linha cantada por {chorus_name} "
        f"(voz masculina). '{both_label}:' = cantada pelos dois juntos.\n"
        f"- Aplique o nome em TODAS as linhas (sem excecao).\n"
        f"- IMPORTANTE: o nome no prefixo NAO deve aparecer no meio da "
        f"linha. Ele serve apenas como marcador de quem canta; nao e "
        f"parte da letra cantada.\n"
        f"- Use \\n entre linhas. Use \\n\\n (linha em branco) entre secoes.\n"
        f"- NUNCA use aspas, apostrofos ou acentuacao grafica. Use apenas "
        f"letras ASCII basicas (sem acentos, sem cedilha, sem til).\n"
        f"- A letra deve rimar e ser cantavel. Faca o possivel para que "
        f"as palavras rimem nos versos e refrões.\n"
        f"- Nao inclua nenhum comentario, JSON ou explicacao. Apenas a "
        f"letra com tags e nomes de cantores nos prefixos."
    )


def _user_prompt_for_duet_clean(
    style: str, gender: str, age: str, theme: str
) -> str:
    """Monta o prompt pedindo uma letra LIMPA (sem prefixos) — só com
    tags estruturais [Verse]/[Chorus]/[Bridge].

    Estratégia alternativa: o music-2.6 demonstrou que respeita
    instruções de voz via prefixos (lê foneticamente). Hipótese: com
    um prompt bem feito, ele talvez respeite a estrutura [Verse]/
    [Chorus] também e faça a alternância de voz baseado nas tags,
    SEM precisar de prefixos na letra. Aí a letra sai limpa.
    """
    if gender == "Homem e mulher":
        voice_plan = (
            "Esta musica e cantada em DUETO entre uma voz feminina e uma "
            "voz masculina. As secoes [Verse] (versos) devem soar como se "
            "fossem cantadas pela voz FEMININA (sozinha). As secoes [Chorus] "
            "(refrões) devem soar como se fossem cantadas pela voz MASCULINA "
            "(sozinha). A secao [Bridge] e o [Chorus] final devem soar como "
            "se fossem cantados PELAS DUAS VOZES JUNTAS (dueto). "
        )
    elif gender == "Duas mulheres":
        voice_plan = (
            "Esta musica e cantada por DUAS vozes femininas distintas. "
            "Os [Verse] pela primeira voz feminina. Os [Chorus] pela segunda. "
            "O [Bridge] e o [Chorus] final pelas duas juntas. "
        )
    elif gender == "Dois homens":
        voice_plan = (
            "Esta musica e cantada por DUAS vozes masculinas distintas. "
            "Os [Verse] pela primeira voz masculina. Os [Chorus] pela segunda. "
            "O [Bridge] e o [Chorus] final pelas duas juntas. "
        )
    else:
        voice_plan = ""

    age_desc = {
        "Jovens": "linguagem jovem, fresca, simples",
        "Adultos": "linguagem adulta, equilibrada",
        "Idosos": "linguagem madura, sabia, com mais ponderacao",
    }.get(age, "")

    return (
        f"Escreva uma letra de musica completa em portugues brasileiro, "
        f"no estilo '{style}', com o tema/ideia: '{theme}'.\n\n"
        f"{voice_plan}"
        f"{age_desc.capitalize() if age_desc else ''}.\n\n"
        f"REGRAS OBRIGATORIAS (siga EXATAMENTE):\n"
        f"- Estrutura, nesta ordem:\n"
        f"  [Intro] (uma linha: '(instrumental)')\n"
        f"  [Verse] (4 linhas de letra — sem prefixo, sem nome)\n"
        f"  [Chorus] (4 linhas de letra — sem prefixo, sem nome)\n"
        f"  [Verse] (4 linhas de letra — sem prefixo, sem nome)\n"
        f"  [Chorus] (4 linhas de letra — sem prefixo, sem nome)\n"
        f"  [Bridge] (4 linhas de letra — sem prefixo, sem nome)\n"
        f"  [Chorus] (final, 4 a 6 linhas — sem prefixo, sem nome)\n\n"
        f"FORMATO DE CADA LINHA (CRUCIAL):\n"
        f"- As linhas de letra NAO devem ter prefixo nenhum (nada de 'Ana:', "
        f"'Pedro:', 'F:', 'M:', 'F&M:' ou similar).\n"
        f"- Apenas o conteudo da letra, sem marcadores no meio da linha.\n"
        f"- A letra deve rimar e ser cantavel.\n"
        f"- Use \\n entre linhas. Use \\n\\n (linha em branco) entre secoes.\n"
        f"- NUNCA use aspas, apostrofos ou acentuacao grafica. Use apenas "
        f"letras ASCII basicas (sem acentos, sem cedilha, sem til).\n"
        f"- Nao inclua nenhum comentario, JSON ou explicacao. Apenas a "
        f"letra com as tags [Intro]/[Verse]/[Chorus]/[Bridge]."
    )


def generate_duet_lyrics(
    client: MiniMaxChatClient,
    style: str,
    gender: str,
    age: str,
    theme: str,
) -> str:
    """Pede ao MiniMax-M3 uma letra roteirada para dueto.

    Retorna a string da letra (com tags). Lança `LyricsAPIError` em caso de erro.
    """
    if not theme or not theme.strip():
        raise LyricsAPIError("O tema/ideia da música é obrigatório.")
    user = _user_prompt_for_duet(style, gender, age, theme.strip())
    # Tentamos uma vez com max_tokens alto. Se vier vazio (o M3 gastou
    # todos os tokens pensando), fazemos retry com max_tokens ainda maior.
    last_err: str = ""
    for attempt, max_tok in enumerate((8000, 12000), start=1):
        try:
            content = client.chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_DUET},
                    {"role": "user", "content": user},
                ],
                # M3 é "reasoning": gasta tokens pensando. 8000 cabe o
                # thinking + a letra na maioria dos casos. Se vier vazio,
                # dobramos.
                max_tokens=max_tok,
                temperature=0.9,
            )
        except LyricsAPIError as e:
            last_err = str(e)
            continue
        if content and content.strip():
            return content.strip()
    raise LyricsAPIError(
        f"M3 retornou resposta vazia após 2 tentativas. {last_err}"
    )


def generate_clean_duet_lyrics(
    client: MiniMaxChatClient,
    style: str,
    gender: str,
    age: str,
    theme: str,
) -> str:
    """Pede ao MiniMax-M3 uma letra LIMPA (sem prefixos) para dueto.

    Estratégia alternativa: sem prefixos nas linhas (nada de "Ana:" ou
    "Pedro:"). A letra sai apenas com as tags [Intro]/[Verse]/[Chorus]/
    [Bridge] e o conteúdo das linhas. A voice direction no prompt do
    music-2.6 explica a estrutura de vozes baseada nas tags.

    Hipótese: como o music-2.6 demonstrou que respeita instruções
    estruturais (F:/M:/F&M: fonéticos), talvez ele respeite a
    estrutura [Verse]/[Chorus] também — e faça a alternância de voz
    baseado só nas tags + prompt bem feito. Aí a letra sai limpa.
    """
    if not theme or not theme.strip():
        raise LyricsAPIError("O tema/ideia da música é obrigatório.")
    user = _user_prompt_for_duet_clean(style, gender, age, theme.strip())
    last_err: str = ""
    for max_tok in (8000, 12000):
        try:
            content = client.chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_DUET},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tok,
                temperature=0.9,
            )
        except LyricsAPIError as e:
            last_err = str(e)
            continue
        if content and content.strip():
            return content.strip()
    raise LyricsAPIError(
        f"M3 retornou resposta vazia após 2 tentativas. {last_err}"
    )


# --------------------- Metadados do YouTube ---------------------

def _extract_json(text: str) -> dict:
    """Extrai um JSON do texto (caso o M3 inclua lixo em volta)."""
    if not text:
        raise ValueError("Conteúdo vazio")
    text = text.strip()
    # Tenta parse direto
    try:
        import json
        return json.loads(text)
    except Exception:
        pass
    # Procura o primeiro {...} na string
    import json
    import re
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"Não achei JSON no conteúdo: {text[:200]!r}")
    return json.loads(m.group(0))


def generate_youtube_metadata(
    client: MiniMaxChatClient,
    style: str,
    duet_enabled: bool,
    duet_gender: str,
    duet_age: str,
    theme: str,
    lyrics: str = "",
) -> dict:
    """Pede ao MiniMax-M3 metadados para o YouTube (título, descrição, tags).

    Retorna um dict com chaves: title, description, tags (list[str]).
    Lança `LyricsAPIError` em caso de erro.
    """
    from .prompts import build_youtube_metadata_prompt
    user = build_youtube_metadata_prompt(
        style=style, duet_enabled=duet_enabled,
        duet_gender=duet_gender, duet_age=duet_age,
        theme=theme, lyrics=lyrics,
    )
    last_err = ""
    for max_tok in (2000, 4000):
        try:
            content = client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Voce e um assistente que responde APENAS em JSON "
                            "valido, sem nenhum texto adicional."
                        ),
                    },
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tok,
                temperature=0.8,
            )
        except LyricsAPIError as e:
            last_err = str(e)
            continue
        if content and content.strip():
            try:
                data = _extract_json(content)
            except (ValueError, Exception) as e:
                last_err = f"Falha ao parsear JSON: {e}"
                continue
            # Normaliza
            if not isinstance(data, dict):
                last_err = "Resposta não é um dict"
                continue
            return {
                "title": str(data.get("title", "") or "").strip(),
                "description": str(data.get("description", "") or "").strip(),
                "tags": [
                    str(t).strip() for t in (data.get("tags") or []) if t
                ],
            }
    raise LyricsAPIError(
        f"M3 não retornou metadados válidos após 2 tentativas. {last_err}"
    )

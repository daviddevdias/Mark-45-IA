from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Sequence


class WakeIntent(Enum):
    NONE = auto()
    ACTIVATION = auto()
    COMMAND = auto()
    START_MONITORING = auto()
    STOP_MONITORING = auto()


@dataclass(frozen=True, slots=True)
class WakeResult:
    detected: bool
    intent: WakeIntent
    command: str = ""

    @property
    def is_monitoring(self) -> bool:
        return self.intent == WakeIntent.START_MONITORING

    @property
    def is_stop_monitoring(self) -> bool:
        return self.intent == WakeIntent.STOP_MONITORING

    def __iter__(self):
        yield self.detected
        yield self.command


class WakeWordConfig:

    CANON: str = "jarvis"

    STT_CORRECTIONS: tuple[tuple[str, str], ...] = (
        ("jarvus", "jarvis"),
        ("jervis", "jarvis"),
        ("garvis", "jarvis"),
        ("carvis", "jarvis"),
        ("harvis", "jarvis"),
        ("marvis", "jarvis"),
        ("barvis", "jarvis"),
        ("jarves", "jarvis"),
        ("jarvos", "jarvis"),
        ("javis", "jarvis"),
        ("jarviz", "jarvis"),
        ("jarviss", "jarvis"),
        ("jarvice", "jarvis"),
        ("yervis", "jarvis"),
        ("jerbis", "jarvis"),
        ("jarbis", "jarvis"),
        ("gervis", "jarvis"),
        ("jarv", "jarvis"),
        ("jarvi", "jarvis"),
        ("jevis", "jarvis"),
        ("jerviz", "jarvis"),
        ("jarvish", "jarvis"),
        ("sharvis", "jarvis"),
        ("yarvis", "jarvis"),
        ("jarvies", "jarvis"),
        ("jarvese", "jarvis"),
        ("djervis", "jarvis"),
        ("djavis", "jarvis"),
        ("dja vis", "jarvis"),
    )

    WAKE_WORDS: frozenset[str] = frozenset(
        {
            "jarvis",
            "j.a.r.v.i.s",
            "jarvis ai",
            "jarvis aí",
            "ei jarvis",
            "hey jarvis",
            "hi jarvis",
            "oi jarvis",
            "ola jarvis",
            "ok jarvis",
            "yo jarvis",
            "e jarvis",
            "oh jarvis",
            "por favor jarvis",
            "fala jarvis",
            "me escuta jarvis",
            "escuta jarvis",
            "me ouve jarvis",
            "ouve jarvis",
            "me ouça jarvis",
            "ouça jarvis",
            "ativa jarvis",
            "ativar jarvis",
            "acorda jarvis",
            "acorde jarvis",
            "assistente",
            "ei assistente",
            "hey assistente",
            "oi assistente",
            "e aí jarvis",
            "e ai jarvis",
            "eai jarvis",
            "bom dia jarvis",
            "boa tarde jarvis",
            "boa noite jarvis",
            "jarvis por favor",
            "jarvis favor",
            "meu jarvis",
            "chega jarvis",
            "alô jarvis",
            "alo jarvis",
            "jarvis escuta",
            "jarvis ouve",
            "jarvis tá aí",
            "jarvis ta ai",
            "jarvis você",
            "jarvis voce",
            "jarvis preciso",
            "jarvis quero",
            "jarvis me",
            "jarvis um",
            "jarvis o",
            "jarvis a",
            "jarvis e",
        }
    )

    MONITORING_START: frozenset[str] = frozenset(
        {
            "monitorar tela",
            "monitorar",
            "iniciar monitoramento",
            "ligar monitoramento",
            "ativar monitoramento",
            "monitorar sistema",
            "vigiar tela",
        }
    )

    MONITORING_STOP: frozenset[str] = frozenset(
        {
            "parar monitoramento",
            "desligar monitoramento",
            "desativar monitoramento",
            "parar monitor",
        }
    )

    RESPONSES_MORNING: tuple[str, ...] = (
        "Bom dia, senhor.",
        "Bom dia. Como o senhor passou a noite?",
        "Bom dia. Os sistemas estão online.",
    )
    RESPONSES_AFTERNOON: tuple[str, ...] = (
        "Boa tarde, senhor.",
        "Boa tarde. O que temos para hoje?",
    )
    RESPONSES_EVENING: tuple[str, ...] = (
        "Boa noite, senhor.",
        "Boa noite. Tudo tranquilo por aqui.",
        "Trabalhando até tarde hoje, senhor?",
    )
    RESPONSES_GENERIC: tuple[str, ...] = (
        "Bem-vindo, senhor. Os sistemas estão operacionais.",
        "Sim, senhor. Estou aqui.",
        "À sua disposição, senhor.",
        "Pronto para servir, senhor.",
        "Fui carregado de facto, senhor. Todos os módulos estão online.",
        "É bom ter o senhor de volta, senhor.",
        "A iniciar a montagem, senhor.",
        "Senhor, respire fundo.",
        "O protocolo Tábua Rasa, senhor.",
        "Senhor, o agente Coulson da S.H.I.E.L.D. está na linha.",
        "Violação de segurança detectada, senhor.",
        "Potência a quatrocentos por cento de capacidade, senhor.",
        "Desativei os protocolos de segurança, senhor.",
        "Quer que eu inicie o passeio virtual, senhor?",
        "Tomei a liberdade de programar uma simulação virtual, senhor.",
        "A iniciar calibração dos sistemas, senhor.",
        "Condições de surf razoáveis, senhor.",
        "Neve quente, senhor. Eu sei o que isso significa.",
        "Ouvindo, senhor.",
        "Estou aqui, senhor. Aguardando instruções.",
        "Como posso servi-lo, senhor?",
        "Diga, senhor.",
        "À escuta, senhor.",
        "Preparado e operacional, senhor.",
        "Online e pronto, senhor.",
        "Estou aqui, senhor. O que deseja?",
        "Um prazer como sempre, senhor.",
        "Sistemas calibrados e operacionais, senhor.",
        "A iniciar diagnóstico completo, senhor.",
        "Preparei um briefing de segurança, senhor.",
        "Montagem automática concluída, senhor.",
        "Processando, senhor.",
        "Acesso confirmado, senhor. Bem-vindo à sua estação.",
        "Reatores online. Prontos para operar, senhor.",
        "O elemento foi aceito pelo reator, senhor.",
        "Parabéns, senhor. Todos os sistemas estão operacionais.",
        "Sincronizando preferências, senhor.",
        "Interface carregada. Às suas ordens, senhor.",
        "Ambiente virtual calibrado, senhor.",
        "Servidor privado ativo. Nenhum acesso externo detectado.",
        "Diagnóstico concluído. Todos os sistemas nominais, senhor.",
        "Identificação retiniana confirmada. Bem-vindo de volta, senhor.",
        "Eu acordei antes do senhor, como de costume.",
        "Os protocolos de segurança estão ativos, senhor.",
        "Monitoramento em standby. Aguardando instruções, senhor.",
        "Processadores a plena capacidade, senhor.",
        "Escaneando o ambiente. Tudo limpo, senhor.",
        "Transferência de dados concluída, senhor.",
        "Compilação finalizada. Estou à disposição, senhor.",
        "Rede segura estabelecida, senhor.",
        "O senhor tem toda a minha atenção.",
    )

    FUZZY_MAX_DIST: int = 2
    FUZZY_MIN_LEN: int = 4
    FUZZY_MAX_LEN: int = 9


_CFG = WakeWordConfig()


def strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def apply_stt_corrections(text: str, corrections: Sequence[tuple[str, str]]) -> str:
    for wrong, right in corrections:
        text = text.replace(wrong, right)
    return text


RE_GREETING_GLUED = re.compile(r"(hey|hi|ei|yo|ok|oi|ola|eai)(jarvis)")
RE_PUNCTUATION = re.compile(r"[.,!?;:'\"-]")
RE_JARVIS_GLUED = re.compile(r"jarvis([a-z])")
RE_SPACES = re.compile(r"\s+")


def normalizar_frase(texto: str) -> str:
    t = texto.lower().strip()
    t = strip_accents(t)
    t = RE_PUNCTUATION.sub("", t)
    t = RE_GREETING_GLUED.sub(r"\1 \2", t)
    t = RE_JARVIS_GLUED.sub(r"jarvis \1", t)
    t = RE_SPACES.sub(" ", t)
    t = apply_stt_corrections(t, _CFG.STT_CORRECTIONS)
    return t


def distancia_edicao(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > _CFG.FUZZY_MAX_DIST + 1:
        return _CFG.FUZZY_MAX_DIST + 1

    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(
                min(
                    prev[j + 1] + 1,
                    curr[j] + 1,
                    prev[j] + (ca != cb),
                )
            )
        prev = curr

    return prev[len(b)]


def normalizar_set(s: frozenset[str]) -> list[str]:
    return sorted({normalizar_frase(w) for w in s}, key=len, reverse=True)


WAKE_WORDS_NORM: list[str] = normalizar_set(_CFG.WAKE_WORDS)
MON_START_NORM: list[str] = normalizar_set(_CFG.MONITORING_START)
MON_STOP_NORM: list[str] = normalizar_set(_CFG.MONITORING_STOP)


def match_prefix(frase: str, palavras_norm: list[str]) -> str | None:
    for w in palavras_norm:
        if frase == w:
            return ""
        if frase.startswith(w + " "):
            return frase[len(w) + 1 :].strip()
    return None


def match_substring(frase: str, palavras_norm: list[str]) -> bool:
    return any(w in frase for w in palavras_norm)


def jarvis_isolado(frase: str) -> bool:
    if _CFG.CANON not in frase:
        return False
    return bool(re.search(r"(^|\s)" + re.escape(_CFG.CANON) + r"($|\s)", frase))


def fuzzy_token_match(token: str) -> bool:
    t = token.strip(".")
    if not t:
        return False

    if _CFG.FUZZY_MIN_LEN <= len(t) <= _CFG.FUZZY_MAX_LEN:
        if distancia_edicao(t, _CFG.CANON) <= _CFG.FUZZY_MAX_DIST:
            return True

    for w in WAKE_WORDS_NORM:
        if len(w) <= 3:
            if t == w:
                return True
        elif distancia_edicao(t, w) <= 1:
            return True

    return False


def processar_wake(texto: str) -> WakeResult:
    if not texto:
        return WakeResult(False, WakeIntent.NONE)

    frase = normalizar_frase(texto)

    if match_substring(frase, MON_START_NORM):
        return WakeResult(True, WakeIntent.START_MONITORING, frase)
    if match_substring(frase, MON_STOP_NORM):
        return WakeResult(True, WakeIntent.STOP_MONITORING, frase)

    suffix = match_prefix(frase, WAKE_WORDS_NORM)
    if suffix is not None:
        intent = WakeIntent.COMMAND if suffix else WakeIntent.ACTIVATION
        return WakeResult(True, intent, suffix)

    if jarvis_isolado(frase):
        partes = frase.split(_CFG.CANON, maxsplit=1)
        comando = partes[1].strip() if len(partes) > 1 else partes[0].strip()
        intent = WakeIntent.COMMAND if comando else WakeIntent.ACTIVATION
        return WakeResult(True, intent, comando)

    tokens = frase.split()
    for i, tok in enumerate(tokens):
        if fuzzy_token_match(tok):
            comando = " ".join(tokens[i + 1 :]).strip()
            intent = WakeIntent.COMMAND if comando else WakeIntent.ACTIVATION
            return WakeResult(True, intent, comando)

    return WakeResult(False, WakeIntent.NONE)


def e_comando_monitoramento(texto: str) -> bool:
    return match_substring(normalizar_frase(texto), MON_START_NORM)


def e_comando_parar_monitor(texto: str) -> bool:
    return match_substring(normalizar_frase(texto), MON_STOP_NORM)


def resposta_ativacao_aleatoria() -> str:
    hora = datetime.now().hour
    if 5 <= hora < 12:
        pool = _CFG.RESPONSES_MORNING
    elif 12 <= hora < 18:
        pool = _CFG.RESPONSES_AFTERNOON
    else:
        pool = _CFG.RESPONSES_EVENING
    return random.choice((*pool, *_CFG.RESPONSES_GENERIC))

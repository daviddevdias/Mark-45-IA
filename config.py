import json
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
API_DIR    = BASE_DIR / "api"
ASSETS_DIR = BASE_DIR / "assets"
API_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

def ler_json(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return {}

def salvar_json(nome_arquivo: str, dados: dict) -> bool:
    caminho   = API_DIR / nome_arquivo
    existente = ler_json(caminho)
    if isinstance(existente, dict):
        existente.update(dados)
    else:
        existente = dados
    try:
        caminho.write_text(
            json.dumps(existente, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False

def carregar_tudo() -> dict:
    arquivos = ["config_smart.json", "api_keys.json", "config_core.json", "notas.json"]
    dados = {}
    for nome in arquivos:
        dados.update(ler_json(API_DIR / nome))
    return dados

def definir_valor_ui(chave: str, valor: str):
    nomes = {
        "gemini":               "GEMINI_API_KEY",
        "qwen":                 "QWEN_API_KEY",
        "spotify_id":           "SPOTIFY_ID",
        "spotify_sec":          "SPOTIFY_SECRET",
        "smartthings":          "SMARTTHINGS_TOKEN",
        "smartthings_tv_id":    "SMARTTHINGS_TV_DEVICE_ID",
        "nome_mestre":          "NOME_MESTRE",
        "voz":                  "voz_atual",
        "device_index":         "DEVICE_INDEX",
        "openweather_api_key":  "OPENWEATHER_API_KEY",
        "telegram_token":       "TELEGRAM_TOKEN",
        "telegram_auth_token":  "TELEGRAM_AUTH_TOKEN",
        "deepgram_api_key":     "DEEPGRAM_API_KEY",
        "whisper_model":        "WHISPER_MODEL",
    }
    alvo = nomes.get(chave, chave)

    if alvo == "DEVICE_INDEX":
        try:
            globals()["DEVICE_INDEX"] = int(valor)
        except ValueError:
            globals()["DEVICE_INDEX"] = 0
        return

    globals()[alvo if alvo in globals() else chave] = valor

    if chave == "nome_mestre":
        try:
            from storage.memory_manager import update_memory
            update_memory({"identity": {"mestre": {"value": str(valor).strip()[:256]}}})
        except Exception:
            pass

    if chave == "cidade_padrao":
        try:
            from storage.memory_manager import update_memory
            update_memory({"preferences": {"cidade": {"value": str(valor).strip()[:256]}}})
        except Exception:
            pass

voz_ui_cb = None

def registrar_callback_voz_painel(cb):
    global voz_ui_cb
    voz_ui_cb = cb

def notificar_voz_painel(on: bool, vol: float = 1.0):
    if voz_ui_cb:
        try:
            voz_ui_cb(bool(on), float(vol))
        except Exception:
            pass

def recarregar_identidade_painel():
    dados = ler_json(API_DIR / "config_core.json")
    nm = dados.get("nome_mestre")
    if nm and str(nm).strip():
        globals()["NOME_MESTRE"] = str(nm).strip()[:256]
    cp = dados.get("cidade_padrao")
    if cp is not None:
        globals()["cidade_padrao"] = str(cp).strip()[:256]

cfg = carregar_tudo()

QWEN_API_KEY             = cfg.get("qwen", "")
GEMINI_API_KEY           = cfg.get("gemini", "")
CURRENT_MODEL            = cfg.get("current_model", "qwen/qwen2.5-vl-72b-instruct")
BASE_URL                 = "https://openrouter.ai/api/v1"

SPOTIFY_ID               = cfg.get("spotify_id", "")
SPOTIFY_SECRET           = cfg.get("spotify_sec", "")
SPOTIFY_REDIRECT_URI     = "http://127.0.0.1:8888/callback"

SMARTTHINGS_TOKEN        = cfg.get("smartthings", "")
SMARTTHINGS_TV_DEVICE_ID = str(cfg.get("smartthings_tv_id", "")).strip()

TELEGRAM_TOKEN           = cfg.get("telegram_token", "")
TELEGRAM_AUTH_TOKEN      = cfg.get("telegram_auth_token", "")
TELEGRAM_ALLOWED_IDS     = cfg.get("telegram_allowed_ids", [])

OPENWEATHER_API_KEY      = cfg.get("openweather_api_key", "")

DEEPGRAM_API_KEY         = cfg.get("deepgram_api_key", "")
WHISPER_MODEL            = cfg.get("whisper_model", "small")

NOME_MESTRE              = cfg.get("nome_mestre", "Chefe")
voz_atual                = cfg.get("voz_atual", cfg.get("voz", "pt-BR-AntonioNeural"))
DEVICE_INDEX             = cfg.get("device_index", 1)
tema_ativo               = cfg.get("tema_ativo", "MIDNIGHT_MINIMAL")
notas                    = cfg.get("notas", "")
cidade_padrao            = cfg.get("cidade_padrao", "")

voz_referencia           = str(ASSETS_DIR / "voz_clone.wav")
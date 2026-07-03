
import json
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "modelos"
API_DIR = BASE_DIR / "api"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

VOZES_CATALOGO = {
    "1": (
        "pt_BR-faber-medium",
        "Faber — a que você já tem (calorosa, mas meio robótica em frases longas)",
    ),
    "2": (
        "pt_BR-cadu-medium",
        "Cadu — tom neutro/limpo, é a voz 'padrão' recomendada pro pt_BR",
    ),
    "3": ("pt_BR-jeff-medium", "Jeff — registro mais alto"),
    "4": (
        "pt_BR-edresson-low",
        "Edresson — mais leve/rápida, qualidade um pouco menor",
    ),
}

# Vozes da comunidade (fora do catálogo oficial) — baixadas direto da URL
VOZES_MANUAIS = {
    "5": (
        "pt_BR-miro-high",
        "Miro — PT-BR em qualidade HIGH (melhor que as medium acima), grave e mais 'cheia'",
        "https://huggingface.co/csukuangfj/vits-piper-pt_BR-miro-high/resolve/main/pt_BR-miro-high.onnx",
        "https://huggingface.co/csukuangfj/vits-piper-pt_BR-miro-high/resolve/main/pt_BR-miro-high.onnx.json",
    ),
    "6": (
        "razo",
        "Razo — PT-BR fine-tunada pra soar natural em assistente de IA/tech",
        "https://huggingface.co/Lucasllfs/Razo-piper-voice/resolve/main/razo.onnx",
        "https://huggingface.co/Lucasllfs/Razo-piper-voice/resolve/main/razo.onnx.json",
    ),
    "7": (
        "jarvis-medium",
        "JARVIS (filmes, EM INGLÊS) — qualidade medium, sotaque britânico grave",
        "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx",
        "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx.json",
    ),
    "8": (
        "jarvis-high",
        "JARVIS (filmes, EM INGLÊS) — qualidade HIGH, a mais parecida com o original",
        "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx",
        "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/high/jarvis-high.onnx.json",
    ),
}

FRASE_TESTE_PT = (
    "Boa noite, senhor. Todos os sistemas estão operacionais. " "Como posso ajudar?"
)
FRASE_TESTE_EN = (
    "Good evening, sir. All systems are fully operational. " "How may I assist you?"
)


def _baixar_arquivo(url: str, destino: Path):
    print(f"  Baixando {destino.name} ...")
    urllib.request.urlretrieve(url, destino)


def garantir_baixado(nome_voz: str) -> Path:
    onnx = MODELS_DIR / f"{nome_voz}.onnx"
    json_cfg = MODELS_DIR / f"{nome_voz}.onnx.json"
    if onnx.exists() and json_cfg.exists():
        return onnx

    # Catálogo oficial: usa o downloader do próprio piper
    for _, (nome, _desc) in VOZES_CATALOGO.items():
        if nome == nome_voz:
            print(f"  Baixando {nome_voz} (catálogo oficial) ...")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "piper.download_voices",
                    nome_voz,
                    "--data-dir",
                    str(MODELS_DIR),
                ],
                check=True,
            )
            return onnx

    # Comunidade: baixa direto da URL
    for _, (nome, _desc, url_onnx, url_json) in VOZES_MANUAIS.items():
        if nome == nome_voz:
            _baixar_arquivo(url_onnx, onnx)
            _baixar_arquivo(url_json, json_cfg)
            return onnx

    raise ValueError(f"Voz desconhecida: {nome_voz}")


def falar_com_voz(nome_voz: str, texto: str):
    from piper import PiperVoice, SynthesisConfig
    import sounddevice as sd
    import soundfile as sf

    onnx = garantir_baixado(nome_voz)
    voice = PiperVoice.load(str(onnx))
    syn_config = SynthesisConfig(normalize_audio=True)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    caminho = tmp.name
    tmp.close()
    with wave.open(caminho, "wb") as wav_file:
        voice.synthesize_wav(texto, wav_file, syn_config=syn_config)

    data, fs = sf.read(caminho, dtype="float32")
    sd.play(data, fs)
    sd.wait()


def salvar_escolha(nome_voz: str):
    caminho = API_DIR / "config_core.json"
    dados = {}
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    dados["tts_engine"] = "piper"
    dados["piper_model"] = f"{nome_voz}.onnx"
    API_DIR.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"\n✅ Salvo em {caminho} — o Jarvis já vai abrir com '{nome_voz}' na próxima vez."
    )


def main():
    print("=== Comparador de vozes Piper ===\n")
    print("--- Catálogo oficial (PT-BR) ---")
    for chave, (nome, desc) in VOZES_CATALOGO.items():
        print(f"  [{chave}] {desc}")
    print("\n--- Comunidade ---")
    for chave, (nome, desc, *_url) in VOZES_MANUAIS.items():
        print(f"  [{chave}] {desc}")
    print(
        "\n  ⚠ As opções 7 e 8 (JARVIS) são treinadas em INGLÊS. Elas vão falar\n"
        "    frases em português com sotaque estranho (o fonemizador é en-GB).\n"
        "    Servem melhor se você mudar o Jarvis pra responder em inglês, ou\n"
        "    só pra ouvir o quão perto ficou da voz original do filme.\n"
    )
    print("  [t] Tocar TODAS em sequência")
    print("  [q] Sair sem mudar nada\n")

    todas = {**VOZES_CATALOGO, **{k: (v[0], v[1]) for k, v in VOZES_MANUAIS.items()}}

    while True:
        escolha = (
            input("Digite o número pra ouvir (ou 't' pra tocar todas, 'q' pra sair): ")
            .strip()
            .lower()
        )

        if escolha == "q":
            print("Saindo sem alterar a configuração.")
            return

        if escolha == "t":
            for chave, (nome, desc) in todas.items():
                frase = FRASE_TESTE_EN if nome.startswith("jarvis") else FRASE_TESTE_PT
                print(f"\n▶ Tocando: {desc}")
                falar_com_voz(nome, frase)
            continue

        if escolha not in todas:
            print("Opção inválida.")
            continue

        nome, desc = todas[escolha]
        frase = FRASE_TESTE_EN if nome.startswith("jarvis") else FRASE_TESTE_PT
        print(f"\n▶ Tocando: {desc}")
        falar_com_voz(nome, frase)

        usar = (
            input(f"Quer deixar '{nome}' como voz padrão do Jarvis? (s/n): ")
            .strip()
            .lower()
        )
        if usar == "s":
            salvar_escolha(nome)
            return


if __name__ == "__main__":
    main()

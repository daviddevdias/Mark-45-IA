import asyncio, os, queue, threading, time, re, tempfile
import edge_tts, pygame, speech_recognition as sr
import sounddevice as sd
import scipy.io.wavfile as wav
import config

audio_io_lock = threading.RLock()
mic_lock = threading.Lock()
mic_cmd: queue.Queue = queue.Queue()
mic_rpy: queue.Queue = queue.Queue()
falando = False
interrompido = False
barge_stop_event = threading.Event()
barge_thread: threading.Thread | None = None
mic_thread: threading.Thread | None = None


def criar_reconhecedor() -> sr.Recognizer:
    r = sr.Recognizer()
    r.pause_threshold = 0.3
    r.non_speaking_duration = 0.1
    r.dynamic_energy_threshold = True
    return r


reconhecedor = criar_reconhecedor()


def limpar_texto(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (t or "").lower().strip())).strip()


def reproduzir_sync(arquivo: str):
    global falando, interrompido
    with audio_io_lock:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(arquivo)
        pygame.mixer.music.play()
        falando, interrompido = True, False
        iniciar_barge_in()
        while pygame.mixer.music.get_busy():
            if interrompido:
                break
            time.sleep(0.05)
        pygame.mixer.music.stop()
    parar_barge_in()
    falando = False
    try:
        config.notificar_voz_painel(False, 1.0)
    except:
        pass


async def falar(texto: str):
    if not texto.strip():
        return
    arquivo = os.path.join(config.ASSETS_DIR, "output.mp3")
    try:
        if os.path.exists(arquivo):
            os.remove(arquivo)
        await edge_tts.Communicate(texto, config.voz_atual).save(arquivo)
        print(f"[Jarvis]: {texto}")
        await asyncio.get_running_loop().run_in_executor(None, reproduzir_sync, arquivo)
    except Exception as e:
        print(f"Erro fala: {e}")


def capturar_audio() -> str:
    fs = 16000
    print("[Status]: Escutando...")
    try:
        audio = sd.rec(int(6 * fs), samplerate=fs, channels=1, dtype="int16")
        sd.wait()
        tmp_path = tempfile.mktemp(suffix=".wav")
        wav.write(tmp_path, fs, audio)
        with sr.AudioFile(tmp_path) as source:
            audio_data = reconhecedor.record(source)
            t = reconhecedor.recognize_google(audio_data, language="pt-BR")
            os.remove(tmp_path)
            res = limpar_texto(t)
            print(f"[Você]: {res}")
            return res
    except Exception as e:
        print(f"Erro captura: {e}")
        return ""


def barge_loop():
    while not barge_stop_event.is_set():
        if not falando or interrompido:
            break
        try:
            audio = sd.rec(int(1 * 16000), samplerate=16000, channels=1, dtype="int16")
            sd.wait()
            tmp_path = tempfile.mktemp(suffix=".wav")
            wav.write(tmp_path, 16000, audio)
            with sr.AudioFile(tmp_path) as source:
                txt = limpar_texto(
                    reconhecedor.recognize_google(reconhecedor.record(source), language="pt-BR")
                )
            os.remove(tmp_path)
            if txt:
                interromper_voz()
                break
        except:
            continue


def iniciar_barge_in():
    global barge_thread
    barge_stop_event.clear()
    if not barge_thread or not barge_thread.is_alive():
        barge_thread = threading.Thread(target=barge_loop, daemon=True)
        barge_thread.start()


def parar_barge_in():
    barge_stop_event.set()


def run_mic_loop():
    while True:
        try:
            mic_cmd.get()
            mic_rpy.put(capturar_audio())
        except:
            time.sleep(0.5)


def ensure_mic_thread():
    global mic_thread
    if not mic_thread or not mic_thread.is_alive():
        mic_thread = threading.Thread(target=run_mic_loop, daemon=True)
        mic_thread.start()


async def ouvir_comando() -> str:
    ensure_mic_thread()
    mic_cmd.put(True)
    return await asyncio.get_running_loop().run_in_executor(None, mic_rpy.get)


def interromper_voz():
    global interrompido
    interrompido = True
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()

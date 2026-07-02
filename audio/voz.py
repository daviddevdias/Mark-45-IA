import asyncio, os, queue, threading, time, re, tempfile
from collections import deque
import edge_tts, pygame
import sounddevice as sd
import numpy as np
import config

audio_io_lock = threading.RLock()
mic_lock = threading.RLock()
mic_cmd: queue.Queue = queue.Queue()
mic_rpy: queue.Queue = queue.Queue()
falando = False
interrompido = False
barge_thread: threading.Thread | None = None
mic_thread: threading.Thread | None = None
barge_cmd: queue.Queue = queue.Queue()
ouvindo_comando = threading.Event()

# ---------------- Whisper ----------------
_whisper_model = None
_whisper_lock = threading.Lock()


def obter_whisper():
    global _whisper_model
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel

                print("[Whisper]: carregando modelo...")
                _whisper_model = WhisperModel(
                    getattr(config, "WHISPER_MODEL", "small"),
                    device=getattr(config, "WHISPER_DEVICE", "cpu"),
                    compute_type=getattr(config, "WHISPER_COMPUTE", "int8"),
                    cpu_threads=os.cpu_count() or 4,
                )
                print("[Whisper]: pronto")
    return _whisper_model


def limpar_texto(t: str) -> str:
    return re.sub(
        r"\s+", " ", re.sub(r"[^\w\s]", " ", (t or "").lower().strip())
    ).strip()


def transcrever(audio: np.ndarray, fs: int = 16000, beam_size: int = 1) -> str:
    try:
        modelo = obter_whisper()
        audio_f32 = audio.astype(np.float32) / 32768.0
        segments, _ = modelo.transcribe(
            audio_f32,
            language="pt",
            beam_size=beam_size,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=250, speech_pad_ms=400),
            condition_on_previous_text=False,
            temperature=0.0,
            initial_prompt="Jarvis. Comandos de voz em português: jarvis, abrir, tocar, pesquisar, parar.",
        )
        texto = " ".join(s.text.strip() for s in segments)
        return limpar_texto(texto)
    except Exception as e:
        print(f"Erro Whisper: {e}")
        return ""


def rms_audio(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def gravar_chunk(fs: int, tamanho: int) -> np.ndarray:
    with mic_lock:
        audio = sd.rec(tamanho, samplerate=fs, channels=1, dtype="int16")
        sd.wait()
    return audio.copy()


def calibrar_ruido(fs: int = 16000, dur: float = 0.4) -> float:
    audio = gravar_chunk(fs, int(dur * fs))
    return rms_audio(audio.flatten())


# ---------------- TTS ----------------
def reproduzir_sync(arquivo: str):
    global falando, interrompido
    with audio_io_lock:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
        pygame.mixer.music.load(arquivo)
        time.sleep(0.05)
        pygame.mixer.music.play()
        falando, interrompido = True, False
        try:
            config.notificar_voz_painel(True, 1.0)
        except:
            pass
        while pygame.mixer.music.get_busy():
            if interrompido:
                break
            time.sleep(0.05)
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    falando = False
    try:
        config.notificar_voz_painel(False, 1.0)
    except:
        pass


async def falar(texto: str):
    if not texto.strip():
        return
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        arquivo = tmp.name
        tmp.close()
        await edge_tts.Communicate(texto, config.voz_atual).save(arquivo)
        print(f"[Jarvis]: {texto}")
        await asyncio.get_running_loop().run_in_executor(None, reproduzir_sync, arquivo)
    except Exception as e:
        print(f"Erro fala: {e}")
    finally:
        try:
            if os.path.exists(arquivo):
                os.unlink(arquivo)
        except:
            pass


# ---------------- Captura de comando ----------------
def capturar_audio() -> str:
    fs = 16000
    chunk_dur = 0.2
    chunk_len = int(chunk_dur * fs)
    max_chunks = int(12 / chunk_dur)  # até ~12s de fala
    silencio_max = int(1.0 / chunk_dur)  # ~1s de silêncio encerra
    pre_roll = int(0.4 / chunk_dur)  # guarda 0.4s antes do gatilho

    print("[Status]: Escutando...")
    ouvindo_comando.set()
    try:
        piso = calibrar_ruido(fs)
        limiar = max(piso * 2.5, 150)

        pre_buf = deque(maxlen=pre_roll)
        buf = []
        gravando = False
        silencio_atual = 0

        for _ in range(max_chunks):
            frame = gravar_chunk(fs, chunk_len)
            rms = rms_audio(frame.flatten())

            if not gravando:
                pre_buf.append(frame)
                if rms > limiar:
                    gravando = True
                    buf.extend(pre_buf)
                    pre_buf.clear()
            else:
                buf.append(frame)
                if rms > limiar:
                    silencio_atual = 0
                else:
                    silencio_atual += 1
                    if silencio_atual >= silencio_max:
                        break

            if interrompido:
                break

        if not buf:
            return ""

        all_audio = np.concatenate(buf).flatten()
        texto = transcrever(all_audio, fs)
        if texto:
            print(f"[Você]: {texto}")
        return texto
    except Exception as e:
        print(f"Erro captura: {e}")
        return ""
    finally:
        ouvindo_comando.clear()


# ---------------- Wake word / barge-in ----------------
def wake_listener():
    fs = 16000
    chunk = int(0.3 * fs)
    buf = []
    ultima_stt = 0

    try:
        while ouvindo_comando.is_set():
            time.sleep(0.1)
        piso = calibrar_ruido(fs)
        limiar = max(piso * 2.0, 100)
    except Exception:
        limiar = 100

    while True:
        try:
            if ouvindo_comando.is_set():
                buf = []
                time.sleep(0.1)
                continue

            audio_flat = gravar_chunk(fs, chunk).flatten()
            rms = rms_audio(audio_flat)

            if rms < limiar:
                buf = []
                continue

            buf.append(audio_flat.copy())

            agora = time.time()
            tempo_buf = len(buf) * 0.3

            # Único checkpoint a cada ~2.0s: detecta wake word E faz barge-in se falando
            if tempo_buf >= 2.0 and (agora - ultima_stt) >= 1.5:
                all_audio = np.concatenate(buf)
                txt = transcrever(all_audio, fs, beam_size=2)
                ultima_stt = agora
                buf = []
                if txt:
                    from tasks.wake import processar_wake

                    ativo, _ = processar_wake(txt)
                    if ativo:
                        if falando:
                            interromper_voz()
                        barge_cmd.put(txt)
        except:
            time.sleep(0.05)


_wake_thread_started = False


def iniciar_wake_listener():
    global _wake_thread_started, barge_thread
    if _wake_thread_started:
        return
    _wake_thread_started = True
    barge_thread = threading.Thread(target=wake_listener, daemon=True)
    barge_thread.start()


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
    try:
        return barge_cmd.get_nowait()
    except queue.Empty:
        pass
    ensure_mic_thread()
    mic_cmd.put(True)
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, mic_rpy.get)
    return res


def interromper_voz():
    global interrompido
    interrompido = True
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
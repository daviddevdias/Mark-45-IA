import asyncio
import os
import queue
import threading
import time

import edge_tts
import pygame
import speech_recognition as sr

import config

import re
import tempfile
from typing import Optional




audio_io_lock = threading.RLock()

mic_lock = threading.Lock()



mic_cmd: queue.Queue = queue.Queue()
mic_rpy: queue.Queue = queue.Queue()



mic_thread: threading.Thread | None = None





sleep_event = threading.Event()
falando = False
interrompido = False
barge_stop_event = threading.Event()
barge_thread: threading.Thread | None = None





def criar_reconhecedor() -> sr.Recognizer:
    r = sr.Recognizer()


    r.pause_threshold = 0.55
    r.non_speaking_duration = 0.25
    r.dynamic_energy_threshold = False
    r.dynamic_energy_adjustment_damping = 0.15
    r.dynamic_energy_ratio = 1.7
    return r


reconhecedor = criar_reconhecedor()

_whisper_model = None
_whisper_lock = threading.Lock()


def get_whisper_model():



    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        try:
            from faster_whisper import WhisperModel  

            nome_modelo = getattr(config, "WHISPER_MODEL", "") or "small"
            _whisper_model = WhisperModel(nome_modelo, device="cpu", compute_type="int8")
            return _whisper_model
        except Exception:
            return None


def limpar_texto_stt(texto: str) -> str:




    t = (texto or "").strip().lower()
    if not t:
        return ""



    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def reconhecer_google(audio: sr.AudioData) -> str:
    return reconhecedor.recognize_google(audio, language="pt-BR")


def reconhecer_whisper(audio: sr.AudioData) -> str:
    model = get_whisper_model()
    if model is None:
        return ""

    wav = audio.get_wav_data(convert_rate=16000, convert_width=2)
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(wav)
            tmp_path = f.name

        segments, _info = model.transcribe(
            tmp_path,
            language="pt",
            vad_filter=True,
            beam_size=5,
        )
        texto = " ".join((seg.text or "").strip() for seg in segments).strip()
        return texto
    except Exception:
        return ""
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass







def suspender_pygame_mixer_para_capture():
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            pygame.mixer.quit()
    except Exception:
        pass







def normalizar_indice_microfone(idx):
    try:
        return int(idx) if idx is not None and int(idx) >= 0 else None
    except Exception:
        return None







def ui_falar(on, vol=1.0):
    try:
        config.notificar_voz_painel(on, vol)
    except Exception:
        pass







def interromper_voz():
    global interrompido

    interrompido = True
    ui_falar(False)
    sleep_event.set()

    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except Exception:
        pass







def barge_loop():


    idx = normalizar_indice_microfone(getattr(config, "DEVICE_INDEX", None))
    rec = criar_reconhecedor()
    rec.pause_threshold = 0.4
    rec.non_speaking_duration = 0.2

    kwargs = {}
    if idx is not None:
        kwargs["device_index"] = idx


    if not mic_lock.acquire(timeout=2.0):
        return

    try:
        with sr.Microphone(**kwargs) as source:
            mic_lock.release()         
            try:
                rec.adjust_for_ambient_noise(source, duration=0.15)
            except Exception:
                pass

            while not barge_stop_event.is_set():
                if not falando or interrompido:
                    break
                try:
                    audio = rec.listen(source, timeout=0.6, phrase_time_limit=1.5)
                    try:
                        txt = limpar_texto_stt(rec.recognize_google(audio, language="pt-BR"))
                    except Exception:
                        txt = ""
                    if txt:
                        print(f"ouvido durante fala: {txt}")
                        interromper_voz()
                        break
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    break
    except Exception:
        try:
            mic_lock.release()
        except RuntimeError:
            pass







def iniciar_listener_interrupcao():
    global barge_thread

    barge_stop_event.clear()

    if barge_thread and barge_thread.is_alive():
        return

    barge_thread = threading.Thread(target=barge_loop, daemon=True)
    barge_thread.start()







def parar_listener_interrupcao():
    barge_stop_event.set()







def reproduzir_sync(arquivo):
    global falando, interrompido

    with audio_io_lock:

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        try:
            pygame.mixer.music.load(arquivo)
            pygame.mixer.music.play()
        except:
            return

        falando = True
        interrompido = False
        sleep_event.clear()

        iniciar_listener_interrupcao()

        while pygame.mixer.music.get_busy():
            if interrompido:
                break
            sleep_event.wait(0.1)

        pygame.mixer.music.stop()
        try:
            pygame.mixer.music.unload()
        except:
            pass

    parar_listener_interrupcao()

    falando = False
    ui_falar(False)







async def falar(texto):
    if not texto.strip():
        return

    arquivo = os.path.join(config.ASSETS_DIR, "output.mp3")

    try:
        if os.path.exists(arquivo):
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
            os.remove(arquivo)
    except:
        pass

    try:
        communicate = edge_tts.Communicate(texto, config.voz_atual)
        await communicate.save(arquivo)
    except Exception:
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, reproduzir_sync, arquivo)







def captura_sync():
    idx = normalizar_indice_microfone(getattr(config, "DEVICE_INDEX", None))

    with audio_io_lock:
        suspender_pygame_mixer_para_capture()


    parar_listener_interrupcao()
    if barge_thread and barge_thread.is_alive():
        barge_thread.join(timeout=4.0)

    time.sleep(0.15)

    print("\nEscutando...\n")

    try:
        kwargs = {}
        if idx is not None:
            kwargs["device_index"] = idx

        with mic_lock:
            with sr.Microphone(**kwargs) as source:
                reconhecedor.adjust_for_ambient_noise(source, duration=0.8)
                try:
                    audio = reconhecedor.listen(source, timeout=10, phrase_time_limit=9)
                except sr.WaitTimeoutError:
                    return ""

        texto = ""
        try:
            texto = limpar_texto_stt(reconhecer_google(audio))
        except Exception:
            texto = ""

        if not texto:
            texto = limpar_texto_stt(reconhecer_whisper(audio))

        print(f"ouvido: {texto}")
        return texto

    except Exception as e:
        print(f"Erro na captura: {e}")
        return ""







def run_mic_loop():
    while True:
        try:
            mic_cmd.get()
            resultado = captura_sync()
            mic_rpy.put(resultado)
        except Exception:
            time.sleep(1)







def ensure_mic_thread():
    global mic_thread

    if mic_thread and mic_thread.is_alive():
        return

    mic_thread = threading.Thread(target=run_mic_loop, daemon=True)
    mic_thread.start()







def ouvir_sync_queued():
    ensure_mic_thread()

    mic_cmd.put(True)

    try:
        return mic_rpy.get(timeout=40)
    except Exception:
        return ""




def listar_microfones() -> list:
    """Lista microfones disponíveis de forma segura, respeitando o mic_lock
    para evitar acesso concorrente ao PyAudio (causa access violation no Windows)."""
    acquired = mic_lock.acquire(timeout=5.0)
    if not acquired:

        return []
    try:
        mics = sr.Microphone.list_microphone_names()
        return [f"{i}: {nome}" for i, nome in enumerate(mics)]
    except Exception:
        return []
    finally:
        mic_lock.release()



async def ouvir_comando():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, ouvir_sync_queued)
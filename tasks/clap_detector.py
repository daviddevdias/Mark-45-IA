
import time
import numpy as np
import sounddevice as sd
import threading
import logging
import config

log = logging.getLogger("jarvis.clap_detector")

SAMPLE_RATE = 16000
CHUNK_SIZE = 4096
FREQUENCY_RANGE = (800, 4000)
CLAP_THRESHOLD = 5.0
MIN_CLAP_DURATION = 0.1
MAX_CLAP_DURATION = 0.5
CLAP_DEBOUNCE = 1.0

clap_callback = None
clap_ativo = False
clap_thread = None
ultima_palma = 0.0


def registrar_callback_palma(cb):
    
    global clap_callback
    clap_callback = cb
    log.info("Callback de palma registrado")


def analisar_palma(audio_chunk: np.ndarray) -> bool:
    
    if len(audio_chunk) == 0:
        return False
    
    energia_total = np.mean(audio_chunk ** 2)
    
    if energia_total < 0.01:
        return False
    
    try:
        fft = np.abs(np.fft.fft(audio_chunk))
        freqs = np.fft.fftfreq(len(audio_chunk), 1 / SAMPLE_RATE)
        
        freq_mask = (freqs > FREQUENCY_RANGE[0]) & (freqs < FREQUENCY_RANGE[1])
        energia_palma = np.mean(fft[freq_mask] ** 2)
        
        if energia_palma > energia_total * CLAP_THRESHOLD:
            return True
    except Exception as e:
        log.debug(f"Erro na FFT: {e}")
    
    return False


def escutar_palmas():
    
    global clap_callback
    
    global ultima_palma
    log.info("🎤 Detector de palmas iniciado")
    
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=CHUNK_SIZE,
            dtype=np.float32,
            latency='low'
        )
        
        with stream:
            while clap_ativo:
                try:
                    audio_data, _ = stream.read(CHUNK_SIZE)
                    audio_data = audio_data.flatten()
                    
                    if analisar_palma(audio_data):
                        agora = time.time()
                        if agora - ultima_palma < CLAP_DEBOUNCE:
                            continue
                        ultima_palma = agora
                        log.info("🎯 PALMA DETECTADA!")
                        
                        if clap_callback:
                            try:
                                clap_callback()
                            except Exception as e:
                                log.error(f"Erro ao chamar callback: {e}")
                
                except Exception as e:
                    log.debug(f"Erro ao ler áudio: {e}")
    
    except Exception as e:
        log.error(f"Erro crítico no detector de palmas: {e}")
    
    log.info("Detector de palmas encerrado")


def iniciar_detector():
    
    global clap_ativo, clap_thread
    
    if clap_ativo:
        log.warning("Detector já está rodando")
        return
    
    clap_ativo = True
    clap_thread = threading.Thread(
        target=escutar_palmas,
        daemon=True,
        name="clap_detector"
    )
    clap_thread.start()
    log.info("🚀 Detector de palmas iniciado")


def parar_detector():
    
    global clap_ativo, clap_thread
    
    clap_ativo = False
    if clap_thread:
        clap_thread.join(timeout=2)
    log.info("⏹️ Detector de palmas parado")

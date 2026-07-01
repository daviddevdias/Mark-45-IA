"""
Detector de palmas (clap detection) para ativação do Jarvis.
Usa análise de frequência e intensidade de áudio para detectar palmas.
"""
import time
import numpy as np
import sounddevice as sd
import threading
import logging
import config

log = logging.getLogger("jarvis.clap_detector")

# ===== CONFIGURAÇÕES =====
SAMPLE_RATE = 16000  # Hz
CHUNK_SIZE = 4096  # amostras
FREQUENCY_RANGE = (800, 4000)  # Hz - onde palmas são detectadas
CLAP_THRESHOLD = 5.0  # Multiplicador de energia
MIN_CLAP_DURATION = 0.1  # segundos
MAX_CLAP_DURATION = 0.5  # segundos
CLAP_DEBOUNCE = 1.0  # segundos entre detecções

clap_callback = None
clap_ativo = False
clap_thread = None
ultima_palma = 0.0


def registrar_callback_palma(cb):
    """Registra callback para quando palma é detectada"""
    global clap_callback
    clap_callback = cb
    log.info("Callback de palma registrado")


def analisar_palma(audio_chunk: np.ndarray) -> bool:
    """
    Detecta palma no chunk de áudio.
    
    Heurística:
    - Pico de energia alta
    - Energia concentrada em faixa de frequência típica de palmas
    - Duração curta
    """
    if len(audio_chunk) == 0:
        return False
    
    # Calcula energia total
    energia_total = np.mean(audio_chunk ** 2)
    
    if energia_total < 0.01:  # Ruído baixo demais
        return False
    
    # FFT para análise de frequência
    try:
        fft = np.abs(np.fft.fft(audio_chunk))
        freqs = np.fft.fftfreq(len(audio_chunk), 1 / SAMPLE_RATE)
        
        # Pega apenas frequências positivas
        freq_mask = (freqs > FREQUENCY_RANGE[0]) & (freqs < FREQUENCY_RANGE[1])
        energia_palma = np.mean(fft[freq_mask] ** 2)
        
        # Se energia em faixa de palma é muito maior que fundo
        if energia_palma > energia_total * CLAP_THRESHOLD:
            return True
    except Exception as e:
        log.debug(f"Erro na FFT: {e}")
    
    return False


def escutar_palmas():
    """
    Loop que escuta por palmas continuamente.
    Rodá em thread separada.
    """
    global clap_callback
    
    global ultima_palma
    log.info("🎤 Detector de palmas iniciado")
    
    try:
        # Cria stream de áudio
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
                    # Lê um chunk de áudio
                    audio_data, _ = stream.read(CHUNK_SIZE)
                    audio_data = audio_data.flatten()
                    
                    # Detecta palma
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
    """Inicia o detector de palmas em uma thread"""
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
    """Para o detector de palmas"""
    global clap_ativo, clap_thread
    
    clap_ativo = False
    if clap_thread:
        clap_thread.join(timeout=2)
    log.info("⏹️ Detector de palmas parado")

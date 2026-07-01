import asyncio, inspect, os, platform, sqlite3, psutil, socket, threading, time
from datetime import datetime

_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "monitor.db"
)
ALERTAS = {
    "tempo": False,
    "bateria": False,
    "temp": False,
    "cpu": False,
    "rede": False,
    "ram": False,
    "disco": False,
}
INTERVALO_S, TEMP_CRITICA, TEMP_OK, BAT_CRITICA, DISCO_CRITICO, DISCO_OK = (
    10,
    82,
    70,
    20,
    90.0,
    80.0,
)
CPU_CRITICO = 90
RAM_CRITICO = 90
falar_callback, monitor_async_loop = None, None
_historico_stats: list[dict] = []
MAX_HISTORICO = 360


def conectar_banco_monitor() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    c = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=5)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute(
        "CREATE TABLE IF NOT EXISTS alertas (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, tipo TEXT NOT NULL, mensagem TEXT NOT NULL, valor REAL)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, cpu REAL, ram REAL, disk REAL, temp REAL, net_sent REAL, net_recv REAL, processes INTEGER)"
    )
    c.commit()
    return c


def registrar_log_alerta(tipo: str, mensagem: str, valor: float = 0.0):
    try:
        with conectar_banco_monitor() as c:
            c.execute(
                "INSERT INTO alertas (ts, tipo, mensagem, valor) VALUES (?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), tipo, mensagem, valor),
            )
            c.commit()
    except:
        pass


def registrar_metricas_no_banco(cpu, ram, disk, temp, net_sent, net_recv, processes):
    try:
        with conectar_banco_monitor() as c:
            c.execute(
                "INSERT INTO metrics (ts, cpu, ram, disk, temp, net_sent, net_recv, processes) VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), cpu, ram, disk, temp, net_sent, net_recv, processes),
            )
            c.commit()
    except:
        pass


def registrar_falar(fn):
    global falar_callback
    falar_callback = fn


def registrar_loop_monitor_voz(loop):
    global monitor_async_loop
    monitor_async_loop = loop


def falar(texto: str):
    if not falar_callback:
        return
    try:
        if inspect.iscoroutinefunction(falar_callback):
            if monitor_async_loop and not monitor_async_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    falar_callback(texto), monitor_async_loop
                )
        else:
            falar_callback(texto)
    except:
        pass


_net_io_last = None
_net_io_time = None


def check_internet() -> bool:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3.0):
            return True
    except:
        return False


def obter_temperatura_cpu() -> float | None:
    try:
        t = psutil.sensors_temperatures()
        if t:
            for n in ("k10temp", "coretemp", "cpu_thermal", "acpitz", "zenpower"):
                if n in t and t[n]:
                    return t[n][0].current
            for n, e in t.items():
                if e and "cpu" in n.lower():
                    return e[0].current
    except:
        pass
    if platform.system().lower() == "windows":
        try:
            import wmi

            sensores = wmi.WMI(namespace="root\\OpenHardwareMonitor").Sensor()
            temps = [
                float(s.Value)
                for s in sensores
                if getattr(s, "SensorType", "") == "Temperature"
                and "cpu" in getattr(s, "Name", "").lower()
            ]
            if temps:
                return max(temps)
        except:
            pass
    return None


def _raiz_disco() -> str:
    if platform.system().lower() == "windows":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def obter_velocidade_rede() -> tuple[float, float]:
    global _net_io_last, _net_io_time
    agora = time.time()
    io = psutil.net_io_counters()
    if _net_io_last is None:
        _net_io_last = io
        _net_io_time = agora
        return 0.0, 0.0
    dt = agora - _net_io_time
    if dt < 1:
        return 0.0, 0.0
    sent = (io.bytes_sent - _net_io_last.bytes_sent) / dt
    recv = (io.bytes_recv - _net_io_last.bytes_recv) / dt
    _net_io_last = io
    _net_io_time = agora
    return sent, recv


def listar_top_processos(limite: int = 5) -> list[dict]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except:
            pass
    procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    return procs[:limite]


def obter_uptime() -> str:
    try:
        segundos = int(time.time() - psutil.boot_time())
        dias = segundos // 86400
        horas = (segundos % 86400) // 3600
        minutos = (segundos % 3600) // 60
        if dias > 0:
            return f"{dias}d {horas}h {minutos}m"
        return f"{horas}h {minutos}m"
    except:
        return "N/A"


def checar_rede():
    o = check_internet()
    if not o and not ALERTAS["rede"]:
        registrar_log_alerta("rede", "Conexão perdida.")
        falar("Atenção, Chefe. Perda de conexão detectada.")
        ALERTAS["rede"] = True
    elif o and ALERTAS["rede"]:
        registrar_log_alerta("rede", "Conexão restaurada.")
        falar("Conexão restaurada. Sistemas online.")
        ALERTAS["rede"] = False


def checar_temperatura():
    t = obter_temperatura_cpu()
    if t is None:
        return
    if t >= TEMP_CRITICA and not ALERTAS["temp"]:
        registrar_log_alerta("temperatura", f"CPU a {t}°C", t)
        falar(f"Alerta térmico. {int(t)} graus.")
        ALERTAS["temp"] = True
    elif t < TEMP_OK:
        ALERTAS["temp"] = False


def checar_bateria():
    b = psutil.sensors_battery()
    if not b:
        return
    if b.percent < BAT_CRITICA and not b.power_plugged and not ALERTAS["bateria"]:
        registrar_log_alerta("bateria", f"Bateria em {b.percent}%", b.percent)
        falar(f"Bateria em {int(b.percent)} por cento.")
        ALERTAS["bateria"] = True
    elif b.power_plugged:
        ALERTAS["bateria"] = False


def checar_disco():
    try:
        u = psutil.disk_usage(_raiz_disco()).percent
    except:
        return
    if u >= DISCO_CRITICO and not ALERTAS["disco"]:
        registrar_log_alerta("disco", f"Disco em {u}%", u)
        falar(f"Disco em {int(u)} por cento. Libere espaço.")
        ALERTAS["disco"] = True
    elif u < DISCO_OK:
        ALERTAS["disco"] = False


def checar_cpu_ram():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    if cpu >= CPU_CRITICO and not ALERTAS["cpu"]:
        registrar_log_alerta("cpu", f"CPU em {cpu}%", cpu)
        falar(f"CPU em {int(cpu)} por cento.")
        ALERTAS["cpu"] = True
    elif cpu < CPU_CRITICO - 10:
        ALERTAS["cpu"] = False
    if ram >= RAM_CRITICO and not ALERTAS["ram"]:
        registrar_log_alerta("ram", f"RAM em {ram}%", ram)
        falar(f"RAM em {int(ram)} por cento.")
        ALERTAS["ram"] = True
    elif ram < RAM_CRITICO - 10:
        ALERTAS["ram"] = False


def monitorar_proativo():
    while True:
        for fn in [checar_rede, checar_temperatura, checar_bateria, checar_disco, checar_cpu_ram]:
            try:
                fn()
            except:
                pass
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage(_raiz_disco()).percent
            temp = obter_temperatura_cpu() or 0.0
            sent, recv = obter_velocidade_rede()
            procs = len(psutil.pids())
            registrar_metricas_no_banco(cpu, ram, disk, temp, sent, recv, procs)
            stats = {
                "cpu": cpu,
                "ram": ram,
                "disk": disk,
                "temp": temp,
                "uptime": obter_uptime(),
                "processos": procs,
                "internet": check_internet(),
                "bateria": (psutil.sensors_battery().percent if psutil.sensors_battery() else None),
                "carregando": (psutil.sensors_battery().power_plugged if psutil.sensors_battery() else None),
                "rede_sent_kbps": round(sent / 1024, 1),
                "rede_recv_kbps": round(recv / 1024, 1),
            }
            _historico_stats.append(stats)
            if len(_historico_stats) > MAX_HISTORICO:
                _historico_stats.pop(0)
        except:
            pass
        time.sleep(INTERVALO_S)


def iniciar_sentinela():
    threading.Thread(target=monitorar_proativo, daemon=True, name="Sentinela").start()


def status_hardware() -> dict:
    cached = _historico_stats[-1] if _historico_stats else {}
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "temp_cpu": cached.get("temp"),
        "disco_percent": cached.get("disk"),
        "bateria_percent": cached.get("bateria"),
        "carregando": cached.get("carregando"),
        "uptime": cached.get("uptime", obter_uptime()),
        "processos": cached.get("processos"),
        "internet": cached.get("internet"),
        "rede_sent_kbps": cached.get("rede_sent_kbps"),
        "rede_recv_kbps": cached.get("rede_recv_kbps"),
        "top_processos": [],
        "alertas": {k: v for k, v in ALERTAS.items() if v},
    }


def status_resumo_texto() -> str:
    s = status_hardware()
    linhas = [
        "Status do sistema:",
        f"CPU: {s['cpu_percent']}% | RAM: {s['ram_percent']}%",
    ]
    if s["temp_cpu"]:
        linhas.append(f"Temperatura: {s['temp_cpu']}°C")
    if s["disco_percent"] is not None:
        linhas.append(f"Disco: {s['disco_percent']}%")
    if s["bateria_percent"] is not None:
        plug = "carregando" if s["carregando"] else "bateria"
        linhas.append(f"Bateria: {s['bateria_percent']}% ({plug})")
    linhas.append(f"Processos: {s['processos']}")
    linhas.append(f"Uptime: {s['uptime']}")
    linhas.append(f"Internet: {'conectado' if s['internet'] else 'offline'}")
    if s["rede_recv_kbps"] > 0 or s["rede_sent_kbps"] > 0:
        linhas.append(f"Rede: down {s['rede_recv_kbps']}Kbps up {s['rede_sent_kbps']}Kbps")
    if s["alertas"]:
        linhas.append(f"Alertas ativos: {', '.join(s['alertas'].keys())}")
    return "\n".join(linhas)


def alertas_recentes(limite: int = 50) -> list[dict]:
    try:
        with conectar_banco_monitor() as c:
            return [
                dict(zip(("ts", "tipo", "mensagem", "valor"), r))
                for r in c.execute(
                    "SELECT ts, tipo, mensagem, valor FROM alertas ORDER BY id DESC LIMIT ?",
                    (limite,),
                ).fetchall()
            ]
    except:
        return []


def historico_metricas(limite: int = 60) -> list[dict]:
    try:
        with conectar_banco_monitor() as c:
            return [
                dict(zip(("ts", "cpu", "ram", "disk", "temp", "net_sent", "net_recv", "processes"), r))
                for r in c.execute(
                    "SELECT ts, cpu, ram, disk, temp, net_sent, net_recv, processes FROM metrics ORDER BY id DESC LIMIT ?",
                    (limite,),
                ).fetchall()
            ]
    except:
        return []

import asyncio, json, os, platform, socket, subprocess, threading, time
from datetime import datetime
import psutil

def escanear_rede() -> list[dict]:
    dispositivos = []
    try:
        if platform.system().lower() == "windows":
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
            for linha in out.splitlines():
                partes = linha.strip().split()
                if len(partes) >= 3 and partes[0].count(".") == 3:
                    ip, mac = partes[0], partes[1]
                    if mac.count("-") == 5 or mac.count(":") == 5:
                        try:
                            host = socket.getfqdn(ip)
                        except:
                            host = ip
                        dispositivos.append({"ip": ip, "mac": mac, "hostname": host})
        else:
            out = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=10).stdout
            for linha in out.splitlines():
                partes = linha.strip().split()
                if len(partes) >= 3 and partes[0].count(".") == 3:
                    ip, mac = partes[0], partes[2]
                    if mac.count(":") == 5:
                        try:
                            host = socket.getfqdn(ip)
                        except:
                            host = ip
                        dispositivos.append({"ip": ip, "mac": mac, "hostname": host})
    except:
        pass
    return dispositivos


TRACKER_KEYWORDS = [
    "google-analytics", "googlesyndication", "googleadservices", "doubleclick",
    "facebook", "fbcdn", "instagram", "whatsapp",
    "scorecardresearch", "quantserve", "outbrain", "taboola",
    "hotjar", "optimizely", "crazyegg", "mouseflow",
    "adserver", "adsystem", "adnxs", "rubiconproject",
    "criteo", "casalemedia", "openx", "pubmatic",
]

def _resolver_dns(dominio: str) -> list[str]:
    try:
        return list(set([socket.gethostbyname(dominio)]))
    except:
        return []

def verificar_privacidade() -> list[dict]:
    tracker_ativo = []
    vistos = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.raddr and conn.raddr.ip:
                ip = conn.raddr.ip
                if ip in vistos:
                    continue
                vistos.add(ip)
                try:
                    host = socket.getfqdn(ip)
                except:
                    host = ip
                for kw in TRACKER_KEYWORDS:
                    if kw in host.lower():
                        tracker_ativo.append({
                            "ip": ip,
                            "host": host,
                            "tracker": kw,
                            "pid": conn.pid or 0,
                            "tipo": "tracker",
                        })
                        break
    except:
        pass
    return tracker_ativo


SUSPECT_PORTS = {22, 23, 3389, 5900, 5901, 21, 3306, 5432, 6379, 27017, 445, 135, 137, 139}

def monitorar_conexoes() -> dict:
    resultado = {"total": 0, "suspeitas": [], "portas_abertas": []}
    portas_vistas = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            resultado["total"] += 1
            if conn.status == "LISTEN":
                lp = conn.laddr.port
                portas_vistas[lp] = {"porta": lp, "pid": conn.pid, "status": "LISTEN"}
            if conn.raddr and conn.raddr.port:
                rp = conn.raddr.port
                if rp in SUSPECT_PORTS:
                    try:
                        proc = psutil.Process(conn.pid).name() if conn.pid else "?"
                    except:
                        proc = "?"
                    resultado["suspeitas"].append({
                        "ip": conn.raddr.ip,
                        "porta": rp,
                        "pid": conn.pid,
                        "processo": proc,
                    })
        resultado["portas_abertas"] = sorted(portas_vistas.values(), key=lambda x: x["porta"])
    except:
        pass
    return resultado


def status_firewall() -> dict:
    info = {"ativo": False, "regras": []}
    try:
        if platform.system().lower() == "windows":
            out = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles"],
                capture_output=True, text=True, timeout=10
            ).stdout
            for linha in out.splitlines():
                if "State" in linha:
                    info["ativo"] = "ON" in linha.upper()
                    break
            out2 = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True, text=True, timeout=15
            ).stdout
            for linha in out2.splitlines():
                if "Rule Name:" in linha:
                    nome = linha.split("Rule Name:")[-1].strip()
                    if nome:
                        info["regras"].append({"nome": nome})
        else:
            info["ativo"] = True
            out = subprocess.run(["iptables", "-L", "-n"], capture_output=True, text=True, timeout=5).stdout
            info["regras"] = [{"linha": l.strip()} for l in out.splitlines() if l.strip()]
    except:
        pass
    return info


def coletar_tudo() -> dict:
    dados = {}
    try:
        dados["dispositivos_rede"] = escanear_rede()
    except:
        dados["dispositivos_rede"] = []
    try:
        dados["trackers"] = verificar_privacidade()
    except:
        dados["trackers"] = []
    try:
        dados["conexoes"] = monitorar_conexoes()
    except:
        dados["conexoes"] = {"total": 0, "suspeitas": [], "portas_abertas": []}
    try:
        dados["firewall"] = status_firewall()
    except:
        dados["firewall"] = {"ativo": False, "regras": []}
    return dados


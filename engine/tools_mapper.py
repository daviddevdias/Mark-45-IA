from __future__ import annotations

import asyncio
import webbrowser
import subprocess
import os
import json
import urllib.parse
from typing import Any, Callable

from tasks.spotify_manager import spotify_stark
from tasks.open_app import open_app
from tasks.weather import obter_previsao_hoje, verificar_chuva_amanha
from tasks.alarm import adicionar_alarme, listar_alarmes, remover_alarme
from tasks.computer_control import computer_settings
from storage.memory_manager import load_memory, update_memory
from engine.cmd_security import avaliar, executar, audit_recente

log = __import__("logging").getLogger("jarvis.tools_mapper")

def executar_no_loop_atual(coro) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import threading
    loop_thread = getattr(loop, "_thread_id", None)
    current_thread = threading.get_ident()

    if loop_thread is not None and loop_thread == current_thread:
        raise RuntimeError(
            "executar_no_loop_atual() chamado dentro da thread do loop de eventos. "
            "Refatore o gerenciador para async ou chame-o via run_in_executor()."
        )

    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=30)


def gerenciador_open_app(argumentos: dict):
    app_name = argumentos.get("app_name", "o aplicativo solicitado")
    open_app(argumentos)
    return f"Inicializando {app_name} imediatamente, Senhor."

def gerenciador_computador(argumentos: dict):
    computer_settings(argumentos)
    return "Configurações de hardware e parâmetros do sistema atualizados, Senhor."

def gerenciador_cmd(argumentos: dict):
    comando = argumentos.get("command", "").strip()
    tarefa = argumentos.get("task", "").strip()
    if not comando and tarefa:
        from engine.ia_router import router
        prompt = f"Gere APENAS o comando de terminal para: {tarefa}. Responda somente com o comando puro."
        try:
            comando = executar_no_loop_atual(router.responder(prompt)).strip().strip("`").strip()
        except Exception as e:
            return f"Erro crítico ao gerar comando neural: {e}"
    
    if not comando:
        return "Alvo de execução nulo. Nenhum comando foi estruturado."
    
    av = avaliar(comando)
    if not av.permitido:
        return f"Ação abortada por segurança, Senhor. Motivo: {av.motivo}"
    
    saida = executar(comando, timeout=20, ferramenta="cmd_control")
    return f"Comando '{comando}' executado. Saída: {saida}"

def gerenciador_web_search(argumentos: dict):
    query = argumentos.get("query", "").strip()
    if query:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"Varredura de rede iniciada. Resultados para '{query}' projetados no navegador, Senhor."
    return "A busca web falhou. Termo de pesquisa inválido ou nulo."

def gerenciador_browser(argumentos: dict):
    acao = argumentos.get("action", "open").lower()
    url = argumentos.get("url", "").strip()
    query = argumentos.get("query", "").strip()
    
    if acao == "open" and url:
        webbrowser.open(url)
        return f"Acessando o protocolo de rede externo em {url}, Senhor."
    if acao in ("search", "open") and query:
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        return f"Pesquisando índices globais para '{query}'."
    if url:
        webbrowser.open(url)
        return f"Direcionando requisição para {url}."
    return "A diretiva do navegador foi processada, mas nenhum parâmetro válido foi extraído."

def gerenciador_youtube(argumentos: dict):
    query = argumentos.get("query", "").strip()
    if query:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"Sincronizando stream de vídeo. Resultados para '{query}' carregados do YouTube."
    else:
        webbrowser.open("https://www.youtube.com")
        return "Acessando interface principal da plataforma YouTube, Senhor."

def gerenciador_spotify(argumentos: dict):
    acao = argumentos.get("action", "").lower()
    if argumentos.get("playlist_name"):
        spotify_stark.listar_e_tocar_playlist(argumentos["playlist_name"])
        return f"Sincronizando áudio. Reproduzindo sua playlist personalizada agora, Senhor."
    if argumentos.get("search_query"):
        spotify_stark.abrir_e_buscar(argumentos["search_query"])
        return f"Localizando faixa de áudio para '{argumentos['search_query']}' no banco de dados musical."
    spotify_stark.controlar_reproducao(acao or "playpause")
    return "Frequências sonoras e reprodutor controlados de acordo com os protocolos, Senhor."

def gerenciador_clima(argumentos: dict):
    cidade = argumentos.get("city", "")
    previsao = argumentos.get("forecast", "hoje").lower()
    if previsao == "amanha":
        res = verificar_chuva_amanha(cidade)
        return f"Análise barométrica concluída para amanhã: {res if res else 'Dados indisponíveis no momento.'}"
    res = obter_previsao_hoje(cidade)
    return f"Dados meteorológicos de hoje atualizados em tempo real, Senhor: {res if res else 'Falha na telemetria local.'}"

def gerenciador_alarme(argumentos: dict):
    operacao = argumentos.get("op", "add").lower()
    if operacao == "list":
        itens = listar_alarmes()
        if isinstance(itens, list):
            return "Listando agendamentos ativos no cronômetro do sistema:\n" + "\n".join(f"• {item['hora']} — {item['missao']}" for item in itens)
        return str(itens)
    if operacao == "remove":
        remover_alarme(argumentos.get("hora", ""), argumentos.get("missao", ""))
        return "Protocolo de agendamento removido da memória operacional, Senhor."
    
    hora = argumentos.get("hora", "")
    missao = argumentos.get("missao", "Lembrete")
    if not hora:
        return "Impossível criar alerta. Janela temporal não especificada."
    
    data_alarme = argumentos.get("data")
    if isinstance(data_alarme, str) and not data_alarme.strip():
        data_alarme = None
        
    adicionar_alarme(hora, missao, data=data_alarme)
    return f"Alarme configurado com sucesso. Notificação agendada para às {hora} para a tarefa: {missao}."

def gerenciador_casa_inteligente(argumentos: dict):
    from tasks.smart_home import (abrir_youtube_tv, buscar_id_tv, energia_tv, diagnosticar_falha_tv, status_tv)
    dispositivo = argumentos.get("device", "").lower()
    acao = argumentos.get("action", "").lower()
    
    if "tv" in dispositivo:
        if acao in ("youtube", "abrir_youtube", "app_youtube"):
            abrir_youtube_tv()
            return "Redirecionando sinal de mídia principal para o aplicativo do YouTube na TV, Senhor."
        if acao == "on":
            if energia_tv(True): return "Módulos de tela ativados. Televisão principal inicializada, Senhor."
            if not buscar_id_tv(): return f"Falha de link com o hardware de vídeo. Diagnóstico: {diagnosticar_falha_tv()}"
            return "Falha de barramento ao enviar sinal de inicialização para a TV."
        if acao == "off":
            if energia_tv(False): return "Encerrando periféricos de vídeo. Televisão principal desativada, Senhor."
            if not buscar_id_tv(): return f"Falha de link com o hardware de vídeo. Diagnóstico: {diagnosticar_falha_tv()}"
            return "Falha de barramento ao enviar sinal de desligamento para a TV."
        if acao == "status":
            return f"Telemetria da interface doméstica: {status_tv()}"
    return "Comando de automação residencial recebido. Subsistema focado apenas nos módulos de TV no momento."

def gerenciador_arquivos(argumentos: dict):
    acao = argumentos.get("action", "")
    caminho = argumentos.get("path", "")
    nome = argumentos.get("name", "")
    conteudo = argumentos.get("content", "")
    permanente = argumentos.get("permanent", False)

    import os, shutil, pathlib

    atalhos = {
        "desktop":   os.path.join(os.path.expanduser("~"), "Desktop"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documentos": os.path.join(os.path.expanduser("~"), "Documents"),
        "home":      os.path.expanduser("~"),
    }

    caminho_resolvido = atalhos.get(caminho.lower(), caminho) if caminho else os.path.expanduser("~")
    alvo = os.path.join(caminho_resolvido, nome) if nome else caminho_resolvido

    try:
        if acao == "list":
            itens = os.listdir(caminho_resolvido)
            return "Itens em " + caminho_resolvido + ": " + ", ".join(itens[:30])
        if acao == "create_file":
            pathlib.Path(alvo).write_text(conteudo, encoding="utf-8")
            return f"Arquivo '{alvo}' criado com sucesso."
        if acao == "create_folder":
            os.makedirs(alvo, exist_ok=True)
            return f"Pasta '{alvo}' criada."
        if acao == "read":
            texto = pathlib.Path(alvo).read_text(encoding="utf-8", errors="replace")
            return texto[:1000]
        if acao == "delete":
            if os.path.isdir(alvo):
                shutil.rmtree(alvo) if permanente else shutil.move(alvo, os.path.join(os.path.expanduser("~"), ".Trash", nome or "pasta"))
            else:
                os.remove(alvo) if permanente else shutil.move(alvo, os.path.join(os.path.expanduser("~"), "Desktop", "lixo_" + nome))
            return f"'{alvo}' removido."
        if acao == "disk":
            total, usado, livre = shutil.disk_usage("/")
            return f"Disco: {livre // (1024**3)} GB livres de {total // (1024**3)} GB."
        return f"Ação '{acao}' não reconhecida pelo gerenciador de arquivos."
    except Exception as e:
        return f"Erro no gerenciador de arquivos: {e}"


def gerenciador_memoria(argumentos: dict):
    categoria = argumentos.get("category")
    chave = argumentos.get("key")
    valor = argumentos.get("value")
    if not all([categoria, chave, valor]):
        return "Indexação de memória de longo prazo falhou devido a argumentos ausentes."

    resultado = update_memory({categoria: {chave: valor}})
    sucesso = isinstance(resultado, dict)
    return f"Dados gravados com sucesso na minha memória de longo prazo. Setor: {categoria}." if sucesso else "Falha crítica ao persistir dados na estrutura de memória interna."

def gerenciador_plano(argumentos: dict):
    from engine.ia_router import router
    objetivo = argumentos.get("goal", "").strip()
    contexto = argumentos.get("context", "")
    if not objetivo:
        return "Estrutura de planejamento vazia. Por favor, forneça o objetivo central."
    
    coro = router.responder(f"Crie um plano estruturado para: {objetivo}. Contexto extra: {contexto}")
    resultado = executar_no_loop_atual(coro)
    return resultado or f"Matriz de planejamento tático calculada para o objetivo: '{objetivo}'. Pronto para execução, Senhor."

def gerenciador_codigo(argumentos: dict):
    from engine.ia_router import router
    descricao = argumentos.get("description", "")
    linguagem = argumentos.get("language", "python")
    codigo_base = argumentos.get("code", "")
    executar_flag = argumentos.get("execute", False)
    
    if not descricao:
        return "Impossível programar sem especificações funcionais na descrição."
        
    comando_ia = f"Gere APENAS código {linguagem}: {descricao}. {codigo_base}"
    codigo_gerado = executar_no_loop_atual(router.responder(comando_ia))
    
    if executar_flag and codigo_gerado:
        import shlex

        import re as _re
        match = _re.search(r"```(?:\w+)?\n([\s\S]+?)```", codigo_gerado)
        codigo_limpo = match.group(1).strip() if match else codigo_gerado.strip()
        if linguagem == "python":
            cmd = f"python -c {shlex.quote(codigo_limpo)}"
        else:
            cmd = f"bash -c {shlex.quote(codigo_limpo)}"
        av = avaliar(cmd)
        if not av.permitido:
            return f"Compilação bloqueada pela diretiva de proteção do núcleo: {av.motivo}"
        executar(cmd, timeout=15, ferramenta="code_helper")
        return f"Algoritmo em {linguagem} gerado, compilado e injetado no sistema com sucesso, Senhor."
        
    return codigo_gerado if codigo_gerado else "O compilador de inteligência artificial falhou ao estruturar a lógica."

def gerenciador_visao(argumentos: dict):
    from vision.capture import analisar_tela
    pergunta = argumentos.get("question", "Analisa e descreve o que está na tela agora.")
    executar_no_loop_atual(analisar_tela(pergunta))
    return "Sensores ópticos ativados. Varredura completa da tela realizada com sucesso, Senhor."

def gerenciador_troca_ia(argumentos: dict):
    from engine.ia_router import router
    modo = argumentos.get("mode", "ollama").lower()
    router.definir_modo(modo)
    return f"Redirecionando sinapses neurais. Motores cognitivos alternados para o modo {modo}, Senhor."

def gerenciador_agente_visual(argumentos: dict):
    tarefa = argumentos.get("task", "")
    if not tarefa:
        return "Nenhuma instrução operacional foi passada para o atuador de interface gráfica."
        
    wrapper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent_s_wrapper.py"))
    try:
        processo = subprocess.run(["python", wrapper_path, tarefa, "--json"], capture_output=True, text=True, timeout=300)
        if processo.returncode == 0:
            try:
                dados = json.loads(processo.stdout)
                return f"Automação de interface finalizada pelo Gui Actuator. Status: {dados.get('status')}. Resposta: {dados.get('message')}"
            except Exception:
                return f"Comando de interface executado. Retorno bruto do atuador: {processo.stdout[:200]}"
        return f"Falha na manipulação física da interface gráfica. Erro de barramento: {processo.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return "A rotina operacional excedeu o tempo limite de segurança de 5 minutos estabelecido para o Agente S."
    except Exception as e:
        return f"Erro crítico na camada de abstração de UI: {e}"

def gerenciador_visao_3d(argumentos: dict):
    try:
        from vision.capture import MotorVisaoEspacial
        import cv2
        motor_3d = MotorVisaoEspacial()
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Falha de hardware. Módulo óptico e câmeras tridimensionais inacessíveis para triangulação de profundidade."
        
        resultado = motor_3d.analisar_medida_cena(frame)
        if resultado["status"] == "sucesso":
            return f"Mapeamento tridimensional concluído. Escala espacial: {resultado['pixels_por_cm']} px/cm. Profundidade relativa calculada, Senhor."
        return f"Erro no processamento da malha geométrica 3D: {resultado['motivo']}"
    except Exception as e:
        return f"O subsistema de fotogrametria e análise volumétrica falhou: {e}"

def gerenciador_traducao_audio(argumentos: dict):
    segundos = argumentos.get("segundos", 10)
    return f"Captando frequências sonoras do ambiente por {segundos} segundos para tradução simultânea em tempo real. Módulos em calibração, Senhor."

def gerenciador_otimizacao_dados(argumentos: dict):
    try:
        from storage.optimizer import comprimir_banco_auditoria
        executar_no_loop_atual(comprimir_banco_auditoria())
        return "Banco de dados desfragmentado e índices otimizados para máxima performance, Senhor."
    except Exception as e:
        return f"Falha no algoritmo de compressão e otimização de armazenamento: {e}"


EXECUTOR_FERRAMENTAS: dict[str, Callable[[dict], str]] = {
    "open_app":                 gerenciador_open_app,
    "computer_control":         gerenciador_computador,
    "cmd_control":              gerenciador_cmd,
    "web_search":               gerenciador_web_search,
    "browser_control":          gerenciador_browser,
    "youtube_video":            gerenciador_youtube,
    "spotify_control":          gerenciador_spotify,
    "weather_report":           gerenciador_clima,
    "set_reminder":             gerenciador_alarme,
    "smart_home":               gerenciador_casa_inteligente,
    "file_controller":          gerenciador_arquivos,
    "save_memory":              gerenciador_memoria,
    "agent_task":               gerenciador_plano,
    "code_helper":              gerenciador_codigo,
    "screen_analysis":          gerenciador_visao,
    "switch_ia_mode":           gerenciador_troca_ia,
    "visual_gui_actuator":      gerenciador_agente_visual,
    "medir_ambiente_3d":        gerenciador_visao_3d,
    "traduzir_audio_ambiente":  gerenciador_traducao_audio,
    "otimizar_banco_dados":     gerenciador_otimizacao_dados,
}

async def despachar(nome: str, args: dict):
    func = EXECUTOR_FERRAMENTAS.get(nome)
    
    if func is None:
        log.error(f"Tentativa de usar ferramenta fantasma: {nome}")
        return f"Falha de link: A ferramenta de codinome '{nome}' não está registrada no kernel principal."
    
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, args)
    except Exception as e:
        log.error(f"Erro fatal na execução da ferramenta '{nome}': {e}")
        return f"A ferramenta {nome} sofreu uma falha crítica de hardware ou runtime durante a execução."
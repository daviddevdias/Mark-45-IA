TOOL_DECLARATIONS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Abre qualquer aplicativo instalado no sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Nome do app. Ex: 'chrome', 'spotify', 'vscode'.",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_control",
            "description": "Controla o PC no Windows: minimizar janelas, screenshot, bloquear tela, volume, mute.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Acao: 'fechar', 'minimizar_tudo', 'print', 'bloqueio', 'volume', 'mute'.",
                    },
                    "nivel": {
                        "type": "integer",
                        "description": "Volume 0-100 (só para action='volume').",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cmd_control",
            "description": "Executa comandos de terminal Linux.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Descrição da tarefa em português. Ex: 'listar arquivos'.",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Pesquisa na web e retorna resumo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo de pesquisa."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_control",
            "description": "Abre URLs ou faz pesquisa no navegador padrão.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "'open' para abrir URL, 'search' para pesquisar.",
                        "enum": ["open", "search"],
                    },
                    "url": {
                        "type": "string",
                        "description": "URL completa para abrir.",
                    },
                    "query": {"type": "string", "description": "Termo de pesquisa."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_video",
            "description": "Pesquisa e abre vídeos no YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo para pesquisar no YouTube.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_control",
            "description": "Controla o Spotify: tocar/pausar/playlist/busca.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Ação: 'playpause', 'next', 'previous', 'buscar'.",
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Música para buscar no Spotify.",
                    },
                    "playlist_name": {
                        "type": "string",
                        "description": "Nome da playlist para tocar.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "weather_report",
            "description": "Obtém previsão do tempo ou alerta de chuva para uma cidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Nome da cidade (ex: 'Porto Alegre').",
                    },
                    "forecast": {
                        "type": "string",
                        "description": "'hoje' ou 'amanha'.",
                        "enum": ["hoje", "amanha"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Cria, lista ou remove alarmes/lembretes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "description": "Operação: 'add', 'list', 'remove'.",
                        "enum": ["add", "list", "remove"],
                    },
                    "hora": {
                        "type": "string",
                        "description": "Horário HH:MM (ex: '14:30').",
                    },
                    "missao": {
                        "type": "string",
                        "description": "Descrição do lembrete.",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data no formato AAAA-MM-DD (opcional).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "smart_home",
            "description": "Controla dispositivos da casa inteligente (TV Samsung).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Dispositivo (ex: 'tv').",
                    },
                    "action": {
                        "type": "string",
                        "description": "Ação: 'on', 'off', 'status', 'youtube', 'volume'.",
                        "enum": ["on", "off", "status", "youtube", "volume"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_controller",
            "description": "Gerencia arquivos e pastas: criar, ler, listar, deletar, info disco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Ação: 'list', 'create_file', 'create_folder', 'read', 'delete', 'disk'.",
                        "enum": [
                            "list",
                            "create_file",
                            "create_folder",
                            "read",
                            "delete",
                            "disk",
                        ],
                    },
                    "path": {
                        "type": "string",
                        "description": "Caminho da pasta (ex: 'desktop', 'downloads').",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome do arquivo/pasta.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo do arquivo (só para create_file).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_task",
            "description": "Cria um plano estruturado para alcançar um objetivo complexo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Objetivo principal.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto adicional.",
                    },
                },
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_helper",
            "description": "Gera código, explica ou debuga. Pode executar se solicitado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Descrição do código ou problema.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Linguagem (python, bash, etc). Padrão: python.",
                    },
                    "execute": {
                        "type": "boolean",
                        "description": "Executar o código gerado?",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_ia_mode",
            "description": "Alterna o provedor de IA entre lmstudio, gemini e openrouter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Modo: 'lmstudio', 'gemini' ou 'openrouter'.",
                        "enum": ["lmstudio", "gemini", "openrouter"],
                    }
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visual_gui_actuator",
            "description": "Agente visual para automação de interface gráfica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Descrição da tarefa visual.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traduzir_audio_ambiente",
            "description": "Escuta o ambiente por alguns segundos e traduz o que ouviu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "segundos": {
                        "type": "integer",
                        "description": "Tempo de escuta em segundos. Padrão: 10.",
                    }
                },
            },
        },
    },
]

import re
import sys
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

# ==============================================================================
# 1. MAPEAMENTO DE REGRAS PGP
# ==============================================================================

EQUIPAMENTOS_PREFIXO_MODELO: List[str] = ['CMTS', 'OLT']

# Estrutura de destino no NFS (/mnt/ServidorBackup): <CIDADE>/<TIPO>/<CATEGORIA>/<AAAA>/<MES>/<DD>/
# Espelha a organização já aplicada aos logs legados por migrar_pgp_logs_legado.sh.
CATEGORIA_POR_TAREFA = {
    'BKP': 'BKP',
    'SEG': 'SEG',
    'VER': 'VER',
    'BKP_OLT': 'BKP',
}

# Mesma abreviação usada em migrar_pgp_logs_legado.sh (CITY_MAP) - manter sincronizado.
CIDADE_PARA_CODIGO = {
    'ARACAJU': 'AJU',
    'RECIFE': 'RCE',
    'FORTALEZA': 'FLA',
    'MACEIO': 'MCO',
    'JOAO_PESSOA': 'JPA',
    'NATAL': 'NTL',
    'SALVADOR': 'SDR',
    'TERESINA': 'TSA',
    'VIT_CONQUISTA': 'VIT',
}

def carregar_regras_pgp() -> Dict[str, Any]:
    caminho_yaml = Path(__file__).parent / 'pgp_regras.yaml'
    try:
        with open(caminho_yaml, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[ERRO] Falha ao carregar arquivo de regras PGP: {e}", file=sys.stderr)
        return {}


# ==============================================================================
# 2. MANIPULAÇÃO DE DIRETÓRIOS E ARQUIVOS (REGRA DE TAREFA APLICADA)
# ==============================================================================

def garantir_pasta_destino(caminho_base: Path, tipo_tarefa: str, cidade: str, equipamento: str, modelo: str) -> Path:
    agora = datetime.now()
    mes_atual = agora.strftime('%B').upper()
    ano_atual = agora.strftime('%Y')
    dia_atual = agora.strftime('%d')

    tarefa_sanitizada = str(tipo_tarefa).upper().strip()
    if tarefa_sanitizada not in CATEGORIA_POR_TAREFA:
        # [SÊNIOR] Nunca use sys.exit() em bibliotecas. Use Raise para o caller tratar o erro.
        raise ValueError(f"Tarefa inválida para nomenclatura de diretório: {tarefa_sanitizada}")

    categoria = CATEGORIA_POR_TAREFA[tarefa_sanitizada]

    if tarefa_sanitizada == 'BKP_OLT':
        tipo_equipamento = 'OLT'
    elif tarefa_sanitizada in ('SEG', 'VER'):
        tipo_equipamento = 'CMTS'
    else:
        # BKP: separa CMTS de ROTEADOR. Equipamento/modelo podem chegar trocados (mesma
        # tolerancia que ja existe em validar_pgp), entao checa os dois campos.
        # Equipamentos legados (STW) nao sao mais consultados; qualquer excecao cai em CMTS.
        candidatos = {str(equipamento).upper().strip(), str(modelo).upper().strip()}
        tipo_equipamento = 'ROTEADOR' if 'RTD' in candidatos else 'CMTS'

    cidade_sanitizada = str(cidade).upper().strip().replace(" ", "_")
    codigo_cidade = CIDADE_PARA_CODIGO.get(cidade_sanitizada, cidade_sanitizada)

    pasta_destino = caminho_base / codigo_cidade / tipo_equipamento / categoria / ano_atual / mes_atual / dia_atual

    try:
        pasta_destino.mkdir(parents=True, exist_ok=True)
        return pasta_destino
    except OSError as error:
        raise RuntimeError(f"Não foi possível criar a estrutura de diretórios em {pasta_destino}: {error}")


def padronizar_nome_e_mover(pasta_origem: Path, pasta_destino: Path, log_bruto: str, equipamento: str, modelo: str,
                            hostname: str, data_log: str, tipo_tarefa: str) -> Path:
    arquivo_origem = pasta_origem / log_bruto

    if not arquivo_origem.exists():
        raise FileNotFoundError(f"Arquivo origem não encontrado: {arquivo_origem}")

    eq_upper = equipamento.upper().strip()
    mod_upper = modelo.upper().strip()
    tarefa_upper = str(tipo_tarefa).upper().strip()

    exige_prefixo = eq_upper in EQUIPAMENTOS_PREFIXO_MODELO or mod_upper in EQUIPAMENTOS_PREFIXO_MODELO

    if exige_prefixo:
        fabricante = eq_upper if mod_upper in EQUIPAMENTOS_PREFIXO_MODELO else mod_upper
        prefixo_tarefa = {"VER": "VERSAO_", "SEG": "SEGURANCA_"}.get(tarefa_upper, "")
        novo_nome = f"{prefixo_tarefa}{fabricante}_{hostname}_{data_log}.txt"
    else:
        novo_nome = f"{hostname}_{data_log}.txt"

    arquivo_destino = pasta_destino / novo_nome

    try:
        shutil.move(str(arquivo_origem), str(arquivo_destino))
        return arquivo_destino
    except Exception as e:
        raise RuntimeError(f"Falha ao mover arquivo {log_bruto} para {arquivo_destino}: {e}")


# ==============================================================================
# 3. VALIDAÇÃO PGP REFATORADA (BLINDADA CONTRA LIXO DE SSH)
# ==============================================================================

def sanitizar_texto_bruto(texto: str) -> str:
    """
    Remove códigos ANSI, backspaces e caracteres de controle do terminal
    que corrompem o log cru e causam falsos negativos no PGP.
    """
    # 1. Remove códigos de escape ANSI (Cores, paginação, formatação de terminal)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    texto = ansi_escape.sub('', texto)

    # 2. Resolve backspaces (\x08). O regex simula o terminal: apaga o char anterior e o backspace.
    # Exemplo prático do IOS-XR: "shwo\x08ow bgp" se transforma em "show bgp".
    encontrou_backspace = True
    while encontrou_backspace:
        texto_novo = re.sub(r'[^\x08]\x08', '', texto)
        if texto_novo == texto:
            encontrou_backspace = False
        texto = texto_novo
    texto = texto.replace('\x08', '')  # Limpa eventuais backspaces órfãos no topo do buffer

    # 3. Remove outros caracteres de controle ASCII perigosos (mantendo \n, \t, \r)
    texto = re.sub(r'[\x00-\x07\x0B-\x0C\x0E-\x1F\x7F]', '', texto)

    # 4. Transforma quebras e tabulações em espaço simples e joga para lowercase
    texto = re.sub(r'\s+', ' ', texto).lower()
    return texto


def validar_pgp(caminho_arquivo: Path, equipamento: str, modelo: str, tipo_tarefa: str, ignorados: list = None) -> Tuple[bool, List[str]]:
    equipamento = equipamento.upper()
    modelo = modelo.upper()
    tipo_tarefa = tipo_tarefa.upper()

    pgp_esperado = carregar_regras_pgp()
    regras_tarefa = pgp_esperado.get(tipo_tarefa)
    if not regras_tarefa:
        print(f"[ERRO] Tipo de tarefa desconhecido: '{tipo_tarefa}'.", file=sys.stderr)
        return False, ["TAREFA_INVALIDA"]

    comandos_esperados = regras_tarefa.get(equipamento, {}).get(modelo)
    if not comandos_esperados:
        comandos_esperados = regras_tarefa.get(modelo, {}).get(equipamento)

    if not comandos_esperados:
        msg_alerta = f"Regra PGP não cadastrada para combinação [{tipo_tarefa} -> {equipamento} -> {modelo}]"
        print(f"[ERRO] {msg_alerta}", file=sys.stderr)
        return False, [f"REGRA_INEXISTENTE:_{modelo}"]

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as arquivo:
            conteudo_log = arquivo.read()
    except IOError as e:
        print(f"[ERRO] Falha ao ler o log para validação PGP: {e}", file=sys.stderr)
        return False, ["FALHA_LEITURA_ARQUIVO"]

    # Passa o log, os comandos ignorados e os exigidos pelo MESMO túnel de sanitização.
    # Garante que as strings possam ser comparadas de forma 100% simétrica.
    conteudo_limpo = sanitizar_texto_bruto(conteudo_log)

    ignorados = ignorados or []
    ignorados_norm = [sanitizar_texto_bruto(c).strip() for c in ignorados]

    faltantes = []

    for cmd_base in comandos_esperados:
        cmd_lower = sanitizar_texto_bruto(cmd_base).strip()

        if cmd_lower in ignorados_norm:
            print(f"--- [INFO] Validação ignorada via orquestrador: O comando '{cmd_base}' foi desativado. ---")
            continue

        if cmd_lower not in conteudo_limpo:
            faltantes.append(cmd_base)

    return len(faltantes) == 0, faltantes

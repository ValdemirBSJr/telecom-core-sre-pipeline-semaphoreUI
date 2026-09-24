#!/usr/bin/env python3
"""
CLI Unificado para Automação Multi-vendor.
"""

import os
import argparse
import sys
from pathlib import Path
from datetime import datetime
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional, Any

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

import funcoes


class AutomacaoError(Exception):
    """Classe base para erros conhecidos e controlados nesta automacao."""
    pass

class ConfiguracaoError(AutomacaoError):
    """Lancada para erros de setup, como credenciais, IPs ou tipo de dispositivo."""
    pass

class ComandoInvalidoError(AutomacaoError):
    """Lancada quando um comando executado no dispositivo retorna um erro explicito."""
    pass


class FornecedorBase(ABC):
    def __init__(self, conexao: Any) -> None:
        self.conexao = conexao
        self.padroes_erro = [
            'error:', 'invalid input', 'unrecognized command',
            'incomplete command', '^', '%', 'overlaps', 'overlap'
        ]

    @abstractmethod
    def preparar_sessao(self) -> None:
        pass

    def enviar_comando_consulta(self, comando: str, **kwargs: Any) -> str:
        print(f"--- [INFO] Executando COMANDO de CONSULTA: '{comando}' ---")
        regex_prompt = self.obter_regex_prompt()
        if regex_prompt and 'expect_string' not in kwargs:
            kwargs['expect_string'] = regex_prompt

        saida: str = self.conexao.send_command(comando, **kwargs)
        linhas_saida = saida.strip().splitlines()

        if len(linhas_saida) <= 20:
            saida_lower = saida.lower()
            for padrao in self.padroes_erro:
                if padrao in saida_lower:
                    raise ComandoInvalidoError(
                        f"O comando '{comando}' foi rejeitado pelo equipamento com o erro: '{saida.strip()}'"
                    )
        return saida

    def obter_regex_prompt(self) -> Optional[str]:
        return None

    def enviar_comandos_configuracao(self, comandos: list[str], **kwargs: Any) -> str:
        print(f"--- [INFO] Executando COMANDO de CONFIG: {comandos} ---")
        return str(self.conexao.send_config_set(comandos, **kwargs))


class FornecedorHuawei(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor Huawei: Entrando em modo enable. ---")
        self.conexao.enable()
        self.padroes_erro = [padrao for padrao in self.padroes_erro if padrao != '%']


class FornecedorZTE(FornecedorBase):
    def preparar_sessao(self) -> None:
        import time
        print("--- [INFO] Fornecedor ZTE: Sessao pronta. ---")
        self.conexao.send_command("terminal length 0", cmd_verify=False)
        time.sleep(2)

    def enviar_comando_consulta(self, comando: str, **kwargs: Any) -> str:
        import time
        tentativas = 3
        read_timeout = kwargs.get('read_timeout', 120)

        for tentativa in range(1, tentativas + 1):
            try:
                if tentativa == 1:
                    saida = super().enviar_comando_consulta(comando, **kwargs)
                else:
                    print(f"--- [AVISO] Ativando modo Teletype (Slow Write). Tentativa {tentativa}/{tentativas}. ---")
                    self.conexao.clear_buffer()
                    for char in comando:
                        self.conexao.write_channel(char)
                        time.sleep(0.05)
                    self.conexao.write_channel('\n')
                    regex_prompt = self.obter_regex_prompt() or self.conexao.base_prompt
                    saida = self.conexao.read_until_pattern(pattern=regex_prompt, read_timeout=read_timeout)

                    saida_lower = saida.lower()
                    if len(saida.strip().splitlines()) <= 20:
                        for padrao in self.padroes_erro:
                            if padrao in saida_lower:
                                raise ComandoInvalidoError(f"Erro: '{saida.strip()}'")
                return saida
            except ComandoInvalidoError as erro:
                mensagem_erro_lower = str(erro).lower()
                if any(t in mensagem_erro_lower for t in ["no such neighbor"]):
                    return f"Bypass de infraestrutura: {comando}"
                if "unknown command" in mensagem_erro_lower or "invalid input" in mensagem_erro_lower:
                    if tentativa < tentativas:
                        self.conexao.write_channel('\n\n')
                        time.sleep(2)
                        continue
                raise
        raise AutomacaoError("Tentativas esgotadas")


class FornecedorNOKIA(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor NOKIA: Sessao pronta. ---")
        try:
            self.conexao.send_command("environment inhibit-alarms", expect_string=r"#", cmd_verify=False)
        except Exception:
            pass
        try:
            self.conexao.send_command("environment screen-length 0", expect_string=r"#")
        except Exception:
            pass
            
    def obter_regex_prompt(self) -> str:
        return r"(>.*#|\]|\#)"
        
    def enviar_comando_consulta(self, comando: str, **kwargs: Any) -> str:
        regex_prompt = self.obter_regex_prompt()
        if regex_prompt:
            kwargs['expect_string'] = regex_prompt
        return super().enviar_comando_consulta(comando, **kwargs)
        

class FornecedorNOKIARTD(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor NOKIA: Sessao pronta. ---")

    def obter_regex_prompt(self) -> str:
        return r"(\#|\])"


class FornecedorHuaweiRTD(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor Huawei (Roteadores): Sessao Pronta. ---")
        self.conexao.send_command("screen-length 0 temporary")
        self.padroes_erro = [padrao for padrao in self.padroes_erro if padrao != '%']

    def obter_regex_prompt(self) -> str:
        return r">"

    def enviar_comando_consulta(self, comando: str, **kwargs: Any) -> str:
        try:
            return super().enviar_comando_consulta(comando, **kwargs)
        except ComandoInvalidoError as erro:
            mensagem_erro_lower = str(erro).lower()
            lista_de_tolerancia = [
                "the instance does not exist",
                "wrong parameter found",
                "too many parameters found",
                "nat instance does not exist",
            ]
            if any(t in mensagem_erro_lower for t in lista_de_tolerancia):
                return f"Bypass de infraestrutura: {comando}"
            raise


class FornecedorCiscoCMTS(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor CISCO: Sessao pronta. ---")

    def obter_regex_prompt(self) -> str:
        return r"#"


class FornecedorArrisCMTS(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor ARRIS: Sessao pronta. ---")

    def obter_regex_prompt(self) -> str:
        return r"#"


class FornecedorCasaCMTS(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor Casa: Sessao pronta. ---")
        # Sem esse aquecimento, o primeiro comando enviado apos o login nao retorna
        # resposta nesse equipamento (observado com "show clock" isolado).
        try:
            self.conexao.send_command("page-off", cmd_verify=False, expect_string=r"#")
        except Exception:
            pass

    def obter_regex_prompt(self) -> str:
        return r"#"


class FornecedorAlcatelRTD(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor Alcatel: Sessao pronta. ---")
        self.conexao.send_command("environment more false")

    def obter_regex_prompt(self) -> str:
        return r"#"


class FornecedorCiscoRTD(FornecedorBase):
    def preparar_sessao(self) -> None:
        print("--- [INFO] Fornecedor Cisco: Sessão pronta. ---")
        try:
            self.conexao.send_command("terminal length 0", cmd_verify=False)
        except Exception:
            pass

    def obter_regex_prompt(self) -> str:
        return r"#"

    def enviar_comando_consulta(self, comando: str, **kwargs: Any) -> str:
        kwargs['cmd_verify'] = True
        if 'read_timeout' not in kwargs:
            kwargs['read_timeout'] = 120
        return super().enviar_comando_consulta(comando, **kwargs)


FORNECEDORES: Dict[str, Type[FornecedorBase]] = {
    'huawei_olt': FornecedorHuawei,
    'zte_zxros': FornecedorZTE,
    'nokia_srl': FornecedorNOKIA,
    'nokia_sros': FornecedorNOKIARTD,
    'huawei': FornecedorHuaweiRTD,
    'cisco_ios': FornecedorCiscoCMTS,
    'arris_cer': FornecedorArrisCMTS,
    'casa_cmts': FornecedorCasaCMTS,
    'cisco_xr': FornecedorCiscoRTD,
    'cisco_rtd': FornecedorCiscoRTD,
    'alcatel_sros': FornecedorAlcatelRTD,
}

# Tarefas PGP (BKP/SEG/VER/BKP_OLT): mantem global_cmd_verify=False, como sempre foi
# (ZTE teletype, buffer swapping do ASR9000 tratado a parte via cmd_verify=True local, etc).
# Fora de uma tarefa PGP (consulta avulsa em qualquer equipamento), usa cmd_verify=True -
# igual ao script legado de consulta simples, que nunca desligou a verificacao de eco.
TAREFAS_PGP = {'BKP', 'SEG', 'VER', 'BKP_OLT'}


def executar_automacao(args: argparse.Namespace) -> None:
    print(f"--- [INFO] Iniciando automacao para o host: {args.name} - {args.ip} ---")
    login = os.getenv('USUARIO') or args.user
    senha = os.getenv('SENHA') or args.password

    if not login or not senha:
        raise ConfiguracaoError("Erro: As variaveis de ambiente 'LOGIN' e 'SENHA' não foram definidas.")

    log_file_handle = None
    try:
        if args.log_file:
            print(f"--- [INFO] Abrindo arquivo de log: {args.log_file} ---")
            try:
                log_file_handle = open(args.log_file, 'wb')
            except IOError as e:
                raise ConfiguracaoError(f"Não foi possível abrir o arquivo de log {args.log_file}: {e}")

        dicionario_dispositivo = {
            "device_type": args.device_type,
            "host": args.ip,
            "username": login,
            "password": senha,
            "secret": args.secret or None,
            "session_log": log_file_handle,
            "session_timeout": 300,
            "timeout": 120,
            "auth_timeout": 120,
            "global_delay_factor": 5,
            "global_cmd_verify": not (args.tarefa and str(args.tarefa).upper() in TAREFAS_PGP),
        }

        dicionario_dispositivo = {k: v for k, v in dicionario_dispositivo.items() if k == 'session_log' or v is not None}
        lista_comandos = [comando.strip() for comando in args.commands.split(',')]
        classe_fornecedor = FORNECEDORES.get(args.device_type)

        if not classe_fornecedor:
            raise ConfiguracaoError(f"O fornecedor '{args.device_type}' não é suportado.")

        with ConnectHandler(**dicionario_dispositivo) as conexao:
            print(f"--- [SUCESSO] Conexao com {args.name} estabelecida. ---")
            fornecedor = classe_fornecedor(conexao)
            fornecedor.preparar_sessao()

            if args.action == 'show':
                for comando in lista_comandos:
                    if not comando: continue
                    saida = fornecedor.enviar_comando_consulta(comando, read_timeout=300)
                    print("\n" + "=" * 20 + f" SAIDA DO COMANDO: {comando} " + "=" * 20)
                    print(saida)
                    print("=" * 60 + "\n")

            elif args.action == 'config':
                saida_cfg = fornecedor.enviar_comandos_configuracao(lista_comandos, read_timeout=120)
                print("\n" + "=" * 20 + " SAIDA DA CONFIGURACAO " + "=" * 20)
                print(saida_cfg)
                print("=" * 60 + "\n")

        if log_file_handle:
            log_file_handle.flush()
            os.fsync(log_file_handle.fileno())

        if args.action == 'show':
            if args.log_file and args.tarefa:
                print("\n--- [INFO] Iniciando Organização e Validação PGP ---")
                if not args.equipamento or not args.modelo:
                    raise ConfiguracaoError("Para executar validação PGP, as flags --equipamento e --modelo são obrigatórias.")

                caminho_base = Path(args.caminho_base_logs)
                arquivo_origem = Path(args.log_file)
                pasta_destino = funcoes.garantir_pasta_destino(caminho_base, args.tarefa, args.cidade, args.equipamento, args.modelo)
                data_log = datetime.now().strftime('%d%m%Y')

                arquivo_final = funcoes.padronizar_nome_e_mover(
                    pasta_origem=arquivo_origem.parent,
                    pasta_destino=pasta_destino,
                    log_bruto=arquivo_origem.name,
                    equipamento=args.equipamento,
                    modelo=args.modelo,
                    hostname=args.name,
                    data_log=data_log,
                    tipo_tarefa=args.tarefa
                )
                print(f"--- [SUCESSO] Log movido para: {arquivo_final} ---")

                lista_comandos_ignorados = [cmd.strip() for cmd in args.ignorar.split(',')] if args.ignorar else []

                is_aderente, faltantes = funcoes.validar_pgp(
                    caminho_arquivo=arquivo_final,
                    equipamento=args.equipamento,
                    modelo=args.modelo,
                    tipo_tarefa=args.tarefa,
                    ignorados=lista_comandos_ignorados
                )

                if not is_aderente:
                    msg_erro = f"PGP NÃO ADERENTE ({args.tarefa}). Comandos faltantes: {', '.join(faltantes)}"
                    raise ComandoInvalidoError(msg_erro)

                print(f"--- [SUCESSO] Validação PGP ({args.tarefa}) 100% Aderente! ---")
            else:
                print("\n--- [INFO] Consulta Simples: Validação PGP e Backup ignorados. ---")
    finally:
        if log_file_handle:
            try:
                log_file_handle.close()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI unificado de Automação de Rede.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-a', '--action', required=True, choices=['show', 'config'], help="Tipo de acao: 'show' ou 'config'.")

    grupo_obrigatorio = parser.add_argument_group('Argumentos Obrigatorios')
    grupo_obrigatorio.add_argument('-i', '--ip', required=True, help="O endereco IP.")
    grupo_obrigatorio.add_argument('-n', '--name', required=True, help="O nome ou hostname do equipamento.")
    grupo_obrigatorio.add_argument('-t', '--device_type', required=True, help="O tipo de dispositivo Netmiko.")
    grupo_obrigatorio.add_argument('-c', '--commands', required=True, help="Comandos a serem executados, separados por virgula.")

    grupo_opcional = parser.add_argument_group('Argumentos Opcionais')
    grupo_opcional.add_argument('-u', '--user', help="Nome do usuario para login.")
    grupo_opcional.add_argument('-p', '--password', help="Senha para login.")
    grupo_opcional.add_argument('-s', '--secret', help="Senha do modo 'enable' (secret).")
    grupo_opcional.add_argument('-l', '--log-file', required=False, help="Arquivo para salvar o log da sessao.")
    grupo_opcional.add_argument('-q','--tarefa', choices=['BKP', 'SEG', 'VER', 'BKP_OLT'], help="Tipo de validação PGP.")
    grupo_opcional.add_argument('-v', '--cidade', default='DESCONHECIDA', help="Cidade para separação de diretorios.")
    grupo_opcional.add_argument('-e', '--equipamento', help="Tipo do equipamento para a regra PGP (Ex: CMTS, RTD).")
    grupo_opcional.add_argument('-m', '--modelo', help="Fabricante para a regra PGP (Ex: CISCO, HUAWEI, CASA).")
    grupo_opcional.add_argument('-d', '--caminho-base-logs', default='/etc/repositorio/local/scripts/', help="Caminho base de backups.")
    grupo_opcional.add_argument('-x', '--ignorar', help="Comandos a ignorar na validação PGP.")

    args = parser.parse_args()
    codigo_saida = 0
    try:
        executar_automacao(args)
    except (ConfiguracaoError, ComandoInvalidoError) as e:
        print(f"!!! [ERRO CONTROLADO] {e}", file=sys.stderr)
        codigo_saida = 1
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        print(f"!!! [ERRO DE CONEXAO/AUTENTICACAO] em {args.name}: {e}", file=sys.stderr)
        codigo_saida = 1
    except Exception as e:
        print(f"!!! [ERRO INESPERADO] em {args.name}. Traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        codigo_saida = 1
    finally:
        sys.exit(codigo_saida)

if __name__ == "__main__":
    main()

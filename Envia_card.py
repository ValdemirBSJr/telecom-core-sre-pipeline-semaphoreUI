#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Necessita: pip install adaptive-cards-py
# Exemplo de uso:
# python3 Envia_card.py -w "<URL_WEBHOOK_TEAMS>" -t "🚨 FALHA GRAVE: EXEMPLO" -n "Host/serviço afetado" -m "Descrição do erro"

import sys
import argparse
import base64
import json
from datetime import datetime
from typing import TypedDict, List, Optional

# --- Importações da sua biblioteca (adaptive-cards-py) ---
import adaptive_cards.card_types as types
from adaptive_cards.card import AdaptiveCard
from adaptive_cards.client import TeamsClient
from adaptive_cards.containers import Column, ColumnSet, Container
from adaptive_cards.elements import Image, TextBlock
from adaptive_cards.validation import CardValidatorFactory, Result


# Estrutura de dados que o Ansible envia para o script
class Equipamentos(TypedDict):
    hostname: Optional[str]
    status: Optional[str]
    falha: Optional[str]


def imagem_para_base64(caminho_imagem):
    # Função mantida do seu script original
    try:
        with open(caminho_imagem, "rb") as arq_imagem:
            return f"data:image/png;base64,{base64.b64encode(arq_imagem.read()).decode('utf-8')}"
    except Exception:
        return ""


def enviar_alerta_falha(webhook_url: str, titulo: str, hostname: str, mensagem_erro: str):
    data_atual = datetime.now().strftime('%d/%m/%y %H:%M')

    # Configura Imagem (logo da empresa deve estar acessível)
    image_url = imagem_para_base64("/etc/repositorio/local/empresa_logo.png")

    # URLs para ícones de status (remotos, mais confiáveis)
    img_nok = "https://img.icons8.com/?size=100&id=Gr9Hk0UxLDFn&format=png&color=000000"

    try:
        containers = []

        # --- 1. Cabeçalho de ERRO ---
        colunas_header = ColumnSet(columns=[
            Column(items=[
                TextBlock(text=titulo, weight=types.FontWeight.BOLDER, size=types.FontSize.LARGE,
                          color=types.Colors.ATTENTION),
                TextBlock(text=f"Automação Falhou em - {data_atual}", size=types.FontSize.SMALL, is_subtle=True)
            ], width="stretch"),
            Column(items=[Image(url=image_url, width="40px")], width="auto")
        ])
        containers.append(Container(items=[colunas_header], style=types.ContainerStyle.EMPHASIS))

        # --- 2. Detalhes do Erro (Strings Simples) ---
        containers.append(Container(items=[
            # Host Falho
            TextBlock(text=f"❌ **HOST AFETADO:** {hostname}", weight=types.FontWeight.BOLDER,
                      color=types.Colors.ATTENTION),
            # Mensagem de Erro
            TextBlock(text=f"*Detalhes do Erro:* {mensagem_erro}", wrap=True),
            # Instrução
            TextBlock(text="--- Ação: Logue no Semaphore para verificar o log de execução completo. ---", wrap=True,
                      is_subtle=True, separator=True)
        ], style=types.ContainerStyle.DEFAULT))

        # --- 3. Rodapé / Ação ---
        card_actions = []

        # Monta Card
        card = AdaptiveCard(version="1.5", body=containers, actions=card_actions)

        # Envia
        client = TeamsClient(webhook_url)
        response = client.send(card)

        if response.status_code == 202:
            print("SUCESSO: Card de falha enviado ao Teams.")
            return 0
        else:
            print(f"ERRO API TEAMS: {response.status_code} - {response.text}")
            return 1

    except Exception as e:
        print(f"ERRO INTERNO SCRIPT: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Envia card de alerta de falha geral para o Teams')
    parser.add_argument('-w', '--webhook', required=True)
    parser.add_argument('-t', '--title', required=True)
    parser.add_argument('-n', '--hostname', required=True, help='Nome do host que falhou.')
    parser.add_argument('-m', '--mensagem', required=True, help='Mensagem de erro do stderr do Ansible.')

    args = parser.parse_args()

    # --- CORREÇÃO AQUI: REMOVENDO A LÓGICA JSON INCOMPATÍVEL ---
    try:
        # Chama a função principal com as strings simples (w, t, n, m)
        sys.exit(enviar_alerta_falha(
            args.webhook,
            args.title,
            args.hostname,
            args.mensagem
        ))
    except Exception as e:
        # Captura qualquer erro de execução do script (exceto o próprio erro do Adaptive Card)
        print(f"ERRO INESPERADO: Falha na chamada do script Python. Erro: {e}")
        sys.exit(1)

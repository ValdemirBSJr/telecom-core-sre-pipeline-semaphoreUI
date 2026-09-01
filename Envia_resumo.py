import argparse
import json
import sys
import base64
import adaptive_cards.card_types as types
from adaptive_cards.card import AdaptiveCard
from adaptive_cards.client import TeamsClient
from adaptive_cards.containers import Column, ColumnSet, Container, ContainerTypes
from adaptive_cards.elements import Image, TextBlock
from adaptive_cards.validation import CardValidatorFactory, Result
from adaptive_cards.actions import ActionOpenUrl
from datetime import datetime
from typing import TypedDict, List, Optional


class Equipamentos(TypedDict):
    hostname: Optional[str]
    status: Optional[str]
    falha: Optional[str]


def enviar_card(equipamentos_list: List[Equipamentos], action_url: str, texto_cabecalho: str, webhook_url: str) -> int:
    data_atual = datetime.now()
    data_formatada = data_atual.strftime('%d/%m/%y')

    def imagem_para_base64(caminho_imagem):
        try:
            with open(caminho_imagem, "rb") as arq_imagem:
                return f"data:image/png;base64,{base64.b64encode(arq_imagem.read()).decode('utf-8')}"
        except Exception as e:
            print(f"Erro ao converter imagem para base64: {e}")
            return None

    empresa_logo = "/etc/repositorio/local/empresa_logo.png"
    base64_imagem = imagem_para_base64(empresa_logo)
    image_url = base64_imagem if base64_imagem else ""

    img_ok = "https://img.icons8.com/?size=100&id=Zy5ghkQj2rKy&format=png&color=000000"
    img_nok = "https://img.icons8.com/?size=100&id=Gr9Hk0UxLDFn&format=png&color=000000"
    img_falha = "https://img.icons8.com/?size=100&id=119067&format=png&color=000000"

    try:
        containers: list[ContainerTypes] = []

        conjunto_colunas: ColumnSet = ColumnSet(
            columns=[
                Column(
                    items=[
                        TextBlock(text=f"{texto_cabecalho} {data_formatada}", size=types.FontSize.EXTRA_LARGE)
                    ],
                    width="stretch",
                ),
                Column(items=[Image(url=image_url, width="40px")] if image_url else[], rtl=True, width="auto"),
            ]
        )
        containers.append(
            Container(
                items=[conjunto_colunas], style=types.ContainerStyle.EMPHASIS, bleed=True
            )
        )

        hostname_coluna_itens = []
        status_coluna_itens = []
        imagem_coluna_itens = []

        # Listas separadas para o desmembramento
        ofensores_coluna_itens = []
        falhas_pgp_coluna_itens = []

        infra_host_coluna_itens = []
        infra_erro_coluna_itens = []

        for equipamento in equipamentos_list:
            hostname_coluna_itens.append(TextBlock(text=f"_{equipamento['hostname']}_"))
            status_coluna_itens.append(TextBlock(text=equipamento["status"]))

            if equipamento["status"] == "OK":
                imagem_coluna_itens.append(Image(url=img_ok, width="20px"))
            elif equipamento["status"] == "NOK":
                imagem_coluna_itens.append(Image(url=img_nok, width="20px"))
                ofensores_coluna_itens.append(TextBlock(text=equipamento["hostname"]))
                falhas_pgp_coluna_itens.append(TextBlock(text=equipamento["falha"], color=types.Colors.WARNING))
            else:
                # Trata as FALHAS de infraestrutura
                imagem_coluna_itens.append(Image(url=img_falha, width="20px"))
                infra_host_coluna_itens.append(TextBlock(text=equipamento["hostname"]))
                infra_erro_coluna_itens.append(TextBlock(text=equipamento["falha"], color=types.Colors.ATTENTION))

        containers.append(
            Container(
                items=[
                    TextBlock(
                        text="**Equipamentos**",
                        size=types.FontSize.MEDIUM,
                    ),
                    ColumnSet(
                        columns=[
                            Column(items=hostname_coluna_itens, width="stretch"),
                            Column(items=status_coluna_itens, spacing=types.Spacing.MEDIUM, rtl=True, width="auto"),
                            Column(items=imagem_coluna_itens, spacing=types.Spacing.MEDIUM, rtl=True, width="auto"),
                        ],
                        separator=True,
                    ),
                ],
                spacing=types.Spacing.MEDIUM,
            )
        )

        # BLOCO 1: Renderiza Ofensores PGP se existirem
        if ofensores_coluna_itens:
            conjunto_colunas_pgp: ColumnSet = ColumnSet(
                columns=[
                    Column(items=ofensores_coluna_itens, width="stretch"),
                    Column(items=falhas_pgp_coluna_itens, width="auto"),
                ]
            )
            containers.append(
                Container(
                    items=[
                        Container(
                            items=[
                                ColumnSet(
                                    columns=[
                                        Column(items=[TextBlock(text="**Ofensores PGP**")], width="stretch"),
                                        Column(items=[TextBlock(text="**Status**")], width="auto"),
                                    ],
                                ),
                            ],
                            style=types.ContainerStyle.WARNING,
                            bleed=True,
                        ),
                        Container(items=[conjunto_colunas_pgp]),
                    ],
                )
            )

        # BLOCO 2: Renderiza Falhas de Conexão/Infra se existirem
        if infra_host_coluna_itens:
            conjunto_colunas_infra: ColumnSet = ColumnSet(
                columns=[
                    Column(items=infra_host_coluna_itens, width="stretch"),
                    Column(items=infra_erro_coluna_itens, width="auto"),
                ]
            )
            containers.append(
                Container(
                    items=[
                        Container(
                            items=[
                                ColumnSet(
                                    columns=[
                                        Column(items=[TextBlock(text="**Falhas de Infra / Timeout**")],
                                               width="stretch"),
                                        Column(items=[TextBlock(text="**Status**")], width="auto"),
                                    ],
                                ),
                            ],
                            style=types.ContainerStyle.ATTENTION,
                            bleed=True,
                        ),
                        Container(items=[conjunto_colunas_infra]),
                    ],
                )
            )

        delimitador_container = Container(
            items=[TextBlock(text=" ", separator=True)]
        )
        containers.append(delimitador_container)

        action_url = ActionOpenUrl(
            title="Ver Arquivos",
            url=action_url
        )
        card_actions = [action_url]

        version = "1.5"
        card = AdaptiveCard(version=version, body=containers, actions=card_actions)

    except Exception as e:
        print(f"Erro ao montar o card: {e}")
        return 0

    try:
        client = TeamsClient(webhook_url)
        response = client.send(card)

        if response.status_code == 202:
            print("Mensagem do card de resumo enviada com sucesso!")
            return 0
        else:
            print(f"Falha ao enviar o card: {response.text}")
            return 1

    except Exception as e:
        print(f"Erro ao enviar o card: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envia card de resumo para o Teams.")
    parser.add_argument('-w', '--webhook', required=True, help="URL do Webhook do Teams (por cidade).")
    parser.add_argument('-t', '--titulo', required=True, help="Texto do cabeçalho.")
    parser.add_argument('-u', '--url', required=True, help="URL do repositório/Gitea para ver os arquivos.")
    parser.add_argument('-d', '--dados', required=True, help="Lista de dicionários em formato JSON string.")

    args = parser.parse_args()

    try:
        lista_equipamentos = json.loads(args.dados)
    except json.JSONDecodeError as e:
        print(f"[ERRO] Formato JSON inválido recebido do Ansible: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(enviar_card(
        equipamentos_list=lista_equipamentos,
        action_url=args.url,
        texto_cabecalho=args.titulo,
        webhook_url=args.webhook
    ))

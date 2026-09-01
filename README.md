# Automacao SRE - Multi-vendor Telecom Core

![Status: estudo de caso](https://img.shields.io/badge/status-estudo%20de%20caso-9333EA)
![Portfólio Valdemir](https://img.shields.io/badge/portf%C3%B3lio-Valdemir-8C1010)

*[English version](README-en.md)*

Este repositório é um **estudo de caso público** do pipeline de automação multi-vendor focado em práticas de SRE para o core de Telecom. Ele apresenta o problema, os princípios do produto e uma arquitetura estritamente conceitual. Não contém código-fonte com IPs reais, automações, credenciais, configurações de infraestrutura, dados de clientes ou regras proprietárias.

## Arquitetura Geral e Responsabilidades

| Componente | Tecnologia | Papel no Pipeline |
|---|---|---|
| **Orquestrador** | Semaphore UI | Cérebro de disparo. Injeta credenciais de forma segura (Vault/Env) e variáveis de contexto (TAREFA, VENDOR, MODELO, COMANDOS). |
| **Control Plane** | Ansible | Orquestra a execução via `connection: local`, lida com rescue de falhas, agrega resultados e dispara telemetria (MS Teams). |
| **Motor de Conexão** | Python 3 + Netmiko | Abstração da complexidade das CLIs, execução de comandos, handshakes SSH e contorno de limitações físicas do hardware. |
| **Validador (PGP)** | Python (`funcoes.py`) | Sanitização de logs (remoção de ANSI/backspaces) e validação de conformidade (substring match) baseada em regras de negócio. |
| **Staging** | RAM (`/dev/shm`) | Escrita dos dumps brutos e processamento em memória, eliminando gargalos de I/O e desgaste prematuro de discos físicos. |
| **Persistência** | Rsync + Gitea/BKP | Transferência assíncrona (stateless) para o servidor de backup final, onde o histórico é versionado/organizado. |

## Fluxo de Execução

1. **Orquestrador -> Ansible:** O Semaphore UI inicia o Job passando um escopo massivo de roteadores, OLTs ou CMTS.
2. O Ansible assume e delega as tarefas para `localhost`. Ele chama os scripts Python injetando variáveis do orquestrador.
3. O Ansible monitora o exit code do Python. Em caso de erro, categoriza falha de infraestrutura ou conformidade e envia alertas.

## Modelos de Tarefas e Variáveis de Contexto

O pipeline utiliza conjuntos de variáveis pré-configuradas no orquestrador (templates) para garantir a execução padronizada de diferentes escopos de automação. Cada template injeta valores específicos no playbook e nos scripts Python.

### Consulta CMTS (`consulta_<arris|casa|cisco>`)
Usado para extrações pontuais e rápidas nos equipamentos.
- `parametros_<arris|casa|cisco>`
- `template_acesso`
- `template_consulta`
- `template_webhooks`
- `template_equip_<arris|casa|cisco>`

### Backup PGP de Roteadores (`pgp_<VENDOR>_rtd_<CIDADE>_bkp_<NÚMERO_HOST>`)
Rotina direcionada para backup de hosts específicos (Roteadores de Borda/Core) de uma cidade.
- `parametros_<VENDOR>_rtd_<CIDADE>_bkp_<NÚMERO_HOST>`
- `template_equip_VENDOR`
- `template_modelo`
- `template_tarefa_bkp`
- `template_cidade`
- `template_url_git_cidade`
- `template_acesso`
- `template_consulta`
- `template_webhooks`

### Validação PGP Geral (`pgp_<VENDOR>_<bkp|seg|ver>`)
Auditoria e versionamento de backups, segurança ou versões de equipamentos de um vendor.
- `parametros_VENDOR_pgp_<bkp|seg|ver>`
- `template_equip_VENDOR`
- `template_modelo`
- `template_tarefa_<bkp|seg|ver>`
- `template_cidade`
- `template_url_git_cidade`
- `template_acesso`
- `template_consulta`
- `template_webhooks`

### Configuração IP Fixo DG (`tarefa_ipfixo_dg_<CIDADE>`)
Automação para provisionamento ou coleta de dados de IP Fixo (Default Gateway) em uma região.
- `template_acesso`
- `template_consulta`
- `template_log_ipfixo`
- `template_equip_VENDOR`
- `parametros_ipfixo_dg`
- `template_webhooks`

## Direitos

Este repositório não concede licença de uso, cópia, modificação ou distribuição de suas automações para fins comerciais. Servindo apenas para demonstração de portfólio.

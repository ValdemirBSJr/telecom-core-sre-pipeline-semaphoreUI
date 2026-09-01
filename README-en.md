# SRE Automation - Multi-vendor Telecom Core

![Status: case study](https://img.shields.io/badge/status-case%20study-9333EA)
![Portfolio Valdemir](https://img.shields.io/badge/portfolio-Valdemir-8C1010)

*[Versão em Português](README.md)*

This repository is a **public case study** of a multi-vendor automation pipeline focused on SRE practices for the Telecom core. It presents the problem, the product principles, and a strictly conceptual architecture. It does not contain source code with real IPs, automations, credentials, infrastructure configurations, customer data, or proprietary rules.

## General Architecture and Responsibilities

| Component | Technology | Role in the Pipeline |
|---|---|---|
| **Orchestrator** | Semaphore UI | The trigger brain. Securely injects credentials (Vault/Env) and context variables (TASK, VENDOR, MODEL, COMMANDS). |
| **Control Plane** | Ansible | Orchestrates execution via `connection: local`, handles failure rescues, aggregates results, and triggers telemetry (MS Teams). |
| **Connection Engine** | Python 3 + Netmiko | Abstracts CLI complexity, command execution, SSH handshakes, and works around physical hardware limitations. |
| **Validator (PGP)** | Python (`funcoes.py`) | Log sanitization (removal of ANSI/backspaces) and compliance validation (substring match) based on business rules. |
| **Staging** | RAM (`/dev/shm`) | Writes raw dumps and processes them in memory, eliminating I/O bottlenecks and premature wear of physical disks. |
| **Persistence** | Rsync + Gitea/BKP | Asynchronous transfer (stateless) to the final backup server, where the history is versioned/organized. |

## Execution Flow

1. **Orchestrator -> Ansible:** The Semaphore UI initiates the Job passing a massive scope of routers, OLTs, or CMTS.
2. Ansible takes over and delegates the tasks to `localhost`. It calls the Python scripts, injecting variables from the orchestrator.
3. Ansible monitors the Python exit code. In case of an error, it categorizes it as an infrastructure or compliance failure and sends alerts.

## Task Models and Context Variables

The pipeline uses pre-configured variable sets (templates) in the orchestrator to ensure standardized execution for different automation scopes. Each template injects specific values into the playbook and Python scripts.

### CMTS Query (`consulta_<arris|casa|cisco>`)
Used for targeted and fast extractions on equipment.
- `parametros_<arris|casa|cisco>`
- `template_acesso`
- `template_consulta`
- `template_webhooks`
- `template_equip_<arris|casa|cisco>`

### Router PGP Backup (`pgp_<VENDOR>_rtd_<CIDADE>_bkp_<NÚMERO_HOST>`)
Targeted routine for backing up specific hosts (Edge/Core Routers) in a city.
- `parametros_<VENDOR>_rtd_<CIDADE>_bkp_<NÚMERO_HOST>`
- `template_equip_VENDOR`
- `template_modelo`
- `template_tarefa_bkp`
- `template_cidade`
- `template_url_git_cidade`
- `template_acesso`
- `template_consulta`
- `template_webhooks`

### General PGP Validation (`pgp_<VENDOR>_<bkp|seg|ver>`)
Auditing and versioning of backups, security, or equipment versions for a vendor.
- `parametros_VENDOR_pgp_<bkp|seg|ver>`
- `template_equip_VENDOR`
- `template_modelo`
- `template_tarefa_<bkp|seg|ver>`
- `template_cidade`
- `template_url_git_cidade`
- `template_acesso`
- `template_consulta`
- `template_webhooks`

### Fixed IP DG Configuration (`tarefa_ipfixo_dg_<CIDADE>`)
Automation for provisioning or data collection of Fixed IP (Default Gateway) in a region.
- `template_acesso`
- `template_consulta`
- `template_log_ipfixo`
- `template_equip_VENDOR`
- `parametros_ipfixo_dg`
- `template_webhooks`

## Rights

This repository does not grant a license for use, copying, modification, or distribution of its automations for commercial purposes. It serves only as a portfolio demonstration.

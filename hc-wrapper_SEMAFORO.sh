#!/usr/bin/env bash
# Uso: hc-wrapper <UUID> <start|0|1>
# Desenvolvido por Valdemir Bezerra para o DTC NE.

HC_URL="http://<HC_SERVER_IP>/ping"
UUID="$1"
STATUS="$2"

# Aborta silenciosamente se faltar a variavel HC (evita quebrar execucoes Ad-Hoc)
if [ -z "$UUID" ] || [ -z "$STATUS" ]; then
    exit 0
fi

if [ "$STATUS" == "start" ]; then
    curl -fsS -m 10 --retry 3 "${HC_URL}/${UUID}/start" >/dev/null 2>&1 || true
elif [ "$STATUS" == "0" ]; then
    curl -fsS -m 10 --retry 3 "${HC_URL}/${UUID}" >/dev/null 2>&1 || true
else
    curl -fsS -m 10 --retry 3 "${HC_URL}/${UUID}/${STATUS}" >/dev/null 2>&1 || true
fi

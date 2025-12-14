#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}
PHONE=${PHONE:-5511999999999}
JQ_BIN=$(command -v jq || true)

pretty_print() {
  local data="$1"
  if [ -n "$JQ_BIN" ]; then
    echo "$data" | "$JQ_BIN" .
  else
    echo "$data"
  fi
}

send_payload() {
  local MSG_ID="$1"
  local BODY="$2"
  curl -s -X POST "${BASE_URL}/webhook/whatsapp" \
    -H "Content-Type: application/json" \
    -d "$(cat <<EOF
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "id": "${MSG_ID}",
          "from": "${PHONE}",
          "type": "text",
          "text": {"body": "${BODY}"}
        }]
      }
    }]
  }]
}
EOF
)"
  echo ""
}

echo ">> Iniciando fluxo de doação"
send_payload "msg-1" "1"
send_payload "msg-2" "Arroz"
send_payload "msg-3" "5kg"
send_payload "msg-4" "hoje 18h"
send_payload "msg-5" "Centro"
send_payload "msg-6" "sim"

echo ">> Consultando doações e matches"
pretty_print "$(curl -s "${BASE_URL}/admin/donations")"
pretty_print "$(curl -s "${BASE_URL}/admin/matches")"

echo ">> Reenviando mesma mensagem (dedupe esperado)"
send_payload "msg-6" "sim"

echo ">> Consultando novamente doações (não deve aumentar)"
pretty_print "$(curl -s "${BASE_URL}/admin/donations")"


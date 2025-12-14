# VEXIA - WhatsApp Real

Sistema de combate à fome que conecta excedentes de comida de restaurantes e mercados com ONGs, voluntários e pessoas em situação de insegurança alimentar via WhatsApp.

> Pronto para Github: visão geral, setup passo a passo (FastAPI + SQLite) e bridge Node (WPPConnect).

## 🚀 Funcionalidades

- **Doação de comida**: Restaurantes e indivíduos podem cadastrar alimentos excedentes
- **Cadastro de ONGs**: Organizações podem se registrar para receber doações
- **Distribuição voluntária**: Voluntários podem cadastrar pontos de distribuição em tempo real
- **Busca de comida**: Pessoas necessitadas podem encontrar opções próximas
- **Matching automático**: Sistema conecta doações com organizações compatíveis
- **Integração WhatsApp**: Toda interação via WhatsApp Cloud API

## 🏗️ Arquitetura

- **FastAPI**: API REST assíncrona
- **SQLAlchemy**: ORM para banco de dados
- **SQLite**: Banco de dados local
- **Alembic**: Migrations do banco
- **State Machine**: Fluxos conversacionais guiados
- **OpenAI**: Extração inteligente de intents (opcional)

## 📋 Pré-requisitos

- Python 3.8+
- Conta WhatsApp Business
- Token WhatsApp Cloud API (opcional para desenvolvimento)

## 🛠️ Instalação e Setup (passo a passo)

### 1. Clone e instale dependências (Python)

```bash
# Instalar dependências
pip install -r requirements.txt
```

### 2. Configure variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o .env com suas configurações principais
# DATABASE_URL=sqlite:///./vexia.db
# URL_PYTHON=http://127.0.0.1:8000/webhook
# NODE_SEND_URL=http://127.0.0.1:3000/send
# (tokens do WhatsApp se for usar Cloud API)
```

### 3. Configure o banco de dados

```bash
# Aplicar migrações existentes (recomendado)
alembic -c alembic.ini upgrade head

# (Opcional) Gerar nova migração após alterar modelos
alembic -c alembic.ini revision --autogenerate -m "sua mensagem"
```

### 4. (Opcional) Popular banco com dados de exemplo

```bash
# Executar seed de organizações de exemplo
python app/db/seed.py
```

### 5. Execute a aplicação (FastAPI)

```bash
# Desenvolvimento
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Produção
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Bridge Node (WPPConnect → FastAPI)

```bash
# Instalar dependências Node
npm install

# Rodar bridge (porta 3000)
npm start
```

Variáveis úteis no Node:
- `URL_PYTHON` (default `http://127.0.0.1:8000/webhook`) — para onde o Node repassa mensagens recebidas.
- `/send` (porta 3000) recebe `{ numero, mensagem }` e envia via WPPConnect.

### 7. Teste rápido local (dedupe + fluxo)

```bash
# Unix/macOS
scripts/test_flow.sh

# Windows PowerShell
scripts/test_flow.ps1
```

## 📱 Configuração WhatsApp

### 1. Meta for Developers

1. Acesse [Meta for Developers](https://developers.facebook.com/)
2. Crie um app do tipo "Business"
3. Adicione o produto "WhatsApp"

### 2. Configure Webhook

- **URL do webhook**: `https://yourdomain.com/webhook/whatsapp`
- **Verify Token**: Mesmo valor do `VERIFY_TOKEN` no .env

### 3. Tokens necessários

```env
WHATSAPP_TOKEN=EAAG...
WHATSAPP_PHONE_NUMBER_ID=123456789
VERIFY_TOKEN=vexia_verify_token
```

## 🔧 Endpoints da API

### Health Check
```
GET /health
```

### WhatsApp Webhook
```
GET  /webhook/whatsapp  # Verificação
POST /webhook/whatsapp  # Receber mensagens
```

### Admin (dados do sistema)
```
GET /admin/donations          # Lista doações
GET /admin/organizations      # Lista ONGs
GET /admin/active-distributions # Distribuições ativas
GET /admin/matches            # Matches realizados
GET /admin/metrics            # Métricas do sistema
```

## 💬 Fluxos de Conversa

### Menu Principal
```
Olá! Como posso te ajudar hoje?
1️⃣ Quero doar comida
2️⃣ Sou ONG / projeto social
3️⃣ Preciso de comida
4️⃣ Sou voluntário (distribuição agora)
```

### Doação de Comida
1. Tipo de comida
2. Quantidade
3. Validade/horário
4. Localização
5. Confirmação

### Cadastro de ONG
1. Nome da organização
2. Áreas de atuação
3. Capacidade de retirada
4. Horários de funcionamento
5. Confirmação

### Busca de Comida
1. Localização/bairro
2. Sistema retorna opções próximas

### Voluntário em Tempo Real
1. Tipo de comida
2. Quantidade
3. Validade/horário
4. Localização
5. Confirmação

## 🧪 Testando Localmente

### Simular webhook WhatsApp / Bridge

```bash
# Exemplo de payload WhatsApp (Cloud API)
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "5511999999999",
            "type": "text",
            "text": {
              "body": "Olá, quero doar comida"
            }
          }]
        }
      }]
    }]
  }'

# Exemplo de payload vindo do Node (bridge)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"numero":"5511999999999@c.us","mensagem":"oi"}'
```

### Ver dados do sistema

```bash
# Métricas
curl http://localhost:8000/admin/metrics

# Doações
curl http://localhost:8000/admin/donations
```

## 🗃️ Estrutura do Banco

### Tabelas Principais

- **users**: Usuários do sistema
- **organizations**: ONGs cadastradas
- **donations**: Doações disponíveis
- **active_distributions**: Distribuições voluntárias ativas
- **matches**: Conexões doação ↔ ONG
- **conversation_state**: Estados das conversas

## 🤖 IA e Matching

### Extração de Intent (OpenAI)

O sistema usa OpenAI para entender mensagens complexas e extrair:
- Intent (doar/org/procurar/voluntário)
- Tipo de comida
- Quantidade
- Localização
- Validade

### Matching Engine

Quando uma doação é criada:
1. Busca ONGs ativas
2. Prioriza por área de cobertura
3. Capacidade de retirada
4. Horários compatíveis
5. Notifica top 1 ONG por WhatsApp

## 📊 Métricas

O endpoint `/admin/metrics` retorna:
- Total de doações
- Distribuições ativas
- Refeições estimadas servidas
- Desperdício evitado (estimativa)

## 🚀 Deploy

### Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN alembic upgrade head

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Railway / Render

1. Configure variáveis de ambiente
2. Comando de inicialização: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Comando de migração: `alembic upgrade head`

## 🔒 Segurança

- Validar tokens do WhatsApp
- Sanitizar inputs
- Rate limiting (recomendado)
- HTTPS obrigatório em produção

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é open source e está sob a licença MIT.

## 🙏 Impacto Social

O VEXIA tem como objetivo combater o desperdício de alimentos e a fome, conectando eficientemente doadores com quem mais precisa, de forma digna e sem burocracia.

### Estatísticas de Impacto
- ✅ Redução de desperdício alimentar
- ✅ Refeições servidas para vulneráveis
- ✅ Conexão rápida e direta
- ✅ Sem custos para usuários
- ✅ Escalável e replicável

---

**Feito com ❤️ para combater a fome e o desperdício alimentar.**

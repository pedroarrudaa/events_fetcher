# 🚀 Deployment Guide - Events Dashboard

Este guia te mostra como fazer o deploy da sua aplicação de eventos. Cobrimos desde opções gratuitas até deployment em produção.

## 📋 Pré-requisitos

- Conta no GitHub
- Banco de dados PostgreSQL online (já configurado)
- Git instalado

## 🆓 Deployment Gratuito (Recomendado)

### 1. Backend - Render (Gratuito)

**Passo 1: Preparar o código**
```bash
# Já feito - verificar se arquivos existem:
# - Procfile
# - render.yaml 
# - runtime.txt
# - requirements.txt (com gunicorn)
```

**Passo 2: Deploy no Render**

1. Acesse [render.com](https://render.com) e crie uma conta
2. Conecte sua conta do GitHub
3. Clique em "New +" → "Web Service"
4. Conecte seu repositório do GitHub
5. Configure:
   - **Name**: `events-api` (ou qualquer nome)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend:app --bind 0.0.0.0:$PORT`
   - **Plan**: Free

**Passo 3: Configurar Variáveis de Ambiente**

No painel do Render, adicione as variáveis:
- `DATABASE_URL`: sua string de conexão PostgreSQL
- `FRONTEND_URL`: `https://seu-app-frontend.vercel.app` (adicionaremos depois)

**Passo 4: Deploy**
- Clique em "Create Web Service"
- Aguarde o build (5-10 minutos)
- Anote a URL: `https://events-api-XXXX.onrender.com`

### 2. Frontend - Vercel (Gratuito)

**Passo 1: Configurar build**

Verificar se o `package.json` está correto:
```json
{
  "scripts": {
    "build": "react-scripts build",
    "start": "react-scripts start"
  }
}
```

**Passo 2: Deploy no Vercel**

1. Acesse [vercel.com](https://vercel.com) e crie uma conta
2. Conecte sua conta do GitHub
3. Clique em "New Project"
4. Selecione seu repositório
5. Configure:
   - **Framework Preset**: Create React App
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `build`

**Passo 3: Configurar Variável de Ambiente**

No painel do Vercel:
1. Vá em Settings → Environment Variables
2. Adicione:
   - **Name**: `REACT_APP_API_URL`
   - **Value**: `https://events-api-XXXX.onrender.com` (URL do seu backend)
   - **Environment**: Production

**Passo 4: Redeploy**
- Vá em Deployments → clique nos 3 pontos → "Redeploy"

### 3. Atualizar CORS no Backend

Atualize a variável `FRONTEND_URL` no Render com a URL real do Vercel.

## 🔧 Alternativas de Deployment

### Backend Alternativas:

1. **Railway** (Gratuito)
   - Similar ao Render
   - Conectar GitHub
   - Deploy automático

2. **Heroku** (Pago - $7/mês)
   - Mais estável que opções gratuitas
   - `git push heroku main`

3. **DigitalOcean App Platform** ($5/mês)
   - Boa performance
   - Fácil de usar

### Frontend Alternativas:

1. **Netlify** (Gratuito)
   - Drag & drop da pasta `build`
   - Configurar variáveis de ambiente

2. **GitHub Pages** (Gratuito)
   - Para projetos públicos
   - Precisa de configuração adicional

## 🏢 Deployment Profissional

### AWS (Mais Complexo, Mais Controle)

**Backend (EC2 + RDS):**
```bash
# 1. Criar EC2 instance
# 2. Instalar Python, Git
# 3. Clonar repositório
# 4. Configurar nginx
# 5. Usar systemd para serviço
```

**Frontend (S3 + CloudFront):**
```bash
# 1. Build da aplicação
npm run build

# 2. Upload para S3
aws s3 sync build/ s3://your-bucket-name

# 3. Configurar CloudFront
```

### Docker (Containerizado)

**Dockerfile para Backend:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "backend:app", "--bind", "0.0.0.0:8000"]
```

**Dockerfile para Frontend:**
```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
```

## 🔄 CI/CD Automático

### GitHub Actions

Crie `.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Render
        run: curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

## 🧪 Teste do Deployment

Após o deployment, teste:

```bash
# Backend
curl https://your-backend-url.onrender.com/health

# Frontend
curl https://your-frontend-url.vercel.app
```

## 🛠 Troubleshooting

### Problemas Comuns:

1. **CORS Error**
   - Verificar variáveis de ambiente
   - Atualizar URL do frontend no backend

2. **Build Failed**
   - Verificar logs no Render/Vercel
   - Confirmar dependências no requirements.txt

3. **Database Connection**
   - Verificar DATABASE_URL
   - Confirmar IP whitelist (se necessário)

4. **Environment Variables**
   - Frontend: deve começar com `REACT_APP_`
   - Backend: configurar no painel do Render

## 📊 Monitoramento

- **Render**: Logs automáticos, métricas básicas
- **Vercel**: Analytics de performance
- **Uptime**: Use services como UptimeRobot

## 💰 Custos Estimados

### Gratuito:
- Render: 750 horas/mês (suficiente para 1 app)
- Vercel: 100GB bandwidth/mês
- **Total: R$ 0/mês**

### Profissional:
- Render Pro: $7/mês
- Vercel Pro: $20/mês  
- **Total: ~R$ 135/mês**

## 🚀 Quick Start (5 minutos)

1. **Push para GitHub** (se ainda não fez)
2. **Deploy Backend**: Render.com → conectar repo → deploy
3. **Deploy Frontend**: Vercel.com → conectar repo/frontend → deploy
4. **Configurar URLs**: Adicionar variáveis de ambiente
5. **Testar**: Acessar URLs e verificar funcionamento

Pronto! Sua aplicação está online! 🎉 
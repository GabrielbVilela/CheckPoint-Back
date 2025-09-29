# 📚 Backend de Gestão de Estágios

API RESTful desenvolvida em **Python** com **FastAPI**, projetada para servir como backend de uma aplicação de **gestão de contratos de estágio**.  

O sistema inclui gestão de múltiplos perfis de utilizador, autenticação segura por **JWT**, e um **sistema de ponto eletrónico com geolocalização**.

O projeto é totalmente contentorizado com **Docker**, garantindo um ambiente consistente e fácil de configurar tanto para desenvolvimento quanto para produção.

---

## ✨ Funcionalidades

- 🔐 **Autenticação com JWT**: Login seguro com geração de tokens de acesso.  
- 👥 **Gestão de Perfis**: Suporte a múltiplos perfis (Aluno, Professor, Coordenador, Admin).  
- 📄 **Gestão de Contratos**: Criação e consulta de contratos de estágio.  
- 📍 **Ponto Eletrónico com Geofencing**: Registo de entrada e saída com validação de localização.  
- ⏱️ **Histórico de Pontos**: Professores podem consultar o histórico de horas dos alunos.  
- 🗺️ **Integração com Google Maps**: Conversão automática de endereços para coordenadas geográficas.  

---

## 🛠️ Tecnologias

- **Backend:** Python 3.12, FastAPI  
- **Base de Dados:** PostgreSQL  
- **ORM:** SQLAlchemy  
- **Autenticação:** JWT (com [python-jose](https://github.com/mpdavis/python-jose))  
- **Servidor ASGI:** Uvicorn  
- **Contentorização:** Docker & Docker Compose  

---

## 🚀 Como Executar

### 📋 Pré-requisitos

- [Git](https://git-scm.com/)  
- [Docker](https://www.docker.com/)  
- [Docker Compose](https://docs.docker.com/compose/)  
- Uma **API Key do Google Maps Geocoding** (obtenha no [Google Cloud Console](https://console.cloud.google.com/))  

---

### ⚙️ Passos de Instalação

1. **Clonar o repositório**

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd nome-da-pasta-do-projeto

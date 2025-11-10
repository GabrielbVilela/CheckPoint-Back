# Use a imagem base do Python
FROM python:3.12-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Diz ao Python para sempre procurar módulos a partir da pasta /app
ENV PYTHONPATH=/app

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do seu projeto para o diretório de trabalho
COPY . .

# Comando para iniciar a aplicação
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

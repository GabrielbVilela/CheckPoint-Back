# Use a imagem base do Python
FROM python:3.12-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Diz ao Python para sempre procurar módulos a partir da pasta /app
ENV PYTHONPATH=/app
ENV PORT=8080

# Cria usuário não privilegiado
RUN addgroup --system app && adduser --system --ingroup app app

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do seu projeto para o diretório de trabalho
COPY . .

# Ajusta permissões e troca usuário
RUN chown -R app:app /app
USER app

# Comando para iniciar a aplicação (sem shell para evitar injection)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${PORT}"]

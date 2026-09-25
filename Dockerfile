FROM python:3.12-slim

# git é obrigatório: PyDriller clona os repositórios
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FAP_HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

CMD ["python", "src/app.py"]

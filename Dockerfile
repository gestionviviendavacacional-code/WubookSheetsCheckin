FROM python:3.11-slim

WORKDIR /app

# Actualizar apt y instalar dependencias necesarias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright
RUN python -m playwright install chromium

# Copiar código
COPY main.py .

# Exponer puerto
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Ejecutar
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "main:app"]

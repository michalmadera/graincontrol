# Dwa warianty. mock: lekki, działa wszędzie. gpu: PyTorch + CUDA, zgłasza kartę w /health.
# Analizator w obu to na razie atrapa; model z repo kamyki wchodzi do wariantu gpu.
FROM python:3.11-slim AS baza
ENV PYTHONUNBUFFERED=1 ANALIZA_DANE=/dane
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analiza ./analiza
RUN useradd --create-home --uid 1000 analiza && mkdir /dane && chown analiza /dane
USER analiza
VOLUME /dane
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "analiza.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM baza AS mock

FROM baza AS gpu
USER root
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124
USER analiza

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/fxsignal
COPY requirements.lock.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir --no-deps -e . && useradd --system fxsignal && mkdir -p var && chown fxsignal var
USER fxsignal
HEALTHCHECK --interval=60s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8087/health',timeout=4).status==200 else 1)"
CMD ["fxsignal", "serve", "--base-dir", "/opt/fxsignal"]

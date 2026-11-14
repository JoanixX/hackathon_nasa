# RAÍZ-SAR AI API and worker runtime: CPython 3.12 on Debian bookworm, Linux x86-64.
# The digest is the image actually pulled and tested on 2026-11-14.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# Rasterio's manylinux wheel bundles GDAL but links the system libexpat.
# Debian mirrors are reached over HTTPS because plain HTTP may be blocked by proxies.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements-linux-py312.lock ./
RUN pip install --root-user-action=ignore --require-hashes -r requirements-linux-py312.lock

RUN useradd --create-home --uid 10001 raiz
COPY --chown=raiz:raiz . /app
RUN mkdir -p /app/.local/runtime && chown -R raiz:raiz /app/.local
USER raiz

EXPOSE 8000
CMD ["uvicorn", "raiz_sar.api:app", "--host", "0.0.0.0", "--port", "8000"]

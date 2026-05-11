# Judges Said backend — FastAPI + a locally-run embedding model.
#
# Built and run on the Hetzner CX23 (2 vCPU x86, 4 GB RAM). The image is large, ~2.5 GB, and
# that is deliberate: the embedding model is baked in rather than downloaded at startup.

FROM python:3.12-slim

# Pinned rather than :latest — uv resolves the lock file, so letting it drift would make the
# build non-reproducible for no benefit.
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies before application code. torch alone is ~400 MB, so this layer must not be
# invalidated by an ordinary code change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Bake the embedding model into the image. Without this every container start pulls ~1.08 GB
# from HuggingFace before it can answer the first question.
#
# Deliberately does NOT import app.config: Settings requires the runtime secrets, which do not
# exist during a build, so the model name arrives as a build argument. Keep this value in step
# with `embedding_model` in app/config.py.
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-base
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" \
    && chmod -R a+rX /opt/hf

COPY . .

# Drop privileges. Done after the copies so the build never needs to chown a 2.5 GB tree —
# a recursive chown would duplicate every file into a new layer.
RUN useradd --create-home --uid 1000 app && chown app:app /app
USER app

EXPOSE 8000

# Single worker on purpose. Each worker loads its own ~1.1 GB copy of the model, so a second
# one would exceed the 4 GB box. Concurrency here is I/O-bound (OpenAI calls, Postgres), which
# one uvicorn event loop handles fine.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

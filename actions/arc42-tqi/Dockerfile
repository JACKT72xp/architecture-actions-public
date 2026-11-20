ARG PYTHON_IMAGE=python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYYAML_FORCE_LIBYAML=0 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements-build.txt requirements-runtime.txt ./
RUN python -m pip install --require-hashes --no-deps -r requirements-build.txt \
    && python -m pip download --require-hashes --no-deps --no-build-isolation \
       --platform any --only-binary=:all: --no-binary=PyYAML \
       -r requirements-runtime.txt --dest /downloads \
    && python -m pip wheel --no-deps --no-build-isolation \
       /downloads/*.whl /downloads/*.tar.gz --wheel-dir /wheels
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-deps --no-build-isolation . --wheel-dir /wheels \
    && python -m pip install --no-index --no-deps /wheels/*.whl \
    && python -c "import pydantic, yaml; assert not pydantic.compiled; assert not yaml.__with_libyaml__"

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --no-deps /wheels/*.whl \
    && python -m pip check \
    && rm -rf /wheels
LABEL org.opencontainers.image.title="arc42-tqi-action" \
      org.opencontainers.image.description="Deterministic arc42 architecture documentation assessment" \
      org.opencontainers.image.licenses="Apache-2.0"
WORKDIR /github/workspace
ENTRYPOINT ["arc42-tqi"]

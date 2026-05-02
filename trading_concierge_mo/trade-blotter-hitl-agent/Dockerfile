# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Trade Blotter HITL Agent — runtime image.
#
# Multi-stage build:
#   * builder:  installs the package + deps into a venv at /opt/venv.
#   * runtime:  copies the venv, drops to a non-root user, runs `adk web`.
#
# The agent picks up MCP_BRIDGE_URL / GOOGLE_API_KEY from the environment.
# ---------------------------------------------------------------------------

ARG PYTHON_VERSION=3.11

# --------------------------- builder --------------------------------------- #
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /build
# Copy only what's needed for installing the package.
COPY pyproject.toml README.md ./
COPY trade_blotter_hitl_agent ./trade_blotter_hitl_agent
COPY assets ./assets

RUN pip install --upgrade pip \
 && pip install .

# --------------------------- runtime --------------------------------------- #
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    ADK_HOST=0.0.0.0 \
    ADK_PORT=8000 \
    A2A_PORT=8100

# curl is used by the entrypoint's wait-for-bridge probe; tini supervises adk
# so signals are forwarded properly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /usr/sbin/nologin --uid 10001 agent

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=agent:agent trade_blotter_hitl_agent ./trade_blotter_hitl_agent
COPY --chown=agent:agent assets ./assets
COPY --chown=agent:agent docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER agent

EXPOSE 8000 8100

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${ADK_PORT}/list-apps" >/dev/null \
    && curl -fsS "http://127.0.0.1:${A2A_PORT:-8100}/health" >/dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8000"]

# SecHound — minimal image. Bundles the framework + curl/git/ripgrep.
# The default `claude` CLI backend isn't in the image; use an API backend
# (SECHOUND_LLM=anthropic|openai|gemini) or mount a claude binary.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git ripgrep ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e ".[yaml,anthropic,openai]"

# Findings DB + engagements persist via a mounted volume.
VOLUME ["/app/findings", "/app/engagements"]

ENTRYPOINT ["sechound"]
CMD ["doctor"]

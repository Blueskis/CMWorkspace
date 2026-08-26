FROM python:3.12-slim

# node is required at runtime — build_docx.py and build_pptx.py emit Node scripts
# (docx-js, pptxgenjs) that runner.py then executes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g docx pptxgenjs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The whole repo is needed, not just service/ — runner.py shells out to
# skills/cm-comms-generator/scripts/ and skills/cm-proposal-generator/scripts/,
# and reads proposal-assets/knowledge-bank/.
COPY . /app

RUN pip install --no-cache-dir -r service/requirements.txt

WORKDIR /app/service
EXPOSE 8000
CMD ["python", "server.py"]

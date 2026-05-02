FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 7001

CMD ["uvicorn", "mcp_http_server:app", "--host", "0.0.0.0", "--port", "7001"]

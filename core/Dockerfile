FROM python:3.12-alpine
WORKDIR /app
COPY app/server.py /app/server.py
COPY app/registry.py /app/registry.py
EXPOSE 8080
CMD ["python", "/app/server.py"]

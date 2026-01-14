FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests paho-mqtt

COPY app.py .

CMD ["python", "app.py"]

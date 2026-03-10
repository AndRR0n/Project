FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000

CMD ["supervisord", "-c", "supervisord.conf"]
# или CMD ["python", "web.py"] если без supervisor
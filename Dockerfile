FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY jmblog/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jmblog/ /app/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "public.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
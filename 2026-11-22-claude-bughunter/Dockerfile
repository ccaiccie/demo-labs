FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/app.py /app/app.py
COPY testdata/seed.json /app/testdata/seed.json

ENV SEED_PATH=/app/testdata/seed.json
ENV LAB_DB_PATH=/tmp/netops_lab.db
ENV PATCH_SQLI=0
ENV PATCH_XSS=0
ENV PATCH_IDOR=0

EXPOSE 8765

CMD ["gunicorn", "--bind", "0.0.0.0:8765", "--workers", "2", "app:app"]

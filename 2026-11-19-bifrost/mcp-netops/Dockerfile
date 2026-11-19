FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY server.py /app/server.py
ENV DEMO_DATA_DIR=/demo-data
EXPOSE 8765
CMD ["python", "-u", "/app/server.py"]

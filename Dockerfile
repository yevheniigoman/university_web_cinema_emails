from python:3.13-slim-bookworm

WORKDIR /app

COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY src /app/src

ENTRYPOINT ["python3", "src/main.py"]
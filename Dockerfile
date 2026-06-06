FROM apache/airflow:2.9.2-python3.11

USER root
# Install build essentials if psycopg2-binary ever needs to compile or for system libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt


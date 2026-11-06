FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/sentinel
COPY pyproject.toml constraints.txt ./
COPY app app
COPY scenarios scenarios
RUN pip install --no-cache-dir -c constraints.txt . && useradd --system --uid 10001 sentinel
COPY alembic.ini ./
COPY alembic alembic
USER 10001
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]

FROM node:20-alpine AS admin-ui-build

WORKDIR /admin-ui

COPY web-admin/package.json ./
RUN npm install

COPY web-admin/ ./

ARG ADMIN_UI_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${ADMIN_UI_API_BASE_URL}
ARG ADMIN_UI_BASE_PATH=/admin/
ENV VITE_BASE_PATH=${ADMIN_UI_BASE_PATH}

RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.4

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

COPY . .
COPY --from=admin-ui-build /admin-ui/dist /app/admin-ui-dist

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

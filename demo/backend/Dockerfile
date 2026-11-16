FROM python:3.13-slim
WORKDIR /app/source
COPY . /app/source
WORKDIR /app/source/demo/backend
RUN pip install --no-cache-dir -r requirements.txt
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

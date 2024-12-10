FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY bot.py .
COPY words.txt .
COPY users.json .
COPY .env .

CMD ["python", "bot.py"] 
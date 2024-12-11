FROM python:3.9-slim

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/config /app/wordlists

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create empty users.json in config directory
RUN touch /app/config/users.json
# Copy the application
COPY . .

CMD ["python", "bot.py"]
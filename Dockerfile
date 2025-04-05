# Use Python 3.9 as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Copy project files
COPY requirements.txt .
COPY chatbot.py .
COPY config_manager.py .
COPY ChatGPT_HKBU.py .
COPY db_helper.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set image name and tag
LABEL name="comp7940_groupi_bot"
LABEL version="1.0"

# Run the bot
CMD ["python", "chatbot.py"] 
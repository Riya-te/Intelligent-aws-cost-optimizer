
# Use official Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Update operating system packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install and update Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade setuptools

# Copy project files
COPY . .

# Default command
CMD ["python", "test.py"]

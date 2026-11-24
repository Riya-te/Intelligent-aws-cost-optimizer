
FROM python:3.13-slim

WORKDIR /app

# Update operating system packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    python -m pip install --no-cache-dir --upgrade "setuptools>=78.1.1" && \
    python -m pip check && \
    rm -f /usr/local/lib/python3.13/site-packages/pip/_vendor/bom.cdx.json

# Verify setuptools version
RUN python -c "import setuptools; print('Setuptools:', setuptools.__version__); assert setuptools.__version__ >= '78.1.1'"

COPY . .

CMD ["python", "test.py"]

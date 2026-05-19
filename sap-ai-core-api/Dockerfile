FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies
COPY requirements-simple.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port
EXPOSE 5056

# Run the application
CMD ["python", "main.py"]

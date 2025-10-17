# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure .streamlit directory exists and has proper permissions
RUN mkdir -p .streamlit && \
    chmod 755 .streamlit

# Create .streamlit directories and copy secrets.toml to the correct locations
RUN mkdir -p /root/.streamlit && \
    if [ -f .streamlit/secrets.toml ]; then \
        cp .streamlit/secrets.toml /root/.streamlit/secrets.toml && \
        chmod 600 /root/.streamlit/secrets.toml; \
    fi

# Expose port
EXPOSE 8080

# Set environment variables
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV DEV_MODE=False

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/_stcore/health || exit 1

# Run the application
CMD ["streamlit", "run", "main.py", "--server.port=8080", "--server.address=0.0.0.0"]

FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV AZURE_SPEECH_KEY=$AZURE_SPEECH_KEY
ENV AZURE_SPEECH_REGION=$AZURE_SPEECH_REGION
ENV AZURE_OPENAI_KEY=$AZURE_OPENAI_KEY

# Expose port
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
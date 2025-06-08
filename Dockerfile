FROM python:3.9-slim

WORKDIR /app

# Set UTF-8 locale and install system dependencies
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && \
    apt-get install -y ffmpeg libgl1 libglib2.0-0 git && \
    rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Environment variables (set these in Hugging Face Secrets UI)
ENV AZURE_SPEECH_KEY=""
ENV AZURE_SPEECH_REGION=""
ENV AZURE_OPENAI_KEY=""

# Expose Streamlit port
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
FROM python:3.10

# Set working directory
WORKDIR /app

# .cbr files are RAR archives — comic2pdf (via the `rarfile` library) needs
# a RAR-extraction binary on PATH. Debian's official repos don't ship the
# non-free "unrar", so we install "unar" (The Unarchiver) instead; rarfile
# auto-detects and uses it as a fallback backend.
RUN apt-get update && \
    apt-get install -y --no-install-recommends unar && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose port for Koyeb health checks
EXPOSE 8080

# Run the bot + webserver
CMD ["python", "bot.py"]

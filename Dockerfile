FROM python:3.11-slim

LABEL maintainer="tfrev contributors"
LABEL description="AI-powered Terraform plan reviewer"

# Install git (needed for diff generation in --auto mode)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install tfrev
COPY . /opt/tfrev
RUN pip install --no-cache-dir /opt/tfrev

# Default working directory (mount your Terraform project here)
WORKDIR /workspace

ENTRYPOINT ["tfrev"]
CMD ["--help"]

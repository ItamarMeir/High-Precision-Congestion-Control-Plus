# We use 20.04 to satisfy VS Code's GLIBC >= 2.28 requirement
FROM ubuntu:20.04

# Prevent interactive prompts (timezone queries, etc.)
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
# Note: We explicitly install python2 and link it, as it's not default in 20.04
RUN apt-get update && apt-get install -y \
    python2 \
    python2-dev \
    build-essential \
    gcc \
    g++ \
    gdb \
    gnuplot \
    git \
    mercurial \
    tcpdump \
    sqlite3 \
    libsqlite3-dev \
    libxml2 \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

# Crucial: Make 'python' command point to python2
RUN ln -sf /usr/bin/python2 /usr/bin/python

# Set working directory
WORKDIR /workspace

# Keep container alive
CMD ["tail", "-f", "/dev/null"]
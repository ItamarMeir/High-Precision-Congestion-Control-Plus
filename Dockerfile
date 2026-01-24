# We use 20.04 to satisfy VS Code's GLIBC >= 2.28 requirement
FROM ubuntu:20.04

# Prevent interactive prompts (timezone queries, etc.)
ENV DEBIAN_FRONTEND=noninteractive
ENV QT_X11_NO_MITSHM=1
ENV DISPLAY=:0
ENV LIBGL_ALWAYS_INDIRECT=1

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
    qtbase5-dev \
    qtchooser \
    qt5-qmake \
    qtbase5-dev-tools \
    x11-apps \
    xauth \
    libgl1-mesa-dev \
    libx11-xcb1 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-randr0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-sync1 \
    libxcb-xkb1 \
    libxrender1 \
    libxi6 \
    libxcursor1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Crucial: Make 'python' command point to python2
RUN ln -sf /usr/bin/python2 /usr/bin/python

# Set working directory
WORKDIR /workspace

# Build NetAnim (Qt GUI) for playback
RUN hg clone https://code.nsnam.org/netanim/ /opt/netanim \
    && cd /opt/netanim \
    && hg update -r netanim-3.108 \
    && qmake NetAnim.pro \
    && make -j"$(nproc)" \
    && ln -sf /opt/netanim/NetAnim /usr/local/bin/NetAnim

# Keep container alive
CMD ["tail", "-f", "/dev/null"]
FROM ubuntu:22.04 AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"\
    POETRY_VERSION=1.4.2 \
    DEBIAN_FRONTEND=noninteractive

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"
ENV PYTHONPATH="${PYSETUP_PATH}"

# Install Aravis dependencies and essential packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    python3-venv \
    python3-cairo \
    python3-numpy \
    python3-pil \
    # Essential dependencies for PyGObject/GI
    libgirepository1.0-dev \
    libgirepository-1.0-1 \
    gir1.2-glib-2.0 \
    gir1.2-gtk-3.0 \
    libffi-dev \
    pkg-config \
    libcairo2-dev \
    gcc \
    python3-dev \
    # Dependencies for building Aravis C library
    git \
    build-essential \
    meson \
    ninja-build \
    libglib2.0-dev \
    libxml2-dev \
    # Additional dependencies identified from logs
    gettext \
    cmake \
    libusb-1.0-0-dev \
    gobject-introspection \
    libgtk-3-dev \
    gtk-doc-tools \
    xsltproc \
    # Dependencies for GStreamer plugin
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    # Requirements for FastAPI app
    curl \
    iproute2 \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Aravis from source
WORKDIR /opt
RUN git clone https://github.com/AravisProject/aravis.git
WORKDIR /opt/aravis

# Configure, build and install Aravis
RUN meson setup build --prefix=/usr/local \
    -Dgst-plugin=enabled \
    -Dintrospection=enabled \
    -Dviewer=disabled \
    -Ddocumentation=disabled

WORKDIR /opt/aravis/build
RUN ninja && ninja install

# Update the library cache
RUN ldconfig

# Create user
RUN addgroup --gid 1000 appuser && adduser --uid 1000 --system --ingroup appuser appuser

WORKDIR $PYSETUP_PATH

RUN chown -R appuser /opt
USER appuser

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Make PyGObject modules visible in our virtual environment
ENV GI_TYPELIB_PATH="/usr/lib/aarch64-linux-gnu/girepository-1.0:/usr/local/lib/aarch64-linux-gnu/girepository-1.0"
ENV LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:/usr/local/lib"

# Copy project dependency files
COPY --chown=appuser ./pyproject.toml ./poetry.lock ./

# Add PyGObject modules to Poetry's virtual environment
RUN poetry config virtualenvs.options.system-site-packages true
RUN poetry install

# ------------------------------------------------------------------------------------
# 'development' stage installs all dev deps and can be used to develop code
FROM base AS development

# Install dev libs
WORKDIR $PYSETUP_PATH
COPY --chown=appuser ./pyproject.toml ./poetry.lock ./
RUN poetry install

WORKDIR /home/appuser

# Remove this line, app will be mounted as a volume:
# COPY --chown=appuser . .
# Instead, only copy scripts (if needed for entrypoint)
COPY --chown=appuser ./scripts ./scripts
RUN chmod +x scripts/*

# Create a script to set MTU for jumbo packets
RUN echo '#!/bin/sh\n\
    # Set jumbo packets on network interface\n\
    # Attempt to find the default interface\n\
    INTERFACE=$(ip -o -4 route show to default | awk "{print \\$5}")\n\
    if [ -n "$INTERFACE" ]; then\n\
    echo "Attempting to set MTU to 9000 on interface $INTERFACE..."\n\
    # Use ip link set dev <interface> mtu 9000 syntax\n\
    ip link set dev "$INTERFACE" mtu 9000\n\
    echo "MTU set on $INTERFACE."\n\
    else\n\
    echo "Warning: Could not determine default interface to set MTU."\n\
    fi\n\
    # Execute the command passed to the entrypoint\n\
    echo "Executing command: $@"\n\
    exec "$@"' > /home/appuser/scripts/set-mtu.sh && \
    chmod +x /home/appuser/scripts/set-mtu.sh

EXPOSE 8009
ENTRYPOINT ["/home/appuser/scripts/docker-entrypoint.sh"]
CMD ["python3", "-m", "app.main"]

# ------------------------------------------------------------------------------------
# 'release' stage uses the clean 'base' stage and copies
# in only our runtime deps that were installed in the 'base'
FROM base AS release

WORKDIR /home/appuser

COPY --chown=appuser . .
RUN chmod +x scripts/*

EXPOSE 8009
ENTRYPOINT ["/home/appuser/scripts/docker-entrypoint.sh"]
CMD ["python3", "-m", "app.main"]

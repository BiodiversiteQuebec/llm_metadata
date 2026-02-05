FROM python:3.12-slim

ARG TZ=America/New_York
ENV TZ="$TZ"

# Install system dependencies (includes firewall tools: iptables, ipset, iproute2, dnsutils, aggregate)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    sudo \
    zsh \
    fzf \
    less \
    procps \
    man-db \
    unzip \
    gnupg2 \
    jq \
    nano \
    vim \
    build-essential \
    openssh-client \
    iptables \
    ipset \
    iproute2 \
    dnsutils \
    aggregate \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y gh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install git-delta for nicer diffs
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
    wget -q "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
    dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
    rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

# Install Node.js 20 (required for Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create non-root dev user
ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/zsh ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Install Claude Code globally
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Copy and set up firewall script (convert CRLF to LF for Windows compatibility)
COPY .devcontainer/init-firewall.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/init-firewall.sh \
    && chmod +x /usr/local/bin/init-firewall.sh \
    && echo "${USERNAME} ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/${USERNAME}-firewall \
    && chmod 0440 /etc/sudoers.d/${USERNAME}-firewall

# Copy and set up workspace initialization script
COPY .devcontainer/init-workspace.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/init-workspace.sh \
    && chmod +x /usr/local/bin/init-workspace.sh

# Set up workspace and command history
RUN mkdir -p /workspace /commandhistory \
    && chown -R ${USERNAME}:${USERNAME} /workspace /commandhistory

USER ${USERNAME}

# Install oh-my-zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" -- --unattended

# Configure Claude alias to always use --dangerously-skip-permissions
RUN echo 'alias claude="claude --dangerously-skip-permissions"' >> ~/.zshrc \
    && echo 'alias claude="claude --dangerously-skip-permissions"' >> ~/.bashrc

# Persist command history across container restarts
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && echo "$SNIPPET" >> ~/.zshrc \
    && echo "$SNIPPET" >> ~/.bashrc

ENV SHELL=/bin/zsh
ENV EDITOR=nano
ENV VISUAL=nano
ENV DEVCONTAINER=true

WORKDIR /workspace

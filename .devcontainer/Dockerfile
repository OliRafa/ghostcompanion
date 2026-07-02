FROM mcr.microsoft.com/devcontainers/python:3.13

ENV POETRY_VIRTUALENVS_IN_PROJECT=true


# Install and configure Poetry and iPython
RUN pipx install poetry

# ai-jail sandbox needs bubblewrap for its namespaces.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
	&& apt-get -y install --no-install-recommends bubblewrap build-essential \
	&& rm -rf /var/lib/apt/lists/*

# Build ai-jail from source: upstream tap has no linux-aarch64 binary.
ARG AI_JAIL_VERSION=1.7.0
RUN set -eux \
	&& curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
		| sh -s -- -y --profile minimal --default-toolchain stable \
	&& . "$HOME/.cargo/env" \
	&& cargo install --git https://github.com/akitaonrails/ai-jail \
		--tag v${AI_JAIL_VERSION} --locked --root /usr/local \
	&& rustup self uninstall -y

# Create volume mount points with correct ownership
RUN mkdir -p /home/${USERNAME}/Work/ghostcompanion \
	/home/${USERNAME}/.local/share/opencode \
	/home/${USERNAME}/.claude \
	&& chown -R ${USERNAME}:${USERNAME} \
	/home/${USERNAME}/Work \
	/home/${USERNAME}/.local \
	/home/${USERNAME}/.claude


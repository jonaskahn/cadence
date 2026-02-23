#!/bin/bash

# Cadence AI Docker Build Script
# This script builds and pushes Docker images for Cadence AI

set -e

# Get version from pyproject.toml
VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
export CADENCE_LATEST_TAG="$VERSION"

echo "Building Cadence AI Docker image version: $VERSION"

# Build and push multi-platform image
docker buildx build -f docker/Dockerfile --platform linux/amd64,linux/arm64 --tag ifelsedotone/cadence:latest --tag ifelsedotone/cadence:${CADENCE_LATEST_TAG} . --push

echo "Cadence AI Docker image built and pushed successfully!"
echo "Tags: latest, $VERSION"
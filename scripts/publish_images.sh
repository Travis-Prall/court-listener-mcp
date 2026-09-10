#!/bin/bash
# Publish the CourtListener ++ MCP image to all configured registries.
#
# Builds a multi-arch (linux/amd64 + linux/arm64) image with BuildKit/buildx
# and pushes it to Docker Hub and the private registry in one step. GHCR is
# normally published automatically by CI (.github/workflows/docker-publish.yml);
# pass --ghcr to also publish there manually.
#
# Tags follow the repository convention: X.Y.Z + latest + sha-<git-short-SHA>.
#
# Usage:
#   scripts/publish_images.sh [VERSION] [--ghcr] [-h|--help]
#
# Arguments:
#   VERSION   Image version to publish (e.g. 0.2.2). Defaults to the exact
#             git tag at HEAD (a leading "v" is stripped), then falls back to
#             the version in pyproject.toml.
#
# Flags:
#   --ghcr    Also push to ghcr.io (in addition to CI's automatic publish)
#   -h|--help Show this help
#
# Environment:
#   DOCKERHUB_USER      Docker Hub username (default: vesha)
#   GITHUB_USER         GHCR namespace (default: travis-prall)
#   PERSONAL_REGISTRY   Private registry host (default: docker.vesha.net)
#   BUILDER             buildx builder name (default: multiarch)

set -euo pipefail

IMAGE_NAME="court-listener-mcp"
DOCKERHUB_USER="${DOCKERHUB_USER:-vesha}"
GITHUB_USER="${GITHUB_USER:-travis-prall}"
PERSONAL_REGISTRY="${PERSONAL_REGISTRY:-docker.vesha.net}"
BUILDER="${BUILDER:-multiarch}"
PLATFORMS="linux/amd64,linux/arm64"

PUSH_GHCR=false
VERSION=""

usage() {
  printf 'Usage: scripts/publish_images.sh [VERSION] [--ghcr] [-h|--help]\n'
  printf '\n'
  printf 'Builds a multi-arch image (%s) and pushes it to Docker Hub and\n' "$PLATFORMS"
  printf '%s. Tags: VERSION + latest + sha-<git-short-SHA>.\n' "$PERSONAL_REGISTRY"
  printf '\n'
  printf 'Flags:\n'
  printf '  --ghcr    Also push to ghcr.io/%s/%s\n' "$GITHUB_USER" "$IMAGE_NAME"
  printf ' -h|--help  Show this help\n'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ghcr) PUSH_GHCR=true ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "error: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    *)
      if [[ -n "$VERSION" ]]; then
        echo "error: unexpected extra argument '$1'" >&2
        exit 1
      fi
      VERSION="$1"
      ;;
  esac
  shift
done

# Run from the repository root regardless of the caller's working directory.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# --- Prerequisites -----------------------------------------------------------
for cmd in docker git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: '$cmd' is required but not installed" >&2
    exit 1
  fi
done
if ! docker buildx version >/dev/null 2>&1; then
  echo "error: the docker buildx plugin is required" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "error: docker daemon is not reachable" >&2
  exit 1
fi

# --- Resolve version and tags ------------------------------------------------
# 1. Explicit argument, 2. exact git tag at HEAD (strip "v"), 3. pyproject.toml
if [[ -z "$VERSION" ]]; then
  VERSION="$(git describe --tags --exact-match HEAD 2>/dev/null | sed 's/^v//' || true)"
fi
if [[ -z "$VERSION" ]]; then
  VERSION="$(sed -n 's/^version = "\([^"]*\)"$/\1/p' pyproject.toml | head -n1)"
fi
if [[ -z "$VERSION" ]]; then
  echo "error: could not determine VERSION; pass it as the first argument" >&2
  exit 1
fi
GIT_SHA="$(git rev-parse --short HEAD)"

# Docker Hub uses "<user>/<image>"; named registries use "<host>/<image>".
PREFIXES=("$DOCKERHUB_USER" "$PERSONAL_REGISTRY")
if $PUSH_GHCR; then
  PREFIXES+=("ghcr.io/$GITHUB_USER")
fi

TAGS=()
for prefix in "${PREFIXES[@]}"; do
  TAGS+=("$prefix/$IMAGE_NAME:$VERSION" "$prefix/$IMAGE_NAME:latest" "$prefix/$IMAGE_NAME:sha-$GIT_SHA")
done

echo "🚀 Publishing $IMAGE_NAME $VERSION (sha-$GIT_SHA) for $PLATFORMS"
echo "--------------------------------------------"
for tag in "${TAGS[@]}"; do
  echo "   $tag"
done

# --- Ensure a multi-arch capable builder exists -------------------------------
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  echo "🛠  Creating buildx builder '$BUILDER' (docker-container driver)..."
  docker buildx create --name "$BUILDER" --driver docker-container >/dev/null
fi
docker buildx inspect "$BUILDER" --bootstrap >/dev/null

# --- Build and push (multi-arch) ----------------------------------------------
BUILD_ARGS=(buildx build --builder "$BUILDER" --platform "$PLATFORMS" --push)
for tag in "${TAGS[@]}"; do
  BUILD_ARGS+=(-t "$tag")
done

echo "📦 Building and pushing $PLATFORMS image..."
docker "${BUILD_ARGS[@]}" .

# --- Verify what landed --------------------------------------------------------
echo "--------------------------------------------"
echo "🔎 Verifying published manifests for :$VERSION..."
for prefix in "${PREFIXES[@]}"; do
  DIGEST="$(docker buildx imagetools inspect "$prefix/$IMAGE_NAME:$VERSION" --format '{{json .Manifest.Digest}}')"
  PLATS="$(docker buildx imagetools inspect "$prefix/$IMAGE_NAME:$VERSION" --format '{{range .Manifest.Manifests}}{{.Platform.OS}}/{{.Platform.Architecture}} {{end}}')"
  echo "   $prefix/$IMAGE_NAME:$VERSION -> $DIGEST [$PLATS]"
done

echo "--------------------------------------------"
echo "✅ Done! Image published to all target registries."

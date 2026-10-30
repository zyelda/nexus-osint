#!/bin/sh
# Vercel build entrypoint. Only the frontend is built here; the Flask
# backend needs a persistent host and is deployed separately.
set -eu

cd frontend
npm ci
npm run build

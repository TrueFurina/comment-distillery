#!/usr/bin/env bash
# Bridge comment-distillery AI config: derive CD_LLM_* from your existing DEEPSEEK_API_KEY.
# Usage (bash/zsh/Git Bash):  source set-cd-env.sh
#
# Why this file exists: the tool only reads CD_LLM_* (it does NOT auto-read
# DEEPSEEK_API_KEY / OPENAI_API_KEY, to avoid hijacking keys used elsewhere and
# to keep the "no AI => pack-only" contract intact). So we bridge here, and the
# real key lives in exactly one place (your DEEPSEEK_API_KEY).
#
# You can override any field before/after sourcing:
#   export CD_LLM_MODEL=deepseek-reasoner   # before or after is fine
#   export CD_LLM_BASE_URL=https://alt.endpoint/v1

if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "[set-cd-env] WARNING: DEEPSEEK_API_KEY not set in this shell; CD_LLM_API_KEY will be empty." >&2
fi

export CD_LLM_API_KEY="${CD_LLM_API_KEY:-$DEEPSEEK_API_KEY}"
export CD_LLM_BASE_URL="${CD_LLM_BASE_URL:-https://api.deepseek.com/v1}"
export CD_LLM_MODEL="${CD_LLM_MODEL:-deepseek-chat}"

echo "[set-cd-env] CD_LLM_* ready (api_key from DEEPSEEK_API_KEY; base_url/model overridable)."
echo "[set-cd-env] Verify with: python -m app --selfcheck"

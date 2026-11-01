@echo off
REM Bridge comment-distillery AI config: derive CD_LLM_* from your existing DEEPSEEK_API_KEY.
REM Usage (cmd):  set-cd-env.bat
REM
REM The tool only reads CD_LLM_*, NOT DEEPSEEK_API_KEY/OPENAI_API_KEY (to avoid
REM hijacking keys used elsewhere and to keep the "no AI => pack-only" contract).
REM So we bridge here; the real key stays in one place (DEEPSEEK_API_KEY).
REM
REM Override any field by setting it BEFORE running this, e.g.:
REM   set CD_LLM_MODEL=deepseek-reasoner
REM   set CD_LLM_BASE_URL=https://alt.endpoint/v1

if not defined DEEPSEEK_API_KEY (
  echo [set-cd-env] WARNING: DEEPSEEK_API_KEY not set in this shell; CD_LLM_API_KEY will be empty.
)
if not defined CD_LLM_API_KEY set "CD_LLM_API_KEY=%DEEPSEEK_API_KEY%"
if not defined CD_LLM_BASE_URL set "CD_LLM_BASE_URL=https://api.deepseek.com/v1"
if not defined CD_LLM_MODEL set "CD_LLM_MODEL=deepseek-chat"

echo [set-cd-env] CD_LLM_* ready (api_key from DEEPSEEK_API_KEY; base_url/model overridable).
echo [set-cd-env] Verify with: python -m app --selfcheck

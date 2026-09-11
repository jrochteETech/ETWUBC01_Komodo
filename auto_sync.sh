
#!/usr/bin/env bash
set -euo pipefail

# ========= CONFIGURABLE VARIABLES =========
BASE="/home/ladmin/ignition"
ENVIRONMENTS=(dev qaqc prod)
LOG_FILE="${LOG_FILE:-$BASE/auto_sync.log}"
MAX_LOG_SIZE=10485760  # 10MB

# Git identity (should match your setup)
GIT_NAME="ladmin"
GIT_EMAIL="ladmin@etechgroup.com"

# Commit message prefix
COMMIT_PREFIX="Auto-sync:"
# ==========================================

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

rotate_log() {
  if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]]; then
    mv "$LOG_FILE" "$LOG_FILE.old"
    log "Log rotated"
  fi
}

sync_environment() {
  local env="$1"
  local env_path="$BASE/$env"

  log "=== Syncing $env environment ==="

  if [[ ! -d "$env_path" ]]; then
    log "ERROR: $env_path does not exist"
    return 1
  fi

  cd "$env_path" || {
    log "ERROR: Cannot cd to $env_path"
    return 1
  }

  # Verify we're on the correct branch
  local current_branch
  current_branch=$(git branch --show-current || true)
  if [[ "$current_branch" != "$env" ]]; then
    log "WARNING: Expected branch '$env' but on '$current_branch', checking out..."
    if ! git checkout "$env"; then
      log "ERROR: Failed to checkout $env branch"
      return 1
    fi
  fi

  # Configure git identity
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"

  case "$env" in
    dev)
      # Check for changes and commit
      if [[ -n $(git status --porcelain) ]]; then
        log "Changes detected in $env, committing..."
        git add -A
        if git commit -m "$COMMIT_PREFIX $env changes at $(date +'%Y-%m-%d %H:%M:%S')"; then
          log "Committed changes in $env"
        else
          log "ERROR: Commit failed for $env"
          return 1
        fi
      else
        log "No local changes in $env"
      fi

      # Pull remote changes (rebase) and push
      log "Pulling remote changes for $env..."
      if ! git pull --rebase origin "$env"; then
        log "WARNING: Pull failed for $env (may need manual intervention)"
      fi

      log "Pushing $env to remote..."
      if ! git push origin "$env"; then
        log "ERROR: Push failed for $env"
        return 1
      fi

      log "✅ $env synced successfully (commit/pull/push)"
      ;;

    qaqc|prod)
      # Only pull remote changes; do not commit or push

      # Ensure correct branch
      git checkout "$env" || { log "ERROR: checkout $env"; return 1; }

      log "Fetching remote for $env..."
      git fetch origin "$env" || { log "WARNING: fetch failed for $env"; }

      # Enforce clean worktree to avoid untracked overwrite errors
      if [[ -n $(git status --porcelain) ]]; then
        log "NOTE: Local changes/untracked files detected in $env. Resetting to origin/$env and cleaning untracked..."
        git reset --hard "origin/$env" || { log "ERROR: reset failed for $env"; return 1; }
        git clean -fd || { log "ERROR: clean failed for $env"; return 1; }
      else
        log "Worktree is clean in $env"
      fi

      # Rebase pull that prefers incoming (remote) on conflicts
      log "Pulling (rebase, prefer upstream) for $env..."
      if git pull --rebase -X theirs origin "$env"; then
        log "✅ $env rebase-pull completed (remote wins on conflicts)"
      else
         log "⚠️ Rebase-pull failed for $env"
        return 1
      fi
      ;;

    *)
      log "ERROR: Unknown environment '$env'"
      return 1
      ;;
  esac

  return 0
}

main() {
  rotate_log
  log "========================================="
  log "Starting auto-sync for Ignition environments"

  local failed=0

  for env in "${ENVIRONMENTS[@]}"; do
    if ! sync_environment "$env"; then
      ((failed++))
      log "⚠️  Failed to sync $env"
    fi
    echo "" >> "$LOG_FILE"
  done

  if [[ $failed -eq 0 ]]; then
    log "🎉 All environments synced successfully"
  else
    log "⚠️  $failed environment(s) failed to sync"
    exit 1
  fi

  log "Auto-sync complete"
  log "========================================="
}

# Run main function
main

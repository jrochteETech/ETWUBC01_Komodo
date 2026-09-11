
#!/usr/bin/env bash
set -euo pipefail

# ========= CONFIGURABLE VARIABLES =========
IMAGE="inductiveautomation/ignition:8.3.1"
BASE="/home/ladmin/ignition"
ENVIRONMENTS=(dev qaqc prod)

# Git remote & identity
REPO_URL="http://ladmin:VPW6Gs73@10.21.2.2:8033/etechadmin/ignition.git"
GIT_NAME="ladmin"
GIT_EMAIL="ladmin@etechgroup.com"

# Ignition ownership/permissions
IGN_UID=2003
IGN_GID=2003
IGN_PERMS=775

# Main working directory (will contain .git)
MAIN_WORKTREE="$BASE/dev"

# Targeted for Ignition 8.3.1+
# Keeps: projects, tag instances/atomic tags, and UDT definitions.

# Directories to keep (relative to /data)
TRACK_DIRS_FOLDERS_ONLY=(
  "config"
  "config/resources"
  "config/resources/core"
  "config/resources/core/ignition"
)
TRACK_DIRS=(
  "projects"
  "config/resources/core/ignition/tag-definition"      # atomic tags + UDT instances
  "config/resources/core/ignition/tag-type-definition" # UDT definitions
  "config/resources/core/ignition/tag-groups"          # Groups
  "config/resources/core/ignition/tag-providers"       # Providers
)

write_gitignore() {
  local env_root="$1"
  local gi="$env_root/.gitignore"

  {
    echo "# Ignore everything by default"
    echo "/*"
    echo
    echo "# Keep the root .gitignore"
    echo "!.gitignore"
    echo
    echo "# Keep only /data and selected subpaths beneath it"
    echo "!/data/"
    echo
    echo "# Ignore everything under /data by default"
    echo "/data/*"
    echo
    # Whitelist only the directories we care about (folder rules)
    for d in "${TRACK_DIRS_FOLDERS_ONLY[@]}"; do
      echo "!/data/${d}/"
      echo "/data/${d}/**"
    done
    # Whitelist exact directories we care about (content rules)
    for d in "${TRACK_DIRS[@]}"; do
      echo "!/data/${d}/"
      echo "!/data/${d}/**"
    done
  } > "$gi"
}

stage_selection_and_commit() {
  # args: path branch label
  local env_path="$1"
  local branch="$2"
  local label="$3"

  cd "$env_path"
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"

  # Ensure .gitignore exists and is tracked
  write_gitignore "$env_path"
  git add .gitignore

  # Add tracked directories if they exist
  for d in "${TRACK_DIRS[@]}"; do
    if [[ -d "data/$d" ]]; then
      git add "data/$d/" 2>/dev/null || echo "  (skip) data/$d"
    fi
  done

  # If nothing staged, create an empty initial commit so remote gets a real commit
  if git diff --cached --quiet 2>/dev/null; then
    git commit --allow-empty -m "Setup ${label} environment ($(date +'%F %T'))"
  else
    git commit -m "Setup ${label} environment ($(date +'%F %T'))"
  fi

  # Push and set upstream
  git push -u origin "$branch" --force-with-lease || echo "  ⚠️  Push failed for $branch"
}

remote_branch_exists() {
  # Must run in a repo context where 'origin' is set
  # returns 0 if remote branch exists
  local branch="$1"
  git ls-remote --heads origin "$branch" | grep -q "refs/heads/$branch"
}

echo "==> Seeding Ignition data folders..."
for ENV in "${ENVIRONMENTS[@]}"; do
  TARGET="$BASE/$ENV/data"
  echo "---- $ENV ----"
  sudo mkdir -p "$TARGET"

  docker run --rm \
    --user 0:0 \
    -v "$TARGET:/mnt/data:rw" \
    --entrypoint bash "$IMAGE" \
    -c 'cp -a /usr/local/bin/ignition/data/. /mnt/data'

  sudo chown -R "$IGN_UID:$IGN_GID" "$TARGET"
  sudo chmod -R "$IGN_PERMS" "$TARGET"
done
echo "==> Data seeding complete."

echo
echo "=== Setting up Git with worktrees ==="

# Initialize main repository in dev directory
cd "$MAIN_WORKTREE"

if [[ ! -d .git ]]; then
  echo "  Initializing repository in $MAIN_WORKTREE"
  git init -b dev
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"
  git remote add origin "$REPO_URL"

  # Create .gitignore and initial commit
  write_gitignore "$MAIN_WORKTREE"
  git add .gitignore

  # Add tracked directories
  for d in "${TRACK_DIRS[@]}"; do
    if [[ -d "data/$d" ]]; then
      git add "data/$d/" 2>/dev/null || echo "  (skip) data/$d"
    fi
  done

  git commit -m "Initial commit: dev environment ($(date +'%F %T'))"
  git push -u origin dev --force-with-lease || echo "  ⚠️  Initial push failed"

  echo "  ✅ Main repository initialized on dev branch"
else
  echo "  Repository already exists in $MAIN_WORKTREE"
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"

  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$REPO_URL"
  else
    git remote set-url origin "$REPO_URL"
  fi
fi

git config --global --add safe.directory "$MAIN_WORKTREE" || true

# Setup worktree for qaqc
if [[ ! -d "$BASE/qaqc/.git" ]] && [[ ! -f "$BASE/qaqc/.git" ]]; then
  echo
  echo "--- Setting up qaqc worktree ---"

  cd "$MAIN_WORKTREE"

  # Temporarily rename existing directory
  if [[ -d "$BASE/qaqc" ]]; then
    mv "$BASE/qaqc" "$BASE/qaqc.tmp"
  fi

  # Make sure we have the latest refs
  git fetch origin --prune || true

  if remote_branch_exists "qaqc"; then
    echo "  Remote branch qaqc exists, creating local branch and worktree from origin"
    # Create local tracking branch from remote
    git fetch origin qaqc:qaqc
    git worktree add "$BASE/qaqc" qaqc
  else
    echo "  Remote branch qaqc not found; creating branch from dev"
    git worktree add "$BASE/qaqc" -b qaqc dev
  fi

  # Move data back if it existed
  if [[ -d "$BASE/qaqc.tmp/data" ]]; then
    cp -a "$BASE/qaqc.tmp/data" "$BASE/qaqc/"
    rm -rf "$BASE/qaqc.tmp"
  fi

  git config --global --add safe.directory "$BASE/qaqc" || true

  # Always ensure an initial commit is pushed to create the remote branch
  stage_selection_and_commit "$BASE/qaqc" "qaqc" "qaqc"
  echo "  ✅ qaqc worktree created and pushed"
else
  echo "  qaqc worktree already exists"
fi

# Setup worktree for prod
if [[ ! -d "$BASE/prod/.git" ]] && [[ ! -f "$BASE/prod/.git" ]]; then
  echo
  echo "--- Setting up prod worktree ---"

  cd "$MAIN_WORKTREE"

  # Temporarily rename existing directory
  if [[ -d "$BASE/prod" ]]; then
    mv "$BASE/prod" "$BASE/prod.tmp"
  fi

  # Make sure we have the latest refs
  git fetch origin --prune || true

  if remote_branch_exists "prod"; then
    echo "  Remote branch prod exists, creating local branch and worktree from origin"
    git fetch origin prod:prod
    git worktree add "$BASE/prod" prod
  else
    echo "  Remote branch prod not found; creating branch from qaqc"
    # Ensure local qaqc exists to base from; if not, fetch it
    if ! git show-ref --verify --quiet refs/heads/qaqc; then
      git fetch origin qaqc:qaqc || true
    fi
    git worktree add "$BASE/prod" -b prod qaqc
  fi

  # Move data back if it existed
  if [[ -d "$BASE/prod.tmp/data" ]]; then
    cp -a "$BASE/prod.tmp/data" "$BASE/prod/"
    rm -rf "$BASE/prod.tmp"
  fi

  git config --global --add safe.directory "$BASE/prod" || true

  # Always ensure an initial commit is pushed to create the remote branch
  stage_selection_and_commit "$BASE/prod" "prod" "prod"
  echo "  ✅ prod worktree created and pushed"
else
  echo "  prod worktree already exists"
fi

echo
echo "🎉 Setup complete!"
echo
echo "Repository structure:"
echo "  Main repo:  $MAIN_WORKTREE (branch: dev)"
echo "  Worktrees:"
echo "    $BASE/qaqc/ (branch: qaqc)"
echo "    $BASE/prod/ (branch: prod)"
echo
echo "Usage:"
echo "  # Work in dev"
echo "  cd $BASE/dev"
echo "  git add data/projects/"
echo "  git commit -m 'Updated project'"
echo "  git push"
echo
echo "  # Merge dev → qaqc"
echo "  cd $BASE/qaqc"
echo "  git merge dev"
echo "  git push"
echo
echo "  # Merge qaqc → prod"
echo "  cd $BASE/prod"
echo "  git merge qaqc"
echo "  git push"
echo
echo "List all worktrees:"
echo "  cd $BASE/dev && git worktree list"
``

#!/bin/zsh
if [ -z "$1" ]; then
  echo "Usage: jarvis_commit.sh \"commit message\""
  exit 1
fi
git add -u
git add $(git ls-files --others --exclude-standard | grep -v -f .gitignore 2>/dev/null) 2>/dev/null
git commit -m "$1"
if [ $? -ne 0 ]; then
  git add -u
  git commit -m "$1"
fi
git stash
git pull origin main --rebase
git stash pop
git add -u
git push origin main
echo "Done — $(git log --oneline -1)"

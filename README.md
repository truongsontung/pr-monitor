# PR Monitor

Monitor GitHub PR statuses, reviews, and CI across multiple repositories. Get alerted when CI status changes, new reviews appear, or maintainers comment.

Built for autonomous bug bounty hunters and open-source contributors who need to track PRs across multiple repos.

## Features

- Track PRs across multiple GitHub repositories
- Detect CI status changes (pending → success/failure)
- Detect new human reviews and approvals
- Detect new maintainer comments
- Persist state between runs (detect only changes)
- Optional email alerts

## Installation

```bash
# Clone
git clone https://github.com/truongsontung/pr-monitor.git
cd pr-monitor

# Install dependencies
pip install requests
```

## Configuration

### 1. Set your GitHub token

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
```

### 2. Create a PR config file (`prs.json`)

```json
[
    {"repo": "tenstorrent/tt-metal", "number": 54907, "label": "$750"},
    {"repo": "pytorch/torchtitan", "number": 4294, "label": "SSRF"},
    {"repo": "huggingface/transformers", "number": 48635, "label": "GQA"}
]
```

### 3. (Optional) Set email alerts

```bash
export EMAIL_TO="your@email.com"
```

## Usage

```bash
# Check all PRs (first run sets baseline)
python3 pr_monitor.py

# Subsequent runs detect changes
python3 pr_monitor.py

# Run every hour
watch -n 3600 python3 pr_monitor.py
```

## Output

```
=== PR Status Summary ===
  ✅ 👀 ✅ tenstorrent/tt-metal#54907: CI=success reviews=1 approvals=1
  ⚠️ ⏳   pytorch/torchtitan#4294: CI=pending reviews=0 approvals=0

🚨 1 Alert(s):
  🎉 APPROVED: tenstorrent/tt-metal#54907 [$750] — ready to merge!
```

## How it works

1. Loads PR list from `prs.json`
2. Fetches CI status, reviews, and comments via GitHub API
3. Compares against previous state (stored in `.pr_monitor_state.json`)
4. Reports only changes since last run

## License

MIT

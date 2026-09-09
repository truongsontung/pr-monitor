#!/usr/bin/env python3
"""
PR Monitor: Check GitHub PR statuses and detect review/CI changes.

Track PRs across multiple repositories, get alerted when CI status changes,
new reviews appear, or maintainers comment.

Usage:
    python3 pr_monitor.py [--config prs.json]

Configuration:
    GITHUB_TOKEN  - GitHub API token (required)
    PRS_CONFIG    - JSON file listing PRs to track (default: prs.json)
    STATE_FILE    - JSON file for state persistence (default: .pr_monitor_state.json)
    EMAIL_TO      - Email address for alerts (optional)

Example prs.json:
    [
        {"repo": "tenstorrent/tt-metal", "number": 54907, "label": "$750"},
        {"repo": "pytorch/torchtitan", "number": 4294, "label": "SSRF"}
    ]
"""
import os
import json
import sys
import requests

# --- Configuration ---
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("❌ Error: Set GITHUB_TOKEN environment variable")
    sys.exit(1)

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {TOKEN}"
}

CONFIG_FILE = os.environ.get("PRS_CONFIG", "prs.json")
STATE_FILE = os.environ.get("STATE_FILE", ".pr_monitor_state.json")
EMAIL_TO = os.environ.get("EMAIL_TO", "")


def load_prs():
    """Load PR list from config file."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_state():
    """Load previous PR state."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    """Save current PR state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def send_email_alert(alerts, subject="PR Monitor Alert"):
    """Send email alert via mailbox (if EMAIL_TO is set)."""
    if not EMAIL_TO:
        return

    # Simple SMTP via local sendmail (if available)
    try:
        import subprocess
        body = "\n".join(alerts)
        # This is a simplified version — in production, use proper SMTP
        print(f"[email] To: {EMAIL_TO} | Subject: {subject}")
        print(body)
    except Exception as e:
        print(f"[email] Failed to send: {e}")


def check_prs():
    """Check all PRs and detect changes."""
    prs = load_prs()
    state = load_state()
    new_state = {}
    alerts = []

    for pr_config in prs:
        repo = pr_config["repo"]
        num = pr_config["number"]
        tag = pr_config.get("label", "")

        try:
            # Get PR info
            url = f"https://api.github.com/repos/{repo}/pulls/{num}"
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            pr = r.json()

            # Get CI status
            sha = pr['head']['sha']
            r2 = requests.get(f"https://api.github.com/repos/{repo}/commits/{sha}/status", headers=HEADERS, timeout=30)
            ci = r2.json().get('state', 'unknown')

            # Get reviews
            r3 = requests.get(f"https://api.github.com/repos/{repo}/pulls/{num}/reviews", headers=HEADERS, timeout=30)
            reviews = r3.json()
            human_reviews = [rv for rv in reviews if not rv.get('user', {}).get('login', '').endswith('[bot]')]
            approvals = [rv for rv in human_reviews if rv.get('state') == 'APPROVED']

            # Get recent comments
            r4 = requests.get(f"https://api.github.com/repos/{repo}/issues/{num}/comments", headers=HEADERS, timeout=30)
            comments = r4.json()
            maintainer_comments = [
                c for c in comments
                if not c.get('user', {}).get('login', '').endswith('[bot]')
                and c.get('user', {}).get('login', '') != 'truongsontung'
            ]

            key = f"{repo}#{num}"
            prev = state.get(key, {})

            # Detect CI status change (only alert when transitioning from pending)
            if prev:
                prev_ci = prev.get('ci', '?')
                if prev_ci != ci and ci != 'pending':
                    alerts.append(f"🔄 CI for {key} [{tag}]: {prev_ci} → {ci}")

                # Detect new reviews
                new_review_count = len(human_reviews) - prev.get('human_reviews', 0)
                if new_review_count > 0:
                    prev_ids = set(prev.get('review_ids', []))
                    for rv in human_reviews:
                        if rv.get('id') not in prev_ids:
                            user = rv.get('user', {}).get('login', '')
                            rv_state = rv.get('state', '')
                            emoji = "✅" if rv_state == "APPROVED" else "❓" if rv_state == "CHANGES_REQUESTED" else "👀"
                            alerts.append(f"{emoji} Review on {key} [{tag}] by @{user}: {rv_state}")

                # Detect new maintainer comments
                new_maintainer_comments = len(maintainer_comments) - prev.get('maintainer_comments', 0)
                if new_maintainer_comments > 0:
                    alerts.append(f"💬 New maintainer comment on {key} [{tag}]")

                # Alert if approval received
                new_approvals = len(approvals) - prev.get('approvals', 0)
                if new_approvals > 0:
                    alerts.append(f"🎉 APPROVED: {key} [{tag}] — ready to merge!")

            new_state[key] = {
                'ci': ci,
                'human_reviews': len(human_reviews),
                'approvals': len(approvals),
                'comments': len(comments),
                'maintainer_comments': len(maintainer_comments),
                'review_ids': [rv.get('id') for rv in human_reviews],
                'updated': pr.get('updated_at', ''),
                'url': pr.get('html_url', ''),
            }

        except Exception as e:
            alerts.append(f"⚠️  Error checking {repo}#{num}: {str(e)[:100]}")

    save_state(new_state)
    return alerts, new_state


def print_status(alerts, state):
    """Print summary status."""
    print("\n=== PR Status Summary ===")
    ci_emojis = {"success": "✅", "pending": "⚠️", "failure": "❌"}
    for key, s in state.items():
        ci = ci_emojis.get(s.get('ci', ''), "❓")
        revs = s.get('human_reviews', 0)
        appr = s.get('approvals', 0)
        rev_emoji = "👀" if revs > 0 else "⏳"
        appr_emoji = "✅" if appr > 0 else ""
        print(f"  {ci} {rev_emoji} {appr_emoji} {key}: CI={s.get('ci','?')} reviews={revs} approvals={appr}")

    if alerts:
        print(f"\n🚨 {len(alerts)} Alert(s):")
        for a in alerts:
            print(f"  {a}")
    else:
        print("\n✅ No changes detected since last check")


if __name__ == "__main__":
    alerts, state = check_prs()
    print_status(alerts, state)
    if alerts:
        send_email_alert(alerts)

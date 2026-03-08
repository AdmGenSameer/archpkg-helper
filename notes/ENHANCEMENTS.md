# New Features Summary

## Version: Post-User Mode Enhancement

This document summarizes the three major enhancements added to archpkg-helper to improve the "normal mode" experience and make Arch Linux maintenance more automated and user-friendly.

---

## 1. Trust Score Display in Search Results 🔍

**What it does:**
- Shows trust scores (0-100) for AUR packages directly in search results
- Color-coded display: 
  - 🟢 Green: High trust (75+)
  - 🟡 Yellow: Medium trust (50-74)
  - 🔴 Red: Low trust (<50)

**How to use:**
```bash
archpkg search <package-name>
```

The search results table now includes a "Trust" column showing the score for AUR packages.

**Files modified:**
- `archpkg/cli.py` - Enhanced search results table with trust score column

---

## 2. AUR Package Trust Audit Command 🛡️

**What it does:**
- Audits all installed AUR packages for trust issues
- Checks votes, popularity, maintainer status, and out-of-date status
- Categorizes packages as low/medium/high trust
- Shows warnings for packages needing attention

**How to use:**
```bash
# Show warnings for low-trust packages only
archpkg audit

# Show detailed information for all packages
archpkg audit --verbose

# Show trust scores for all AUR packages
archpkg audit --all

# Custom threshold for warnings (default: 40)
archpkg audit --threshold 60
```

**Trust scoring criteria:**
- Votes: 0-30 points
- Popularity: 0-25 points
- Maintainer: +10 points (has maintainer) or -10 points (orphaned)
- Out-of-date: -20 points if flagged

**Example output:**
```
⚠ WARNING: 2 low-trust package(s) found (score < 40):
  ✗ old-package - Score: 25/100 (low)
  ✗ unmaintained-pkg - Score: 38/100 (low)

✨ 15 high-trust package(s) (score ≥ 70)

💡 Recommendation: Review low-trust packages and consider:
   - Checking if they're still maintained
   - Looking for alternatives with higher trust scores
   - Removing packages you no longer need
```

**Files added:**
- New command `audit` in `archpkg/cli.py` (lines 1723-1886)

---

## 3. Background Monitoring Service 🔔

**What it does:**
- Runs automatically every 6 hours (and 5 minutes after boot)
- Checks for:
  - New Arch news announcements
  - Available system updates
  - Low-trust AUR packages
- Sends desktop notifications when action is recommended
- Only runs in "normal" mode with proactive advice enabled

**How to enable:**
During `archpkg setup`, you'll be prompted:
```
Would you like to enable background monitoring? [Y/n]
```

Or manually install:
```bash
cd /path/to/archpkg-helper
systemd/service-manager.sh install
systemd/service-manager.sh enable
```

**Service management commands:**
```bash
# Check status
systemctl --user status archpkg-monitor.timer

# View logs
journalctl --user -u archpkg-monitor.service -n 50

# Run check immediately
python3 -m archpkg.monitor --once

# Stop service
systemctl --user stop archpkg-monitor.timer

# Start service
systemctl --user start archpkg-monitor.timer

# Disable service
systemd/service-manager.sh disable

# Uninstall service
systemd/service-manager.sh uninstall
```

**Notification examples:**
- "System Maintenance Recommendation: Review 2 new Arch news items"
- "3 System Recommendations: • 15 package updates available • 1 low-trust AUR package detected • Review 1 Arch news item"

**Files added:**
- `archpkg/monitor.py` - Background monitoring logic
- `systemd/archpkg-monitor.service` - Systemd service unit
- `systemd/archpkg-monitor.timer` - Systemd timer unit
- `systemd/service-manager.sh` - Service installation/management helper

**Files modified:**
- `archpkg/cli.py` - Added service installation during `archpkg setup --mode normal`

---

## Technical Details

### Trust Score Calculation Algorithm

```python
score = 0
score += min(votes, 100) * 0.3        # Max 30 points
score += min(popularity * 100, 100) * 0.25  # Max 25 points

if has_maintainer and not orphaned:
    score += 10
else:
    score -= 10

if out_of_date:
    score -= 20

# Normalize to 0-100
score = max(0, min(100, score))
```

### Background Monitoring Schedule

- **Initial run:** 5 minutes after system boot
- **Recurring:** Every 6 hours
- **Persistent:** If system was off, runs on next boot

### System Requirements

- **OS:** Arch Linux or Arch-based distributions
- **AUR Helper:** paru (preferred) or yay
- **Systemd:** Required for background monitoring service
- **Notification:** notify-send (usually pre-installed)

---

## User Experience Flow

### New User Setup (Normal Mode)

1. User runs `archpkg setup` or `install.sh`
2. Selects "normal" profile (recommended)
3. Prompted to enable background monitoring
4. Service installed and enabled automatically
5. First check runs 5 minutes after boot
6. Receives notification if action needed

### Daily Usage

1. User searches for packages → sees trust scores
2. User installs AUR package → automatic trust check
3. Every 6 hours → background check runs
4. User receives notification → takes action if needed
5. User runs `archpkg audit` → reviews installed packages periodically

---

## Benefits

**For End Users:**
- ✅ Proactive system health monitoring
- ✅ No need to remember to check for news/updates
- ✅ Visual trust indicators help make informed decisions
- ✅ Reduced risk of installing low-quality AUR packages
- ✅ Desktop notifications keep them informed

**For Advanced Users:**
- ✅ Can opt-out with "advanced" mode
- ✅ Full manual control still available
- ✅ Service can be disabled/uninstalled easily
- ✅ All features work independently

---

## Testing Checklist

- [x] Trust scores display correctly in search results
- [x] Audit command runs without errors
- [x] Audit command correctly categorizes packages
- [x] Monitor module compiles without errors
- [x] Systemd service files are valid
- [x] Service manager script is executable
- [x] Setup command installs service in normal mode
- [x] Documentation updated in README.md
- [x] All Python files pass compilation check
- [x] All files pass error checking (no linting errors)

---

## Future Enhancements (Optional)

1. Web dashboard for viewing trust audit history
2. Email notifications in addition to desktop notifications
3. Integration with Arch Security Advisory (ASA) feeds
4. Automated trust score trend tracking over time
5. Machine learning-based trust scoring improvements
6. Integration with AUR package comments/feedback

---

## Credits

Developed as part of the archpkg-helper project enhancement phase.
Focus area: Improving user experience for "normal mode" Arch Linux users through automation and proactive system maintenance.

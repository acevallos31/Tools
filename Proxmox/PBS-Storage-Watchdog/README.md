# PBS Storage Watchdog (Raspberry Pi / Docker)

Snapshot of the **deployed** Proxmox Backup Server storage guard and watchdog as discussed on 2026-11-06. Files represent the normal-operation verified configuration; this is **not** a tested disaster-recovery release.

## Purpose

A Raspberry Pi runs Proxmox Backup Server in Docker. The PBS datastore lives on a separately mounted USB SATA SSD. A USB disconnect once left the container running with its datastore unavailable, producing I/O errors and failed PVE backups.

- `pbs-guard.service` checks the expected mount UUID and chunk directory before starting the PBS container. Its `BindsTo` mount dependency can stop PBS if systemd sees the mount unit go away.
- `pbs-storage-watchdog.timer` runs once per minute.
- The watchdog checks UUID, `/dev/disk/by-id`, the chunks directory, and a timed `stat`.
- On the first failed check it logs a warning and queues a WARNING email.
- On the second consecutive failed check it queues CRITICAL and attempts to stop `pbs-guard.service` and the PBS Docker container.
- It queues RECOVERED when the storage check later passes, **but never automatically restarts PBS**.

## File layout

| File | Installed location |
| --- | --- |
| `pbs-storage-watchdog` | `/usr/local/sbin/pbs-storage-watchdog` (root:root, mode 750) |
| `pbs-guard.service` | `/etc/systemd/system/pbs-guard.service` |
| `pbs-storage-watchdog.service` | `/etc/systemd/system/pbs-storage-watchdog.service` |
| `pbs-storage-watchdog.timer` | `/etc/systemd/system/pbs-storage-watchdog.timer` |

The implementation depends on the separately maintained **custom** `/opt/pbs/smart-alerts/pbs-smart-queue` durable SQLite mail queue and its `pbs-smart-queue.service`. It is **not** part of standard PBS; this repository does not ship that dependency.

## Configuration required before reuse

**Do not copy these files onto another host without editing them first.**

1. Replace the mount UUID and `DEVICE` by-id path for the actual SSD.
2. Verify the datastore path (`/mnt/pbs/datastore/datastore/.chunks` in this installation), the name of the Docker container (`pbs`), and the matching systemd mount unit (`mnt-pbs.mount`).
3. Check whether the custom SQLite mail queue is installed and whether `root@localhost` is routed through the PBS notification system. The email transport runs through PBS itself.
4. Ensure Docker's restart policy for this specific PBS container is `no`, otherwise Docker may bypass the guard. Keep the mount managed by `/etc/fstab`/systemd.
5. The source script contains site-specific device identifiers and a generic localhost destination, **not SMTP credentials**.

## Normal-condition checks (read-only)

```bash
sudo bash -n /usr/local/sbin/pbs-storage-watchdog
systemctl is-active pbs-guard.service
systemctl is-active pbs-storage-watchdog.timer
systemctl is-active pbs-smart-queue.timer
findmnt /mnt/pbs -o TARGET,SOURCE,FSTYPE,UUID
sudo docker inspect pbs --format 'Running={{.State.Running}} Health={{.State.Health.Status}} Restart={{.HostConfig.RestartPolicy.Name}}'
sudo /opt/pbs/smart-alerts/pbs-smart-queue status
journalctl -u pbs-storage-watchdog.service -n 20 --no-pager
```

## Important limitations

- **Only healthy-storage execution and an independent queue-to-PBS test email were verified**; a real or simulated SSD failure has not been exercised.
- `stat` may pass using cached filesystem metadata even after physical media loss. This check does not guarantee actual disk I/O.
- `/run` incident flags disappear on reboot. They are not durable incident history; a new boot can reset deduplication.
- The warning/critical message is queued in persistent SQLite storage on the Raspberry Pi NVMe, but sending uses the **PBS container**. If PBS is stopped, critical emails may be delayed until it is manually restarted. A queued notification is not proof of Gmail delivery.
- The watchdog marks `RECOVERED` when **storage** is available, not when PBS is healthy. Its failure state is then cleared.
- A custom restart of the Docker container by another component can bypass the guard.
- `BindsTo` reacts to systemd mount-unit state changes; it does not inherently detect every lower-level USB or I/O fault.
- If the SQLite queue fails to accept a message, this version logs an error but does not retry that message as a distinct alert.
- The watchdog can attempt to stop PBS but should not be treated as guaranteeing a clean shutdown under a fully hung USB I/O path.

## Recovery approach

After a physical storage incident: investigate USB enclosure/cable/power, verify block device and filesystem, validate the UUID and datastore, inspect the watchdog logs and incident status, and **manually** restart `pbs-guard.service` only when storage is healthy. Confirm Docker health and perform a test backup. Do not simulate disk disconnects on a production host solely to test notifications.

The SMTP mechanism for regular PVE/PBS backup notices and the existing SMART queue should be preserved independently.

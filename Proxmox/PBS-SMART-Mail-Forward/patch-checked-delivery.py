#!/usr/bin/env python3
"""Patch pinned upstream Rust sources for honest SMTP handoff acknowledgments.

This is a minimal opt-in deviation from the official source. The stock
proxmox-notify Bus::send swallows endpoint errors and its caller exits 0.
"""

from pathlib import Path


def patch(proxmox_rs: Path, upstream: Path) -> None:
    lib = proxmox_rs / "proxmox-notify/src/lib.rs"
    source = lib.read_text()
    anchor = "    /// Send a test notification to a target (endpoint or group)."
    assert source.count(anchor) == 1
    checked = '''    /// Send and propagate endpoint errors so a durable queue can retry.
    /// A notification without matched/enabled targets is NOT acknowledged.
    pub fn send_checked(&self, notification: &Notification) -> Result<(), Error> {
        let targets = matcher::check_matches(self.matchers.as_slice(), notification);
        if targets.is_empty() {
            return Err(Error::Generic("no notification targets matched".into()));
        }

        let mut sent = 0;
        let mut failures = Vec::new();
        for target in targets {
            match self.endpoints.get(target) {
                Some(endpoint) if endpoint.disabled() => {
                    failures.push(format!("target '{target}' is disabled"));
                }
                Some(endpoint) => match endpoint.send(notification) {
                    Ok(()) => {
                        sent += 1;
                        info!("notified via target `{target}`");
                    }
                    Err(err) => failures.push(format!("target '{target}' failed: {err}")),
                },
                None => failures.push(format!("target '{target}' does not exist")),
            }
        }
        if sent == 0 || !failures.is_empty() {
            return Err(Error::Generic(format!(
                "notification incomplete: sent={sent}; {}",
                failures.join("; ")
            )));
        }
        Ok(())
    }

'''
    lib.write_text(source.replace(anchor, checked + anchor, 1))

    app = upstream / "src/main.rs"
    source = app.read_text()
    call = "    proxmox_notify::api::common::send(config, &notification)?;"
    assert source.count(call) == 1
    source = source.replace(call, "    proxmox_notify::Bus::from_config(config)?.send_checked(&notification)?;", 1)
    main = "fn main() {"
    assert source.count(main) == 1
    source = source[:source.index(main)] + '''fn main() {
    if std::env::args().any(|arg| arg == "--pbs-smart-queue-protocol") {
        println!("checked-delivery-v1");
        return;
    }
    if let Err(err) = Logger::from_env("PROXMOX_LOG", LevelFilter::INFO)
        .journald()
        .init()
    {
        eprintln!("unable to initialize syslog: {err}");
    }

    if let Err(err) = forward_mail() {
        eprintln!("could not forward mail: {err:#}");
        std::process::exit(1);
    }
}

fn forward_mail() -> Result<(), Error> {
    let mail = read_stdin()?;
    let has_pve = Path::new(PVE_CFG_PATH).exists();
    let has_pbs = Path::new(PBS_CFG_PATH).exists();
    if !has_pve && !has_pbs {
        anyhow::bail!("neither PVE nor PBS config directory exists");
    }
    if has_pve {
        forward_for_pve(&mail)?;
    }
    if has_pbs {
        forward_for_pbs(&mail, has_pve)?;
    }
    Ok(())
}
'''
    app.write_text(source)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch-checked-delivery.py proxmox-rs upstream")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))

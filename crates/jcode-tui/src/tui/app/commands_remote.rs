use super::{App, DisplayMessage};
use crate::gateway::control::{
    RemoteCommand, RemoteStatus, ToggleOutcome, create_pairing_invite, parse_remote_command,
    revoke_device, set_gateway_enabled,
};

const REMOTE_HELP: &str = "\
**`/remote`** - use jcode from any device

`/remote` opens your Jcode account, the entry point for Jcode Cloud access.
Cloud is being bundled with eligible Jcode subscriptions. The managed host
control plane is currently in early access.

- `/remote` or `/remote cloud` - activate or manage Jcode Cloud
- `/remote status` - local gateway state, dial address, paired devices
- `/remote on` / `/remote off` - enable or disable the gateway
- `/remote pair` - show a pairing code and QR for a new device
- `/remote revoke <device>` - remove a paired device

For self-hosting, run `/remote on`, restart the server, then `/remote pair`.
";

const CLOUD_ACCOUNT_URL: &str = "https://jcode.sh/account";

pub(super) fn handle_remote_command(app: &mut App, trimmed: &str) -> bool {
    let Some(parsed) = parse_remote_command(trimmed) else {
        return false;
    };

    match parsed {
        Err(message) => app.push_display_message(DisplayMessage::error(message)),
        Ok(RemoteCommand::Help) => {
            app.push_display_message(DisplayMessage::system(REMOTE_HELP.to_string()));
            app.set_status_notice("Помощь по удаленному доступу");
        }
        Ok(RemoteCommand::Cloud) => activate_cloud(app),
        Ok(RemoteCommand::Status) => show_status(app),
        Ok(RemoteCommand::On) => toggle(app, true),
        Ok(RemoteCommand::Off) => toggle(app, false),
        Ok(RemoteCommand::Pair) => show_pairing_invite(app),
        Ok(RemoteCommand::Revoke(target)) => revoke(app, &target),
    }

    true
}

fn activate_cloud(app: &mut App) {
    let signed_in = crate::subscription_catalog::has_credentials();
    let tier = crate::subscription_catalog::cached_tier();
    let account_line = if signed_in {
        match tier {
            Some(tier) => format!("Signed in on the **{}** plan.", tier.display_name()),
            None => "Вы вошли в свой аккаунт Jcode.".to_string(),
        }
    } else {
        "Вы еще не вошли. Страница аккаунта проведет вас через процесс входа без пароля и настройку подписки."
            .to_string()
    };

    let opened = super::helpers::open_path_or_url_detached(CLOUD_ACCOUNT_URL).is_ok();
    let open_line = if opened {
        "Открыта страница вашего безопасного аккаунта Jcode в браузере."
    } else {
        "Откройте страницу вашего безопасного аккаунта Jcode:"
    };
    app.push_display_message(DisplayMessage::system(format!(
        "**Jcode Cloud early access**\n\n{account_line}\n\n{open_line}\n\n{CLOUD_ACCOUNT_URL}\n\n\
         The managed-host control plane is not generally available yet. Reference hosts wake on \
         demand and stop when idle. To use your own machine now, run \
         `/remote on`, restart the server, then `/remote pair`."
    )));
    app.set_status_notice(if opened {
        "Аккаунт Jcode Cloud открыт"
    } else {
        "Ссылка на аккаунт Jcode Cloud готова"
    });
}

fn show_status(app: &mut App) {
    let status = RemoteStatus::load();
    app.push_display_message(DisplayMessage::system(status.to_markdown()));
    app.set_status_notice(if status.enabled {
        "Удаленный доступ включен"
    } else {
        "Удаленный доступ выключен"
    });
}

fn toggle(app: &mut App, enabled: bool) {
    match set_gateway_enabled(enabled) {
        Ok(ToggleOutcome::Unchanged { .. }) => {
            app.push_display_message(DisplayMessage::system(format!(
                "Удаленный доступ уже **{}**.",
                if enabled { "on" } else { "off" }
            )));
        }
        Ok(ToggleOutcome::Changed { .. }) => {
            // The listener binds during server startup, so a config change
            // alone does not open or close the port.
            let body = if enabled {
                let status = RemoteStatus::load();
                format!(
                    "Remote access **enabled** on port `{}`.\n\n\
                     Restart the server to open the port:\n\n\
                     ```\njcode server reload\n```\n\n\
                     Then run `/remote pair` to authorize a device.\n\n\
                     Other machines will dial `{}`.\n",
                    status.port,
                    status.dial_address()
                )
            } else {
                "Remote access **disabled**.\n\n\
                 Restart the server to close the port:\n\n\
                 ```\njcode server reload\n```\n\n\
                 Paired devices are kept; use `/remote revoke <device>` to remove them.\n"
                    .to_string()
            };
            app.push_display_message(DisplayMessage::system(body));
            app.set_status_notice(if enabled {
                "Удаленный доступ включен (требуется перезапуск)"
            } else {
                "Удаленный доступ выключен (требуется перезапуск)"
            });
        }
        Err(error) => app.push_display_message(DisplayMessage::error(format!(
            "Не удалось обновить удаленный доступ: {}",
            crate::util::format_error_chain(&error)
        ))),
    }
}

fn show_pairing_invite(app: &mut App) {
    match create_pairing_invite() {
        Ok(invite) => {
            let mut body = String::from("**Pair a device**\n\n");

            if !invite.gateway_enabled {
                body.push_str(
                    "Remote access is currently **off**, so this code cannot be used yet. \
                     Run `/remote on` and restart the server first.\n\n",
                );
            }

            body.push_str(&format!(
                "- Pairing code: **{}** (expires in 5 minutes)\n- Connect to: `{}`\n",
                invite.spaced_code(),
                invite.dial_address
            ));

            if let Ok(qr) = crate::login_qr::render_unicode_qr(&invite.uri) {
                body.push_str("\n```\n");
                body.push_str(&qr);
                body.push_str("\n```\n");
            }

            app.push_display_message(DisplayMessage::system(body));
            app.set_status_notice("Код сопряжения готов");
        }
        Err(error) => app.push_display_message(DisplayMessage::error(format!(
            "Не удалось создать код сопряжения: {}",
            crate::util::format_error_chain(&error)
        ))),
    }
}

fn revoke(app: &mut App, target: &str) {
    match revoke_device(target) {
        Ok(removed) if removed.is_empty() => {
            app.push_display_message(DisplayMessage::error(format!(
                "Нет сопряженного устройства, соответствующего `{target}`. Выполните `/remote status` для списка устройств."
            )));
        }
        Ok(removed) => {
            app.push_display_message(DisplayMessage::system(format!(
                "Отозвано {}. Это устройство должно снова выполнить сопряжение для повторного подключения.",
                removed
                    .iter()
                    .map(|name| format!("`{name}`"))
                    .collect::<Vec<_>>()
                    .join(", ")
            )));
            app.set_status_notice("Устройство отозвано");
        }
        Err(error) => app.push_display_message(DisplayMessage::error(format!(
            "Не удалось отозвать устройство: {}",
            crate::util::format_error_chain(&error)
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `/remote` and `/remote-release` share a prefix, and only dispatch order
    /// plus the parser's whitespace rule keep them apart. Assert the boundary
    /// so a later edit cannot silently steal the other command's input.
    #[test]
    fn remote_parser_does_not_claim_remote_release() {
        assert_eq!(parse_remote_command("/remote-release"), None);
        assert_eq!(
            parse_remote_command("/remote"),
            Some(Ok(RemoteCommand::Cloud))
        );
    }

    /// The help text is the discoverability surface; keep it in sync with the
    /// subcommands the parser actually accepts.
    #[test]
    fn help_documents_every_supported_subcommand() {
        for sub in ["cloud", "status", "on", "off", "pair", "revoke"] {
            assert!(
                REMOTE_HELP.contains(sub),
                "помощь должна документировать /remote {sub}"
            );
            assert!(
                parse_remote_command(&format!("/remote {sub} x")).is_some(),
                "парсер должен распознавать /remote {sub}"
            );
        }
    }
}

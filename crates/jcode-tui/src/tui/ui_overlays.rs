use super::{
    accent_color, ai_color, ai_text, asap_color, clear_area, dim_color, get_grouped_changelog,
    header_icon_color, header_name_color, header_session_color, pending_color, queued_color,
    record_chat_overlay_copy_snapshot, rgb, tool_color, user_bg, user_color, user_text,
};
use crate::tui::TuiState;
use crate::tui::info_widget::WidgetPlacement;
use ratatui::{
    prelude::*,
    widgets::{Block, Borders, Paragraph},
};

use super::selection_highlight::highlight_line_selection;

pub(super) fn draw_changelog_overlay(
    frame: &mut Frame,
    area: Rect,
    scroll: usize,
    app: &dyn TuiState,
) {
    clear_area(frame, area);

    let groups = get_grouped_changelog();
    let mut lines: Vec<Line<'static>> = Vec::new();

    if groups.is_empty() {
        lines.push(Line::from(Span::styled(
            "Нет доступных записей журнала изменений.",
            Style::default().fg(dim_color()),
        )));
    } else {
        for group in &groups {
            let heading = match &group.released_at {
                Some(released_at) => format!("  {} · {}", group.version, released_at),
                None => format!("  {}", group.version),
            };
            lines.push(Line::from(Span::styled(
                heading,
                Style::default()
                    .fg(rgb(200, 200, 220))
                    .add_modifier(Modifier::BOLD),
            )));
            lines.push(Line::from(""));
            for entry in &group.entries {
                lines.push(Line::from(vec![
                    Span::styled("    • ", Style::default().fg(dim_color())),
                    Span::styled(entry.clone(), Style::default().fg(rgb(170, 170, 185))),
                ]));
            }
            lines.push(Line::from(""));
        }
    }

    let total_lines = lines.len();
    let visible_height = area.height.saturating_sub(2) as usize;
    let max_scroll = total_lines.saturating_sub(visible_height);
    let scroll = scroll.min(max_scroll);

    let scroll_info = if total_lines > visible_height {
        let pct = if max_scroll > 0 {
            (scroll * 100) / max_scroll
        } else {
            100
        };
        format!(" {}% ", pct)
    } else {
        String::new()
    };

    let title = format!(" Журнал изменений {}", scroll_info);
    let block = Block::default()
        .title(Span::styled(
            title,
            Style::default()
                .fg(rgb(200, 200, 220))
                .add_modifier(Modifier::BOLD),
        ))
        .title_bottom(Line::from(Span::styled(
            " Esc для закрытия · перетащите для выбора, отпустите для копирования · прокрутка колесом/j/k",
            Style::default().fg(dim_color()),
        )))
        .borders(Borders::ALL)
        .border_style(Style::default().fg(dim_color()));

    let inner = block.inner(area);
    frame.render_widget(block, area);

    if inner.width == 0 || inner.height == 0 {
        return;
    }

    let visible_end = scroll
        .saturating_add(inner.height as usize)
        .min(total_lines);

    // Register the rendered lines so the shared copy-selection machinery can map
    // mouse drags to text and highlight + copy the selection, exactly like the
    // chat viewport. Without this, mouse capture would block native terminal
    // selection and there would be no way to copy from the overlay.
    record_chat_overlay_copy_snapshot(&lines, scroll, visible_end, inner);

    let mut visible_lines: Vec<Line<'static>> =
        lines.get(scroll..visible_end).unwrap_or(&[]).to_vec();

    if let Some(range) = app.copy_selection_range().filter(|range| {
        range.start.pane == crate::tui::CopySelectionPane::Chat
            && range.end.pane == crate::tui::CopySelectionPane::Chat
    }) {
        let (start, end) = if (range.start.abs_line, range.start.column)
            <= (range.end.abs_line, range.end.column)
        {
            (range.start, range.end)
        } else {
            (range.end, range.start)
        };
        for abs_idx in start.abs_line.max(scroll)..=end.abs_line.min(visible_end.saturating_sub(1))
        {
            let rel_idx = abs_idx.saturating_sub(scroll);
            if let Some(line) = visible_lines.get_mut(rel_idx) {
                let start_col = if abs_idx == start.abs_line {
                    start.column
                } else {
                    0
                };
                let end_col = if abs_idx == end.abs_line {
                    end.column
                } else {
                    line.width()
                };
                *line = highlight_line_selection(line, start_col, end_col);
            }
        }
    }

    frame.render_widget(Paragraph::new(visible_lines), inner);
}

pub(super) fn draw_help_overlay(frame: &mut Frame, area: Rect, scroll: usize, app: &dyn TuiState) {
    clear_area(frame, area);

    let section_style = Style::default()
        .fg(accent_color())
        .add_modifier(Modifier::BOLD);
    let cmd_style = Style::default().fg(rgb(230, 230, 240));
    let desc_style = Style::default().fg(rgb(150, 150, 165));
    let key_style = Style::default().fg(rgb(200, 180, 120));
    let sep_style = Style::default().fg(rgb(50, 50, 55));

    let mut lines: Vec<Line<'static>> = Vec::new();

    let separator = || -> Line<'static> {
        Line::from(Span::styled(
            "  ─────────────────────────────────────────────────",
            sep_style,
        ))
    };

    let help_entry = |cmd: &str, desc: &str| -> Line<'static> {
        Line::from(vec![
            Span::styled("    ", Style::default()),
            Span::styled(cmd.to_string(), cmd_style),
            Span::styled("  ", Style::default()),
            Span::styled(desc.to_string(), desc_style),
        ])
    };

    let alt = jcode_tui_core::keybind::alt_chord;
    let key_entry = |key: &str, desc: &str| -> Line<'static> {
        Line::from(vec![
            Span::styled("    ", Style::default()),
            Span::styled(format!("{:<22}", key), key_style),
            Span::styled(desc.to_string(), desc_style),
        ])
    };

    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled(" Команды", section_style)));
    lines.push(Line::from(""));
    lines.push(help_entry("/help", "Показать это окно справки"));
    lines.push(help_entry(
        "/help <command>",
        "Показать детали для одной команды",
    ));
    lines.push(help_entry("/model", "Список или переключение моделей"));
    lines.push(help_entry("/model <name>", "Переключиться на другую модель"));
    lines.push(help_entry(
        "/provider-test-coverage",
        "Показать доказательства живого тестирования для текущего провайдера/модели",
    ));
    lines.push(help_entry("/agents", "Настроить модели для ролей агентов"));
    lines.push(help_entry(
        "/swarm-prompt",
        "Открыть активный запрос маршрутизации роя в вашем редакторе",
    ));
    lines.push(help_entry(
        "/effort <level>",
        "Установить усилие (none|minimal|low|medium|high|xhigh|max|swarm|swarm-deep)",
    ));
    lines.push(help_entry(
        "/fast [on|off|status|default ...]",
        "Переключить быстрый режим",
    ));
    lines.push(help_entry(
        "/transport <mode>",
        "Установить транспорт соединения (auto|https|websocket)",
    ));
    lines.push(help_entry(
        "/alignment [status|centered|left]",
        "Показать или сохранить предпочтение выравнивания текста",
    ));
    lines.push(help_entry(
        "/compact-notifications [status|on|off]",
        "Свернуть уведомления роя/файлов в одну строку",
    ));
    lines.push(help_entry(
        "/show-agentgrep-output [status|on|off]",
        "Отображать полный вывод поиска agentgrep в чате",
    ));
    lines.push(help_entry("/config", "Показать активную конфигурацию"));
    lines.push(help_entry("/config init", "Создать файл конфигурации по умолчанию"));
    lines.push(help_entry("/config edit", "Открыть конфигурацию в $EDITOR"));
    lines.push(help_entry("/dictate", "Запустить настроенное внешнее диктование"));
    lines.push(help_entry(
        "/git [status]",
        "Показать статус ветки и рабочего дерева для репозитория",
    ));
    lines.push(help_entry(
        "/context",
        "Показать полный снимок контекста сессии",
    ));
    lines.push(help_entry(
        "/skills",
        "Показать загруженные навыки и рекомендации от jcode",
    ));
    lines.push(help_entry("/info", "Показать информацию о сессии и использование токенов"));
    lines.push(help_entry(
        "/keys",
        "Показать конфликты клавиш с вашим терминалом/ОС",
    ));
    lines.push(help_entry("/usage", "Показать лимиты использования подключенного провайдера"));
    lines.push(help_entry(
        "/support",
        "Отправить электронное письмо в службу поддержки с предзаполненной диагностикой",
    ));
    lines.push(help_entry("/version", "Показать версию и детали сборки"));
    lines.push(help_entry(
        "/changelog",
        "Показать последние изменения в этой сборке",
    ));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled(" Сессия", section_style)));
    lines.push(Line::from(""));
    lines.push(help_entry("/clear", "Очистить разговор и начать заново"));
    lines.push(help_entry(
        "/compact",
        "Обобщить старые сообщения для освобождения контекста",
    ));
    lines.push(help_entry(
        "/rewind",
        "Показать историю с номерами, /rewind N для перемотки",
    ));
    lines.push(help_entry(
        "/fix",
        "Попытаться восстановить работу, когда модель не может продолжить",
    ));
    lines.push(help_entry(
        "/poke",
        "Стимулировать модель к возобновлению с незавершенными задачами (on/off/status)",
    ));
    lines.push(help_entry(
        "/plan [goal]",
        "Создать план-карточку только с предложением (без правок)",
    ));
    lines.push(help_entry(
        "/improve",
        "Автономно улучшать репозиторий до снижения отдачи",
    ));
    lines.push(help_entry(
        "/improve resume",
        "Возобновить последний сохраненный цикл/план улучшения",
    ));
    lines.push(help_entry(
        "/refactor",
        "Запустить безопасный цикл рефакторинга с независимым обзором",
    ));
    lines.push(help_entry(
        "/refactor resume",
        "Возобновить последний сохраненный цикл/план рефакторинга",
    ));
    lines.push(help_entry(
        "/splitview [on|off|status]",
        "Отразить текущий чат в боковой панели",
    ));
    lines.push(help_entry(
        "/fork [prompt]",
        "Разделить сессию в новое окно (псевдоним: /split)",
    ));
    lines.push(help_entry(
        "/transfer",
        "Открыть новую сессию только с обобщенным контекстом + скопированными задачами",
    ));
    lines.push(help_entry(
        "/workspace [status|on|off|add]",
        "Включить и управлять рабочей областью сессии в стиле Niri",
    ));
    lines.push(help_entry(
        "/catchup [next|list]",
        "Перейти к завершенным сессиям и открыть краткий обзор",
    ));
    lines.push(help_entry(
        "/back",
        "Вернуться к предыдущей исходной сессии обзора",
    ));
    lines.push(help_entry("/resume", "Просмотреть и возобновить предыдущие сессии"));
    lines.push(help_entry(
        "/active",
        "Управление активными сессиями: просмотр работающих и готовых",
    ));
    lines.push(help_entry(
        "/catchup [next]",
        "Переход к завершенным сессиям с кратким описанием",
    ));
    lines.push(help_entry(
        "/back",
        "Возврат к предыдущей сессии Catch Up",
    ));
    lines.push(help_entry("/save [метка]", "Сохранить сессию для /resume"));
    lines.push(help_entry(
        "/rename <имя>|--clear",
        "Установить или очистить имя текущей сессии",
    ));
    lines.push(help_entry(
        "/unsave",
        "Удалить закладку из текущей сессии",
    ));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled("  Память и Рой", section_style)));
    lines.push(Line::from(""));
    lines.push(help_entry("/memory [on|off]", "Переключить функции памяти"));
    lines.push(help_entry(
        "/test [утверждение]",
        "Выполнить многоуровневую проверку и создать доказательство",
    ));
    lines.push(help_entry(
        "/initiatives",
        "Открыть обзор инициатив / возобновить инициативу",
    ));
    lines.push(help_entry("/swarm [on|off]", "Переключить функции роя"));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled("  Аутентификация и Аккаунты", section_style)));
    lines.push(Line::from(""));
    lines.push(help_entry("/auth", "Показать статус аутентификации"));
    lines.push(help_entry(
        "/login [провайдер]",
        "Интерактивный или прямой вход",
    ));
    lines.push(help_entry(
        "/account",
        "Открыть выбор аккаунтов Claude/OpenAI",
    ));
    lines.push(help_entry(
        "/subscription",
        "Проверить каркас подписки jcode",
    ));
    lines.push(help_entry(
        "/subscribe",
        "Зачем и как подписаться на jcode",
    ));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled("  Система", section_style)));
    lines.push(Line::from(""));
    lines.push(help_entry("/reload", "Перезагрузить в более новую версию если доступна"));
    lines.push(help_entry(
        "/restart",
        "Перезапустить с текущей версией (без сборки)",
    ));
    lines.push(help_entry(
        "/rebuild",
        "Полное обновление (git pull + сборка + тесты)",
    ));
    if app.is_remote_mode() {
        lines.push(help_entry("/client-reload", "Принудительно перезагрузить клиентскую версию"));
        lines.push(help_entry("/server-reload", "Принудительно перезагрузить серверную версию"));
        lines.push(help_entry(
            "/continue",
            "Продолжить каждую прерванную активную сессию которая бы возобновилась автоматически",
        ));
    }
    lines.push(help_entry(
        "/debug-visual",
        "Включить визуальную отладку для проблем TUI",
    ));
    lines.push(help_entry("/quit", "Выйти из jcode"));

    // The sections above are hand-curated for ordering, but they drift as
    // commands are added. Anything registered and not already shown gets listed
    // here so no working command is invisible in /help.
    let shown: std::collections::HashSet<String> = lines
        .iter()
        .filter_map(|line| line.spans.get(1).map(|span| span.content.to_string()))
        .map(|cmd| {
            cmd.split_whitespace()
                .next()
                .unwrap_or_default()
                .to_string()
        })
        .collect();
    let uncovered: Vec<(&str, &str)> = crate::tui::app::registered_command_entries()
        .filter(|(name, _)| !shown.contains(*name))
        .collect();
    if !uncovered.is_empty() {
        lines.push(Line::from(""));
        lines.push(separator());
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled("  Другие команды", section_style)));
        lines.push(Line::from(""));
        for (name, desc) in uncovered {
            lines.push(help_entry(name, desc));
        }
    }

    let skills = app.available_skills();
    if !skills.is_empty() {
        lines.push(Line::from(""));
        lines.push(separator());
        lines.push(Line::from(""));

        lines.push(Line::from(Span::styled("  Навыки", section_style)));
        lines.push(Line::from(""));
        for skill in &skills {
            lines.push(help_entry(&format!("/{}", skill), "Активировать навык"));
        }
    }

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled("  Навигация", section_style)));
    lines.push(Line::from(""));
    lines.push(key_entry("PageUp / PageDown", "Прокрутка истории"));
    lines.push(key_entry("Вверх / Вниз", "Прокрутка истории (когда поле ввода пустое)"));
    lines.push(key_entry(
        "Ctrl+J / Ctrl+K",
        "Переход к следующему / предыдущему запросу пользователя (также Ctrl+] / Ctrl+[)",
    ));
    lines.push(key_entry(
        "Ctrl+Shift+J / Ctrl+Shift+K",
        "Прокрутить историю вниз / вверх на одну строку",
    ));
    lines.push(key_entry(
        "Cmd/Super+K / J",
        "Переход к предыдущему / следующему запросу пользователя (macOS, если перенаправлено)",
    ));
    lines.push(key_entry("Ctrl+1..4", "Изменить размер боковой панели до 25/50/75/100%"));
    lines.push(key_entry(
        "Ctrl+5..9",
        "Переход по давности (5 = 5-я по свежести)",
    ));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled(
        "  Диаграммы и Сравнения",
        section_style,
    )));
    lines.push(Line::from(""));
    lines.push(key_entry(
        &crate::tui::keybind::side_panel_toggle_key_label(),
        "Переключить боковую панель (или панель диаграмм если пусто)",
    ));
    lines.push(key_entry(&alt("T"), "Переключить положение диаграммы (сбоку/сверху)"));
    lines.push(key_entry(
        &alt("Shift+I"),
        "Показать/скрыть встроенные изображения (сохраняется)",
    ));
    lines.push(key_entry("Ctrl+H / Ctrl+L", "Фокус на чат / диаграмму / сравнения"));
    lines.push(key_entry(
        "Ctrl+L / Cmd+L",
        "Очистить экран, история остается выше (никакая панель не в фокусе)",
    ));
    lines.push(key_entry(
        "Ctrl+Left / Right",
        "Циклический переход между диаграммами (когда диаграмма в фокусе)",
    ));
    lines.push(key_entry("h/j/k/l / стрелки", "Панорамирование диаграммы (когда в фокусе)"));
    lines.push(key_entry("[ / ]", "Масштабирование диаграммы (когда в фокусе)"));
    lines.push(key_entry("+ / -", "Изменить размер панели диаграммы"));
    lines.push(key_entry(
        &format!("{} / /diff", alt("G")),
        "Циклический режим сравнения (Выкл/Встроенный/Закрепленный/Файл)",
    ));
    lines.push(key_entry("Shift+Tab", "Циклический переход между избранными моделями"));
    lines.push(key_entry("Ctrl+O", "Установить модель по умолчанию (в выборе /model)"));
    lines.push(key_entry(
        "Ctrl+N",
        "Добавить/убрать модель из избранного (в выборе /model)",
    ));

    lines.push(Line::from(""));
    lines.push(separator());
    lines.push(Line::from(""));

    lines.push(Line::from(Span::styled("  Ввод и Редактирование", section_style)));
    lines.push(Line::from(""));
    lines.push(key_entry(
        "Ctrl+C / Ctrl+D",
        "Выход (нажмите дважды для подтверждения)",
    ));
    lines.push(key_entry("Ctrl+X", "Вырезать всю строку ввода в буфер обмена"));
    lines.push(key_entry(
        "Ctrl+A",
        "Копировать видимую область чата плюс контекст поблизости",
    ));
    lines.push(key_entry("Очистить строку ввода", "Ctrl+U"));
    lines.push(key_entry("Ctrl+K", "Удалить до конца строки ввода"));
    lines.push(key_entry(
        &format!("{} / {}", alt("Backspace"), alt("Delete")),
        "Удалить предыдущее слово во вводе",
    ));
    lines.push(key_entry(
        "Cmd/Super+Backspace / Delete",
        "Удалить предыдущее слово во вводе",
    ));
    if cfg!(target_os = "macos") {
        // On macOS, Cmd+Left/Right default to effort cycling; Home/End and
        // Cmd+A/E still jump to the start/end of the input.
        lines.push(key_entry("Home / End", "Перейти к началу / концу строки ввода"));
    } else {
        lines.push(key_entry(
            "Cmd/Super+Left / Right",
            "Перейти к началу / концу строки ввода",
        ));
    }
    lines.push(key_entry("Cmd/Super+Z", "Отменить редактирование ввода"));
    lines.push(key_entry("Cmd/Super+X / V", "Вырезать ввод / вставить из буфера обмена"));
    lines.push(key_entry("Ctrl+S", "Спрятать / вернуть ввод (сохранить на потом)"));
    lines.push(key_entry("Ctrl+Backspace", "Удалить предыдущее слово во вводе"));
    lines.push(key_entry("Ctrl+B / Ctrl+F", "Перемещение по словам влево / вправо"));
    lines.push(key_entry("Ctrl+Left / Right", "Перемещение по словам влево / вправо"));
    lines.push(key_entry(
        &format!("Shift+Enter / {}", alt("Enter")),
        "Вставить новую строку во входные данные",
    ));
    lines.push(key_entry(
        "Trailing \\ then Enter",
        "Вставить новую строку (резервный вариант; запустите /terminal-setup для исправления Shift+Enter)",
    ));
    lines.push(key_entry(
        "Ctrl+Enter / Cmd+Enter",
        "Использовать противоположный режим отправки во время обработки",
    ));
    lines.push(key_entry("Ctrl+Up", "Получить ожидающее сообщение для редактирования"));
    lines.push(key_entry("Ctrl+Tab / Ctrl+T", "Переключить режим очереди"));
    lines.push(key_entry(
        "Ctrl+R",
        "Поиск в истории запросов (между сессиями)",
    ));
    lines.push(key_entry(
        &format!("Ctrl+V / {}", alt("V")),
        "Вставить из буфера обмена (текст или изображение)",
    ));
    lines.push(key_entry(
        &alt("A"),
        "Быстрое копирование видимой области чата плюс контекст поблизости",
    ));
    lines.push(key_entry(&alt("Y"), "Переключить режим выбора/копирования чата"));
    lines.push(key_entry(&alt("S"), "Переключить блокировку прокрутки при наборе"));
    lines.push(key_entry("Ctrl+P", "Переключить автоматическое уведомление о неполных задачах"));
    lines.push(key_entry(&alt("X"), "Показать/скрыть карточку списка задач в чате"));
    lines.push(key_entry(
        &crate::tui::keybind::effort_switch_keys_label(),
        "Цикл усилия (рассуждение + рой)",
    ));
    if cfg!(target_os = "macos") {
        lines.push(key_entry(
            &alt("Left / Right"),
            &format!("Перемещение по словам во входных данных (также {} / {})", alt("B"), alt("F")),
        ));
    }
    if let Some(label) = app.dictation_key_label() {
        lines.push(key_entry(&label, "Запустить настроенное диктование"));
    }
    if let Some(label) = crate::tui::keybind::load_open_resume_key().label {
        lines.push(key_entry(&label, "Открыть выбор сессии /resume"));
    }
    if let Some(label) = crate::tui::keybind::load_new_terminal_key().label {
        lines.push(key_entry(
            &label,
            "Создать новую сессию jcode в новом терминале",
        ));
    }

    lines.push(Line::from(""));

    let total_lines = lines.len();
    let visible_height = area.height.saturating_sub(2) as usize;
    let max_scroll = total_lines.saturating_sub(visible_height);
    let scroll = scroll.min(max_scroll);

    let scroll_info = if total_lines > visible_height {
        let pct = if max_scroll > 0 {
            (scroll * 100) / max_scroll
        } else {
            100
        };
        format!(" {}% ", pct)
    } else {
        String::new()
    };

    let title = format!(" Help {}", scroll_info);
    let block = Block::default()
        .title(Span::styled(
            title,
            Style::default()
                .fg(rgb(200, 200, 220))
                .add_modifier(Modifier::BOLD),
        ))
        .title_bottom(Line::from(Span::styled(
            " Esc для закрытия · колесо мыши/j/k для прокрутки · Пробел/PageUp страница · /help <cmd> для деталей",
            Style::default().fg(dim_color()),
        )))
        .borders(Borders::ALL)
        .border_style(Style::default().fg(dim_color()));

    let paragraph = Paragraph::new(lines)
        .block(block)
        .scroll((scroll as u16, 0));

    frame.render_widget(paragraph, area);
}

pub(super) fn draw_model_status_overlay(
    frame: &mut Frame,
    area: Rect,
    scroll: usize,
    content: &str,
) {
    clear_area(frame, area);

    let title_style = Style::default()
        .fg(accent_color())
        .add_modifier(Modifier::BOLD);
    let text_style = Style::default().fg(rgb(210, 210, 220));
    let dim_style = Style::default().fg(dim_color());

    let mut lines: Vec<Line<'static>> = Vec::new();
    lines.push(Line::from(Span::styled("  Статус модели", title_style)));
    lines.push(Line::from(Span::styled(
        "  Доказательства проверки работы провайдера/модели в jcode",
        dim_style,
    )));
    lines.push(Line::from(""));

    for raw in content.lines() {
        if let Some(title) = raw.strip_prefix("# ") {
            lines.push(Line::from(Span::styled(format!("  {title}"), title_style)));
        } else if let Some(title) = raw.strip_prefix("## ") {
            lines.push(Line::from(Span::styled(format!("  {title}"), title_style)));
        } else if raw.trim().is_empty() {
            lines.push(Line::from(""));
        } else {
            lines.push(Line::from(Span::styled(
                format!("  {raw}"),
                model_status_line_style(raw, text_style),
            )));
        }
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "  ↑/↓ прокрутка, PgUp/PgDn страница, c копировать отчет, q/Esc закрыть",
        dim_style,
    )));

    let paragraph = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(" /provider-test-coverage"),
        )
        .scroll((scroll.min(u16::MAX as usize) as u16, 0));
    frame.render_widget(paragraph, area);
}

fn model_status_line_style(raw: &str, default: Style) -> Style {
    // Reuse the same semantic classification the CLI uses so the TUI overlay
    // and `jcode provider-test-coverage` stay color-consistent.
    use crate::live_tests::CoverageLineStyle;
    match crate::live_tests::classify_provider_test_coverage_line(raw) {
        CoverageLineStyle::Title => Style::default()
            .fg(accent_color())
            .add_modifier(Modifier::BOLD),
        CoverageLineStyle::Pass => Style::default().fg(rgb(120, 220, 150)),
        CoverageLineStyle::Fail => Style::default().fg(rgb(240, 110, 110)),
        CoverageLineStyle::Warn => Style::default().fg(rgb(235, 190, 105)),
        CoverageLineStyle::Dim => Style::default().fg(dim_color()),
        CoverageLineStyle::Plain => default,
    }
}

pub(super) fn draw_debug_overlay(
    frame: &mut Frame,
    placements: &[WidgetPlacement],
    chunks: &[Rect],
) {
    if chunks.len() < 5 {
        return;
    }
    render_overlay_box(frame, chunks[0], "messages", Color::Red);
    render_overlay_box(frame, chunks[1], "queued", Color::Yellow);
    render_overlay_box(frame, chunks[2], "status", Color::Cyan);
    render_overlay_box(frame, chunks[3], "picker", Color::Magenta);
    render_overlay_box(frame, chunks[4], "input", Color::Green);
    if chunks.len() > 5 && chunks[5].height > 0 {
        render_overlay_box(frame, chunks[5], "donut", Color::Blue);
    }

    for placement in placements {
        let title = format!("widget:{}", placement.kind.as_str());
        render_overlay_box(frame, placement.rect, &title, Color::Magenta);
    }
}

fn render_overlay_box(frame: &mut Frame, area: Rect, title: &str, color: Color) {
    if area.width == 0 || area.height == 0 {
        return;
    }
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(color))
        .title(Span::styled(title.to_string(), Style::default().fg(color)));
    frame.render_widget(block, area);
}

pub(super) fn debug_palette_json() -> Option<serde_json::Value> {
    Some(serde_json::json!({
        "user_color": color_to_rgb(user_color()),
        "ai_color": color_to_rgb(ai_color()),
        "tool_color": color_to_rgb(tool_color()),
        "dim_color": color_to_rgb(dim_color()),
        "accent_color": color_to_rgb(accent_color()),
        "queued_color": color_to_rgb(queued_color()),
        "asap_color": color_to_rgb(asap_color()),
        "pending_color": color_to_rgb(pending_color()),
        "user_text": color_to_rgb(user_text()),
        "user_bg": color_to_rgb(user_bg()),
        "ai_text": color_to_rgb(ai_text()),
        "header_icon_color": color_to_rgb(header_icon_color()),
        "header_name_color": color_to_rgb(header_name_color()),
        "header_session_color": color_to_rgb(header_session_color()),
    }))
}

fn color_to_rgb(color: Color) -> Option<[u8; 3]> {
    match color {
        Color::Rgb(r, g, b) => Some([r, g, b]),
        Color::Indexed(n) if n >= 16 => {
            let (r, g, b) = crate::tui::color_support::indexed_to_rgb(n);
            Some([r, g, b])
        }
        _ => None,
    }
}

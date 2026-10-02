# HANDOFF — русская локализация jcode

Документ для продолжения работы в следующем сеансе. Обновлять по мере продвижения.

## Что это

Отдельный форк jcode с частичной русской локализацией TUI.
Папка: `/home/ilya/Program/jcode-ru`, ветка `dev`, remote `origin` = upstream
(`https://github.com/1jehuang/jcode.git`), remote `fork` = `git@github.com:polosinilya/jcode-ru.git`.

Публичный репозиторий: **https://github.com/polosinilya/jcode-ru** (ветка `dev` — default).
Релиз: **https://github.com/polosinilya/jcode-ru/releases/tag/v0.84.0-ru.0001**
(ассет `jcode_0.84.0-ru.0001_amd64.deb`).

Пуш изменений: `git push fork dev`.

Upstream-клон для сборки/экспериментов: `/home/ilya/Program/jcode` (та же ветка `dev`,
тот же коммит локализации, плюс собранный `target/`).

## Текущее состояние (готово)

- Rust-тулчейн: **stable 1.99.0** установлен в `~/.cargo` / `~/.rustup` (rustup, minimal).
- Базовая сборка апстрима проходит: `0.84.0-dev (0735c75)`.
- Локализовано **~2 762 строки** в **63 файлах** (`crates/jcode-tui`,
  `crates/jcode-tui-account-picker`).
- Локализованный билд собирается (exit 0, без `unreachable pattern`).
- Собран `.deb`: `dist/jcode_0.84.0-ru.0001_amd64.deb` (ставит `/usr/bin/jcode`).
- Артефакты пайплайна сохранены в `i18n/` (см. ниже).

Коммиты ветки `dev`:

| commit | описание |
|---|---|
| `f276a10` | feat(i18n): русская локализация TUI (main screens) |
| `a37db60` | docs: русский README + скрипт `.deb` |
| (следующий) | docs: handoff + артефакты i18n |

## Как собрать и упаковать

```bash
cd /home/ilya/Program/jcode-ru
export PATH="$HOME/.cargo/bin:$PATH"

# libssl-dev отсутствует — собираем со встроенным OpenSSL:
cargo build --release --bin jcode --features linux-compat-vendored-openssl -j 12
# инкрементально ~14 c, чистая сборка ~10 мин

JCODE_DEB_VERSION=0.84.0-ru.0001 scripts/make_deb_ru.sh
sudo dpkg -i dist/jcode_0.84.0-ru.0001_amd64.deb
jcode --version
```

Примечания:
- `assets/` исключён через sparse-checkout; для сборки не нужен.
- Обычная сборка без фичи требует системный `libssl-dev` (сейчас не установлен,
  sudo-пароль не запрашивался). Фича `linux-compat-vendored-openssl` собирает
  OpenSSL из исходников (нужны `perl`, `make`, `cc` — есть).
- Один из git-зависимостей апстрима: `github.com/1jehuang/agentgrep`,
  `github.com/1jehuang/mermaid-rs-renderer` — тянутся при первой сборке.

## Пайплайн локализации (в `i18n/`)

1. **Инвентарь** (`i18n/inventory/`): `inv_auth.tsv`, `inv_status.tsv`,
   `inv_input.tsv`, `inv_help.tsv`, `candidates.tsv` — user-visible строки
   (file, line, literal, source_line). Инвентарь зашумлён, поэтому не все строки UI.
2. **Батчи** (`i18n/nb/b*.tsv`): входные блоки по 120 строк с raw-литералами.
3. **Переводы** (`i18n/ntr/b*.tsv`): вывод агентов в формате `<idx>\t<ru|SKIP>`.
   Переводили агенты `general` на провайдере **kodikrouter** (`qwen/qwen3-coder`).
4. **Применение** (`i18n/tools/apply_v2.py`): детерминированно заменяет литерал на
   записанной строке; отбрасывает строки с несовпадением плейсхолдеров
   (`{}`/`{:?}`) или escape-последовательностей; пишет `apply_v2_report.json`.
5. **Защита логики**: после применения отдельным проходом откатываются литералы,
   используемые как ключи парсинга (`match`-паттерны, `==`, `.eq`, `starts_with`,
   `contains` и т.п.) — иначе ломается разбор команд (пример: `/telemetry everything`).

Команда применения:

```bash
cd /home/ilya/Program/jcode-ru
python3 i18n/tools/apply_v2.py
```

(скрипты в `i18n/tools/` используют абсолютные пути `/tmp/opencode/...` —
при переносе в репозиторий пути нужно поправить или скопировать `i18n/nb` и
`i18n/ntr` обратно в `/tmp/opencode/{nb,ntr}`).

## Что осталось (на следующий раз)

1. **Добить покрытие UI**: не переведены часть справки (`input_help.rs`), кластеры
   remote/ssh, model/inline, chat/transcript, debug/devtools (исключить).
   ~1 485 строк пропущены как служебные; часть — реально UI, стоит перепроверить.
2. **CLI-справка** `jcode --help` (clap в крейте `jcode`) — не локализована.
3. **i18n-слой** (опционально): вынести строки в `t(key)` + крейт + поле
   `display.language` в конфиге, если нужен переключатель языка вместо хардкода.
4. **Публикация — сделано.** Репозиторий и релиз `v0.84.0-ru.0001` опубликованы
   (см. выше). Следующий релиз: собрать новый `.deb`, создать тег/релиз
   (`v0.84.0-ru.0002`) и приложить ассет. Для API-операций нужен токен
   (`repo` scope) — через device-flow или `gh auth login`.
5. **Проверка в реальном TUI**: `script`-снимок кадра не даёт текст; для визуальной
   проверки запускать бинарник в настоящем терминале (или через PTY-инструмент).

## Грабли (запомнить)

- **Не переводить литералы-ключи парсинга** — только отображаемый текст.
- **`/tmp/opencode` не переживёт перезагрузку** — рабочие артефакты теперь в `i18n/`.
- `cargo build` сам по себе ничего не доказывает для runtime; daemon-пути в
  `~/.jcode/builds/...` апстрима нас не касаются (мы ставим бинарь в `/usr/bin`).
- Запуск бинарника из каталога репозитория включает self-dev режим; из `/usr/bin`
  в другом каталоге — нет.

## Ориентиры сессий

- Предыдущая (изучение jcode, opencode-ru): `ses_f516ea539...` (17.09.2026).
- Текущая (локализация/сборка): `ses_f0469a7b...` (02.10.2026).

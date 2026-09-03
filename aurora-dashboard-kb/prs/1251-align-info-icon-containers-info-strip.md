# PR #1251: fix(aurora): align the info icon in the containers info strip (#1229)

**Автор:** mark-karnaukh-extern-sap · **Статус:** open (создан 01.09.2026, не смержен)
**Ветки:** `mark-fix-align-info-icon` → `main` · **Файлов:** 2 (+7/-1)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1251

## Что сделано

Закрывает #1229: в info-строке над таблицей Swift containers (`N containers, Remaining Quota: …`) иконка-подсказка (ⓘ) визуально сидела не по центру относительно соседнего текста. Причина — в оборачивающем `TooltipTrigger`: по умолчанию (`asChild` не передан) он рендерит нативный `<button>` вокруг переданных детей, а не отдаёт стилизацию самой иконке; браузерные дефолтные паддинги/border-box кнопки раздувают итоговую высоту триггера примерно до ~25px при том, что сама иконка (`Icon size="20px"`) — 20px. Внутри строки на `flex items-center` (`data-testid="containers-info-block"`) более высокий бокс триггера центрируется иначе, чем однострочный текст, отсюда видимый сдвиг.

Правка ограничивает высоту триггера классом `max-h-5` (Tailwind, `max-height: 1.25rem` = 20px), приводя высоту бокса кнопки к высоте самой иконки. Изменение однострочное, плюс changeset (`patch`) — никакой логики, пропсов или структуры компонента не тронуто.

## Как это реализовано

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/ContainerLimitsTooltip.tsx:64-70
return (
  <Tooltip triggerEvent="hover" placement="bottom-end" open={open}>
    <TooltipTrigger className="max-h-5">
      <span>
        <Icon icon="info" size="20px" className="text-theme-light hover:text-theme-default cursor-pointer" />
      </span>
    </TooltipTrigger>
```

Проверено по исходнику `@cloudoperators/juno-ui-components`, закреплённой версии `9.4.0` (`packages/aurora/package.json:86`, тег `@cloudoperators/juno-ui-components@9.4.0` в `juno/`) — `className` у `TooltipTrigger` при `asChild=false` (используемый здесь путь) прокидывается напрямую в атрибут нативного `<button>` и ни с чем не сцеплен:

```tsx
// juno: packages/ui-components/src/components/TooltipTrigger/TooltipTrigger.component.tsx
return (
  <button
    ref={ref}
    data-state={state.open ? "open" : "closed"}
    {...state.getReferenceProps(props)}
    className={`${className} ${state.disabled && " jn:cursor-default"}`}
  >
    {children}
  </button>
)
```

Т.е. никакого встроенного клэмпа высоты в самом `TooltipTrigger` нет — высота кнопки целиком определяется UA-стилями `<button>` (паддинги/border), и именно это правка компенсирует снаружи через `className`.

Исторический контекст (`git log` по файлу, `origin/main`): использование обычного `<button>`-триггера вместо прежнего `asChild` — не случайность этого PR, а осознанное решение из #1124 (`13e2ae1d`, «fix(portal): swift container limits tooltip not showing on hover»): там `Icon` под `asChild` не форвардил ref корректно, из-за чего тултип не открывался по hover, и фикс сознательно перешёл на дефолтный `<button>`-триггер с иконкой, обёрнутой в `<span>`. Побочным эффектом того необходимого фикса и стала лишняя высота кнопки, которую #1251 сейчас убирает — правка не конфликтует с #1124, а устраняет его визуальный побочный эффект, не откатывая сам фикс наведения.

## Что затронуло

`git grep -n 'ContainerLimitsTooltip' origin/main -- '*.ts' '*.tsx'` — единственное место рендера во всём монорепо:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/index.tsx:401
<ContainerLimitsTooltip serviceInfo={serviceInfo} accountInfo={accountInfo} />
```

внутри того самого `data-testid="containers-info-block"` (`className="text-theme-light ml-auto flex items-center gap-1"`) — ровно тот контекст, который описан в PR. Остальные совпадения — `ContainerLimitsTooltip.test.tsx` и мок в `Containers/index.test.tsx`, оба не потребители, а тесты.

Изменение чисто presentational: одна Tailwind-утилита на `className` пропе `TooltipTrigger`, которая (см. выше) ничего, кроме итогового атрибута `class` кнопки, не затрагивает — путь `asChild` не используется здесь ни до, ни после PR, так что ветка с `cloneElement`/мерджем рефов в `TooltipTrigger` не в игре. Публичный контракт компонента (`ContainerLimitsTooltipProps`, дети, структура тултипа) не менялся. Единственный потребитель тестирован тем же файлом (`ContainerLimitsTooltip.test.tsx`), который PR не трогает и который не проверяет высоту/классы — риска регрессии в тестах нет, блэст-радиус ограничен визуальным центрированием одной иконки в одной строке одной вьюхи.

## Ревью

Диф проверен по пяти направлениям: комплаенс с `CLAUDE.md` (корневой, взят из `DOCS/ToolDocs/claude-config/aurora-dashboard-config/CLAUDE.md`), bug-scan самого дифа, исторический контекст (`git log`/`git blame` по файлу, см. выше — #1124), prior-PR-feedback (`git log --oneline` по файлу — только 3 коммита: #1124, #964 upgrade juno, #850 переезд пакета; ничего в духе незакрытого ревью-треда), comment-compliance (комментариев в самом файле, регламентирующих высоту/стили триггера, нет — не с чем сверяться).

Комплаенс: PR title `fix(aurora): align the info icon in the containers info strip (#1229)` — тип `fix` и scope `aurora` оба входят в списки `commitlint.config.mjs` (`types`/`scopes`), формат `<type>(<scope>): <subject>` соблюдён. Changeset (`.changeset/heavy-dingos-lead.md`, `"@cobaltcore-dev/aurora": patch`) по форме и уровню (`patch` для точечного визуального фикса) совпадает с конвенцией остальных changeset'ов репозитория.

**Проблем с уверенностью ≥80 не найдено.**

Единственная рассмотренная гипотеза, не прошедшая порог: что `max-h-5` может обрезать иконку, если реальная высота контента (иконка + паддинги кнопки) превышает 20px. При проверке — Tailwind `max-h-*` не задаёт `overflow: hidden` сам по себе (в отличие от `h-*` с последующим `overflow-hidden`), у `TooltipTrigger`/`button` здесь никакого `overflow` не выставлено нигде в дифе или в юно-компоненте, так что переполнение по умолчанию `visible` — контент не обрежется, даже если паддинги кнопки формально не влезают в 20px. К тому же единственное содержимое триггера — сама 20px-иконка в `<span>` без собственных паддингов, так что естественная высота контента и так ровно 20px. Оценка: 15/100 (гипотетически возможно в других браузерных движках с иным UA-стилем кнопки, но не подтверждается ни кодом, ни чек-листом автора «Info icon is vertically aligned… Tooltip still opens on hover and is positioned correctly»).

---
Проанализировано: 02.09.2026 · коммит `7c1b89bc` (head, PR open/unmerged)

# Операции КПО: снимок MCP

## Содержание

- [Правила чтения снимка](#правила-чтения-снимка)
- [Чтение и аудит](#чтение-и-аудит)
- [Метаданные карты](#метаданные-карты)
- [Участники и размещение](#участники-и-размещение)
- [Узлы и составные операции](#узлы-и-составные-операции)
- [Аннотации и связи](#аннотации-и-связи)
- [Значения перечислений](#значения-перечислений)
- [Что не подтверждено](#что-не-подтверждено)

## Правила чтения снимка

Сверено с 40 доступными XPM-операциями MCP Социотеха 2026-11-06.
Приведены локальные имена без префикса конкретного клиента.
Перед вызовом обнаружить фактическое имя, прочитать описание и входную схему.
Это справочник возможностей, не исполняемый контракт и не результат
проверки мутаций на живом проекте.

**Каждая операция ниже требует `boardId: string`.** В таблицах он опущен.
Остальные ID и текстовые поля — строки, если не указано иное.
`?` означает необязательное поле; `| null` — допустимый явный `null`.
`index` — число; порядок и смысл индекса сверять с текущим состоянием
и описанием клиента, не переносить предположения из другого API.

Создающие операции принимают необязательный `id?: string | null`.
По умолчанию не передавать его, а сохранять ID из ответа и последующего чтения.
Дополнительные `sourceLinkId`, `targetLinkId`, `fromSourceLinkId`,
`laneId`/`rowId` в составных операциях не трактовать по одному имени
как выбор существующей сущности: их назначение не раскрыто полностью.
Не передавать их без уточнения текущего контракта. Не пропускать обязательный
`mapId`: получать идентификатор карты из чтения, а не из `boardId`.

## Чтение и аудит

| Операция | Аргументы сверх boardId | Возвращаемый контур |
| --- | --- | --- |
| `get_xpm` | нет | Полная КПО |
| `get_xpm_lane` | `laneId` | Дорожка со строками и узлами |
| `get_xpm_node` | `nodeId` | Узел, строка, дорожка, аннотации, смежные связи |
| `get_xpm_link` | `linkId` | Связь и оба узла |
| `audit_xpm` | нет | Начальная ключевая точка, обязательные вход/выход, повреждённые ссылки |

В описаниях объявлены ресурсы:

- `sociotech://board/{boardId}/xpm`;
- `sociotech://board/{boardId}/xpm/lane/{laneId}`;
- `sociotech://board/{boardId}/xpm/node/{nodeId}`;
- `sociotech://board/{boardId}/xpm/link/{linkId}`.

Предпочитать их, если клиент предоставляет совместимый доступ; иначе
использовать инструменты чтения. Не открывать эти URI как HTTP-адреса.
Общий `audit_board` также заявляет включение XPM.

## Метаданные карты

| Операция | Аргументы сверх boardId |
| --- | --- |
| `update_xpm_map_process_name` | `processName?: string \| null` |
| `update_xpm_map_mapping_goal` | `mappingGoal?: string \| null` |
| `update_xpm_map_thinking_positions` | `thinkingPositions?: string \| null` |
| `update_xpm_map_modality` | `modality: Modality` |
| `update_xpm_map_palette` | `palette: Palette` |

`thinkingPositions` — строка, не массив ролей. Для текстовых очисток проверить
текущую семантику `null`/пустой строки; не посылать их при отсутствии поручения.

## Участники и размещение

| Операция | Аргументы сверх boardId | Эффект |
| --- | --- | --- |
| `create_xpm_agent` | `mapId, id?, name?: string \| null, icon?: Icon` | Создать участника |
| `update_xpm_agent_name` | `agentId, name` | Изменить имя |
| `update_xpm_agent_icon` | `agentId, icon: Icon` | Изменить иконку |
| `add_xpm_agent_to_lane` | `agentId, laneId` | Назначить существующего участника дорожке |
| `create_xpm_lane` | `mapId, index, id?, agentId?: string \| null` | Создать дорожку |
| `move_xpm_lane` | `laneId, index` | Изменить положение дорожки |
| `delete_xpm_lane` | `laneId` | Удалить дорожку; каскад уточнять до вызова |
| `create_xpm_row` | `mapId, laneId, index, id?, channel?: string \| null` | Создать строку |
| `update_xpm_row_channel` | `rowId, channel?: string \| null` | Изменить канал строки |
| `move_xpm_row` | `rowId, index` | Переместить строку только внутри её дорожки |
| `delete_xpm_row` | `rowId` | Удалить строку; каскад уточнять до вызова |

Иконка не является методическим типом «актор/агент», правом доступа
или ответственным проекта.

## Узлы и составные операции

Все шесть создающих операций ниже принимают `mapId`, `type: NodeType`,
`id?: string | null`, `name?: string | null`.

| Операция | Дополнительные аргументы | Эффект |
| --- | --- | --- |
| `create_xpm_node` | `rowId` | Отдельный узел в конце строки, без связей |
| `create_next_xpm_node` | `sourceNodeId, sourceLinkId?: string \| null` | Узел в конце строки источника и связь следования от него |
| `create_previous_xpm_node` | `sourceNodeId, sourceLinkId?: string \| null` | Узел перед первым узлом строки и связь к нему; перенос старта с исходного стартового узла |
| `create_between_xpm_node` | `sourceNodeId, targetNodeId, sourceLinkId?: string \| null, targetLinkId?: string \| null` | Вставка между узлами одной строки с заменой связи следования двумя |
| `create_branch_xpm_node` | `sourceNodeId, rowId?: string \| null, fromSourceLinkId?: string \| null` | Новая строка, узел и связь следования от источника |
| `split_xpm_node` | `sourceNodeId, laneId?: string \| null, rowId?: string \| null, sourceLinkId?: string \| null` | Новая дорожка, строка, узел и связь взаимодействия от источника |

`create_next_xpm_node` — добавление в конец, а не произвольная вставка после
источника. `split_xpm_node` — создание второй стороны взаимодействия,
а не перенос исходного узла или разбиение его текста. Назначение
участника новой дорожке проверить отдельно: создание записи участника
не заявлено в эффекте `split_xpm_node`.

Составные операции описывают автосвязи словами `sequence`/`interaction`.
Не передавать `sequence` в enum обычной операции связи: допустимы только
`sequenceSolid`, `sequenceDashed` и `interaction`.
После составной операции прочитать фактический тип автосвязи.

| Операция | Аргументы сверх boardId | Эффект |
| --- | --- | --- |
| `update_xpm_node_name` | `nodeId, name` | Изменить название |
| `update_xpm_node_type` | `nodeId, type: NodeType` | Изменить тип |
| `update_xpm_node_is_start` | `nodeId, isStart: boolean` | Поставить/снять старт; поставить можно только первому узлу дорожки |
| `move_xpm_node` | `nodeId, rowId, previousNodeId?: string \| null` | Вставить после указанного узла; `null` — в начало строки |
| `delete_xpm_node` | `nodeId` | Удалить узел вместе с его связями |

## Аннотации и связи

| Операция | Аргументы сверх boardId | Особенность |
| --- | --- | --- |
| `update_xpm_node_layer` | `nodeId, layer: Layer, isEnabled: boolean, values: string[]` | Передать состояние одного слоя; сохранить прежние значения при дополнении |
| `update_xpm_node_attachment` | `nodeId, attachment: Attachment, enabled: boolean, text` | Текстовое событие/этап, не загрузка файла |
| `update_xpm_node_story` | `nodeId, storyId?: string \| null` | Связать с существующей рабочей историей; `null` — очистить связь |
| `create_xpm_link` | `mapId, sourceNodeId, targetNodeId, type: LinkType, id?, label?: string \| null, withDirection?: boolean` | Между парой в одном направлении допустима одна связь любого типа; взаимодействие не дублируется и обратно |
| `update_xpm_link_type` | `linkId, type: LinkType` | Изменить тип с проверкой дублей |
| `update_xpm_link_label` | `linkId, label?: string \| null` | Изменить подпись |
| `update_xpm_link_show_direction` | `linkId, showDirection: boolean` | Показать/скрыть направление |
| `delete_xpm_link` | `linkId` | Удалить связь |

Не путать `withDirection` при создании и `showDirection` при изменении.
Помимо дублей пары, проверять транзитивную группу `interaction`: в наблюдавшемся
runtime она не могла содержать две точки одной дорожки. Описание операции
в клиенте может не перечислять это ограничение.
В ошибке дублирования сервис возвращает ID существующей связи:
сначала прочитать её и сравнить смысл, а не повторять создание.
Одна скалярная ссылка `storyId` не даёт оснований обещать несколько историй
на одном узле. Её очистка не является командой удаления истории.

Общий `Layer` enum — не матрица доступности по `NodeType`.
В реальной записи 2026-11-06 `Input` и `Condition` отклонялись для `Trigger`.
Вопрос узла и подписи исходов работали. Для ключевых/опциональных точек
подтверждены записи входа, выхода, операций, каналов, барьеров, средств
и дополнительных сведений. Наблюдения не подтверждают остальные комбинации
и не заменяют новый runtime. Подробнее — в MCP-процессе.

## Значения перечислений

| Имя | Допустимые значения |
| --- | --- |
| `NodeType` | `keyPoint`, `optionalPoint`, `uncontrolledPoint`, `trigger` |
| `LinkType` | `sequenceSolid`, `sequenceDashed`, `interaction` |
| `Modality` | `notSet`, `asIs`, `toBe`, `hybrid` |
| `Palette` | `mono`, `dance`, `pastel` |
| `Layer` | `condition`, `input`, `channels`, `operations`, `barriers`, `means`, `output`, `custom` |
| `Attachment` | `precedingEvent`, `accompanyingEvent`, `stage` |
| `Icon` | `cook`, `caller`, `waitress`, `croupier`, `carrier`, `mechanoid`, `scientist`, `courier`, `employee`, `cashier`, `beardie`, `manager`, `dispatcher`, `smoker`, `banker`, `boss`, `eater`, `punklady`, `rocklady`, `model`, `hostess`, `cadet` |

## Что не подтверждено

В этом снимке не обнаружены отдельные операции создания/удаления самой
XPM-карты, удаления участника, снятия участника с дорожки, переноса строки
на другую дорожку, отдельного узла типа `event`, импорта/экспорта XPM,
запуска специальной ИИ-генерации XPM или пакетного применения XPM-мутаций.
Не выводить эти возможности из похожих операций других карт.

`export_project` перечисляет только `LinkedSwot`, `HypothesisMap`, `Sim`,
хотя аргумент `mapType` имеет строковый тип. Это не разрешает подставить `Xpm`.
Общие операции описаний/ответственных не перечисляют XPM-типы.
У XPM-мутаций в снимке нет аргументов версии: ревизия помогает заметить
изменение, но не создаёт атомарную защиту от конкурентной записи.

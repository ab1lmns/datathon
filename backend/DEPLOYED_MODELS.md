# Модели действующего GPU-сервиса

Состояние на 17.10.2026. Базовые веса находятся в `/workspace/.hf_home/hub`, рабочий процесс запускается с `HF_HUB_OFFLINE=1`. Исходный Qwen3-VL-8B сохранён только для отката и сейчас не загружен в GPU.

| Компонент | Модель | Локальный snapshot |
|---|---|---|
| Детектор людей и COCO предметов | [PekingU/rtdetr_v2_r50vd](https://huggingface.co/PekingU/rtdetr_v2_r50vd) | `282494075698cab9faa1096ae26856890030c817` |
| Поиск предметов по текстовым категориям | [google/owlv2-base-patch16-ensemble](https://huggingface.co/google/owlv2-base-patch16-ensemble) | `cfd3195ba4ea9592eec887ded089f4c08eff231d` |
| Визуальные признаки для классификаторов | [facebook/dinov2-base](https://huggingface.co/facebook/dinov2-base) | `f9e44c814b77203eaa57a6bdbbd535f21ede1415` |
| Точечные вопросы по двери и экрану | [Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | `ebb281ec70b05090aa6165b016eac8ec08e71b17` |

Локальные обученные веса: `models/safe_clf.joblib` (SHA-256 `808e32e0b78640a4549ebc3fda5fe0bc1851219024fe70b832d2c0d75f6b8635`) и `models/money_clf.joblib` (SHA-256 `45a41fc732ac89b8e8fed2f3cac30be28131f81c89a90fc26b655ac877efe143`). Веса скопированы без изменений из проверенного репозитория. Это классификаторы знакомых сцен; независимая переносимость на новую кассу не установлена.

Исходный проект распространяется по MIT LICENSE в этом каталоге. Лицензии базовых весов следует проверять по указанным карточкам перед внешним распространением сборки.

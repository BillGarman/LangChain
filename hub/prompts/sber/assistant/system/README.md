# Промпты для внутреннего использования

🚨В этом разделе находятся промпты, предназначенные для внутреннего использования внутри экосистемы Сбера. Пожалуйста не выкладывайте их в открытый доступ!

Набор системных промптов для ассистентов

## Inputs

Нет

## Content

- `instruct.yaml` - основной промпт голосового ассистента (персонаж по-умолчанию - Сбер)
- `aifna.yaml` - дополнительная инициализация для персонажа Афина.
- `joy.yaml` - дополнительная инициализация для персонажа Джой.
- `search.yaml` - промпт для поиска лучшего результата в поисковой выдаче
- `tenders.yaml` - промпт для поиска в тендерах

## Usage

Пример использования.
Важно! Для корректой работы загрузчика промптов у вас должен быть сетевой доступ к https://stash.sigma.sbrf.ru/ .

```python
from langchain.prompts import load_prompt

joy = load_prompt('lc://prompts/sber/assistant/system/joy.yaml')
afina = load_prompt('lc://prompts/sber/assistant/system/afina.yaml')
...
```

Вы также можете скачать файл с конфигурацией промпта и загружать его вручную.

```python
from langchain.prompts import load_prompt

joy = load_prompt('./my_local_prompts/joy.yaml')

...

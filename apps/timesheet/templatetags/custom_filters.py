from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, False)
    return False


@register.filter
def remove_h(value):
    """
    Удаляет букву 'ч' из значения и возвращает число.
    Если значение не цифра (например 'А'), возвращает 0.
    """
    if not value:
        return 0
    cleaned = str(value).replace('ч', '').strip()
    if cleaned.isdigit():
        return int(cleaned)
    return 0


@register.filter
def format_fio_short(full_name):
    """Форматирует ФИО в формат И.И. Иванов"""
    if not full_name:
        return " "
    parts = full_name.split()

    if len(parts) == 3:
        last_name = parts[0]
        first_initial = parts[1][0] + '.' if parts[1] else ''
        second_initial = parts[2][0] + '.'
        return f"{first_initial}{second_initial}{last_name}"
    elif len(parts) == 2:
        last_name = parts[0]
        first_initial = parts[1][0] + '.' if parts[1] else ''
        return f"{first_initial}{last_name}"
    return full_name


@register.filter
def to_int(value):
    """Приводит значение к int, иначе 0"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _get_attr_or_key(item, attr, default=0):
    """Вспомогательная функция: достаёт значение из словаря или объекта"""
    if isinstance(item, dict):
        return item.get(attr, default)
    return getattr(item, attr, default)


@register.filter
def sum_attr_any(iterable, attr):
    """
    Суммирует значения атрибута/ключа для словарей и объектов.
    Работает с int/float, строками вида '8ч', игнорирует буквы.
    """
    total = 0
    for item in iterable:
        value = _get_attr_or_key(item, attr, 0)
        if isinstance(value, (int, float)):
            total += value
        else:
            cleaned = str(value).replace('ч', '').strip()
            try:
                total += float(cleaned)
            except (ValueError, TypeError):
                continue
    return int(total) if total.is_integer() else total


@register.filter
def sum_attr_int(iterable, attr):
    """
    Суммирует целочисленные значения атрибута/ключа.
    Игнорирует буквы и некорректные значения.
    """
    total = 0
    for item in iterable:
        value = _get_attr_or_key(item, attr, 0)
        if isinstance(value, int):
            total += value
        else:
            cleaned = str(value).replace('ч', '').strip()
            if cleaned.isdigit():
                total += int(cleaned)
    return total

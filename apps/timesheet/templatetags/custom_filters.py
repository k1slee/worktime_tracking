from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    return dictionary.get(key, False)

@register.filter
def sum_attr(queryset, attr):
    """Сумма значений атрибута в QuerySet"""
    total = 0
    for item in queryset:
        value = getattr(item, attr, 0)
        if value:
            total += value
    return total

@register.filter
def remove_h(value):
    """Удаляет букву 'ч' из значения"""
    if value:
        return str(value).replace('ч', '').strip()
    return value

@register.filter
def format_fio_short(full_name):
    """Форматирует ФИО в формат И.И. Иванов"""
    if not full_name:
        return " "
    parts = full_name.split()

    if len(parts) == 3:
        last_name = parts[0]
        first_initial = parts[1][0] + '.' if parts[1] else ''#Первая буква имени
        second_initial = parts[2][0] + '.' #Первая буква отчества
        return f"{first_initial}{second_initial}{last_name}"
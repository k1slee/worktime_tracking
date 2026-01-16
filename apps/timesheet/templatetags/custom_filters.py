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
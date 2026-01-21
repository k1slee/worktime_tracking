import pandas as pd
from datetime import datetime
from apps.timesheet.models import Holiday

# Загружаем Excel
df = pd.read_excel("holidays.xlsx", header=None)

for row in df.iloc[1:].itertuples(index=False):
    for cell in row:  # каждая ячейка = дата
        if pd.notna(cell):  # пропускаем пустые
            try:
                day = pd.to_datetime(cell).date()
                Holiday.objects.get_or_create(
                    date=day,
                    defaults={"type": "holiday", "name": "Выходной"}
                )
            except Exception as e:
                print(f"Ошибка для {cell}: {e}")

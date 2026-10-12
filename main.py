
import pandas as pd

ventas = [
    {"producto": "teclado", "unidades": 5, "precio": 12000},
    {"producto": "mouse", "unidades": 8, "precio": 7500},
    {"producto": "monitor", "unidades": 2, "precio": 180000},
]

df = pd.DataFrame(ventas)
df["total"] = df["unidades"] * df["precio"]

archivo = "reporte_ventas.xlsx"
df.to_excel(archivo, index=False)

print(df)
print(f"\nreporte generado: {archivo}")
print(f"ventas totales: ${df['total'].sum():,.2f}")

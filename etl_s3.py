import pandas as pd
import boto3
from datetime import datetime

ARCHIVO ="operaciones.csv"


df = pd.read_csv(ARCHIVO, na_values=["NULL"])
print(f"Filas Leidas: {len(df)}")

print(f"Columnas: {df.columns.tolist()}")

UMBRAL = 0.8

columnas_texto=df.select_dtypes(include=["object", "string"]).columns
for col in columnas_texto:
    df[col] = df[col].str.strip().str.upper()
    valores = df[col].dropna()
    if valores.empty:
        df[col] = df[col].fillna("SIN DATO")
        continue
    como_numero = pd.to_numeric(valores, errors="coerce")
    if como_numero.notna().mean() >= UMBRAL:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
        print(f"{col}: convertida a número")
        continue
    como_fecha = pd.to_datetime(valores, errors="coerce", format="mixed")
    if como_fecha.notna().mean() >= UMBRAL:
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        print(f"{col}: convertida a fecha")
    df[col] = df[col].fillna("SIN DATO")
df = df.drop_duplicates()

print(f"Se realizo limpieza de datos.")

OBLIGATORIAS = ["id_operacion", "contenedor_num", "fecha_arribo", "estado_actual", "peso_kg", "costo_usd"]
RANGOS = {
    "peso_kg": (0.01, 30500),    # mayor que 0 y hasta el peso "máximo" de un contenedor
    "costo_usd": (0.1, None),      # None = sin límite superior
}
VALORES_PERMITIDOS = {
    "estado_actual": ["EN TRANSITO", "ADUANA", "RETRASADO", "ENTREGADO"],
}

# 3.2 Motor de validación (general: sirve para cualquier archivo)
motivos = pd.Series("", index=df.index)

for col in OBLIGATORIAS:
    vacio = df[col].isna() | (df[col] == "SIN DATO")
    motivos[vacio] += f"{col} vacío; "

for col, (minimo, maximo) in RANGOS.items():
    fuera = df[col] < minimo
    if maximo is not None:
        fuera = fuera | (df[col] > maximo)
    motivos[fuera] += f"{col} fuera de rango; "

for col, permitidos in VALORES_PERMITIDOS.items():
    no_permitido = ~df[col].isin(permitidos)
    motivos[no_permitido] += f"{col} no permitido; "

validos = df[motivos == ""]
rechazados = df[motivos != ""].copy()
rechazados["motivo_rechazo"] = motivos[motivos != ""]


print(f"Válidas: {len(validos)} | Rechazadas: {len(rechazados)}")
print(rechazados[["id_operacion", "peso_kg", "estado_actual", "motivo_rechazo"]])



validos.to_parquet("operaciones.parquet", index=False)
rechazados.to_parquet("rechazos.parquet", index=False)
print("Archivos Parquet generados")


BUCKET = "prueba-roldan"
AHORA = datetime.now()
HOY = AHORA.strftime("%Y-%m-%d")                                        
PARTICION = f"anio={AHORA:%Y}/mes={AHORA:%m}/dia={AHORA:%d}"

validos = validos.copy()
validos["fecha_carga"] = HOY
rechazados["fecha_carga"] = HOY

s3 = boto3.client("s3")
s3.upload_file(ARCHIVO, BUCKET, f"logistica/raw/operaciones/{PARTICION}/operaciones.csv")
s3.upload_file("operaciones.parquet", BUCKET, f"logistica/curated/operaciones/{PARTICION}/operaciones.parquet")
s3.upload_file("rechazos.parquet", BUCKET, f"logistica/quarantine/operaciones/{PARTICION}/rechazos.parquet")
print(f"Carga del {HOY} subida a S3 en {PARTICION}")
import duckdb
import os

# Opret forbindelse til DuckDB i hukommelsen
con = duckdb.connect(database=':memory:')

# Eksempel på rådata - en virksomheds salgsdatasæt
sample_data = [
    {'produktId': 'A001', 'salgsdato': '2023-01-15', 'salgskanal': 'online', 'value': 1250.50},
    {'produktId': 'A001', 'salgsdato': '2023-01-15', 'salgskanal': 'butik', 'value': 875.25},
    {'produktId': 'B002', 'salgsdato': '2023-01-15', 'salgskanal': 'online', 'value': 950.75},
    {'produktId': 'B002', 'salgsdato': '2023-01-15', 'salgskanal': 'butik', 'value': 1100.00},
    {'produktId': 'A001', 'salgsdato': '2023-02-20', 'salgskanal': 'online', 'value': 1500.75},
    {'produktId': 'A001', 'salgsdato': '2023-02-20', 'salgskanal': 'butik', 'value': 1025.50},
    {'produktId': 'B002', 'salgsdato': '2023-02-20', 'salgskanal': 'online', 'value': 1175.25},
    {'produktId': 'B002', 'salgsdato': '2023-02-20', 'salgskanal': 'butik', 'value': 1350.75},
]

# Opret midlertidig tabel med rådata
con.execute("CREATE TEMPORARY TABLE raw_data AS SELECT * FROM sample_data")

# Find unikke salgskanaler
print("Unikke salgskanaler:")
channels = con.execute("SELECT DISTINCT salgskanal FROM raw_data").fetchall()
for channel in channels:
    print(f"  {channel[0]}")

# Dynamisk pivot-forespørgsel
salgskanal_ids = [channel[0] for channel in channels]
pivot_columns = ", ".join([
    f"MAX(CASE WHEN salgskanal = '{channel}' THEN value END) as \"{channel}_salg\""
    for channel in salgskanal_ids
])

# Udfør pivot
pivot_query = f"""
CREATE TABLE pivoteret_salgsdata AS
SELECT 
    produktId,
    salgsdato,
    EXTRACT(YEAR FROM salgsdato) as år,
    EXTRACT(MONTH FROM salgsdato) as måned,
    {pivot_columns},
    SUM(value) as total_salg
FROM raw_data
GROUP BY produktId, salgsdato
"""
con.execute(pivot_query)

# Opret output-mappe
output_dir = "pivoteret_salgsdata"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Gem pivoterede data som Parquet-filer
print("\nGemmer partitionerede Parquet-filer...")
con.execute(f"""
COPY pivoteret_salgsdata 
TO '{output_dir}' 
(FORMAT PARQUET, PARTITION_BY (år, måned), COMPRESSION 'ZSTD')
""")
print(f"Data gemt i {output_dir} mappe")

# Test indlæsning af partitionerede data
print("\nTester indlæsning af partitionerede data...")
alle_data = con.execute(f"SELECT * FROM parquet_scan('{output_dir}')").df()
print(f"Indlæst {len(alle_data)} rækker fra alle partitioner")

# Vis første få rækker af pivoterede data
print("\nPivoterede salgsdata:")
con.execute("SELECT * FROM pivoteret_salgsdata").show()

# Eksempel på partition-specifik forespørgsel
year_month = con.execute("SELECT DISTINCT år, måned FROM pivoteret_salgsdata ORDER BY år, måned LIMIT 1").fetchone()
år, måned = year_month
print(f"\nIndlæser specifik partition for {år}-{måned:02d}...")
partition_data = con.execute(f"""
SELECT * FROM parquet_scan('{output_dir}') 
WHERE år = {år} AND måned = {måned}
""").df()
print(f"Indlæst {len(partition_data)} rækker fra partition {år}-{måned:02d}")

#!/usr/bin/env python3

from datasets import load_dataset
import pandas as pd
import os

# Load the dataset with the specific configuration
# List of all available configurations
configs = [
    "codiesp_D_source",
    "codiesp_P_source",
    "codiesp_X_source",
    "codiesp_extra_cie_source",
    "codiesp_extra_mesh_source",
]

os.makedirs("codiesp_csvs", exist_ok=True)

# Load each configuration
for config in configs:
    dataset = load_dataset("bigbio/codiesp", name=config, trust_remote_code=True)
    print(f"Loaded configuration: {config}")
    for split in dataset.keys():
        # Definir el nombre del archivo CSV
        csv_filename = f"codiesp_csvs/{config}_{split}.csv"

        # Verificar si el archivo ya existe
        if os.path.exists(csv_filename):
            response = input(
                f"The file {csv_filename} already exists. Do you want to fetch the data again? (Y/N): "
            )
            if response.upper() != "Y":
                print("Operation cancelled. continuing...")
                continue

        # Si no existe, crear el archivo CSV
        print(f"Creando {csv_filename}...")
        df = pd.DataFrame(dataset[split])
        # Remove 'id' and 'document_id' columns if they exist
        columns_to_drop = ["id", "document_id"]
        # Convert labels from list to semicolon-separated string if the column exists
        if 'labels' in df.columns:
            df['labels'] = df['labels'].apply(lambda x: ';'.join(x) if isinstance(x, list) else x)
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
        df.to_csv(csv_filename, index=False)
        print(f"¡Creado correctamente {csv_filename}!")

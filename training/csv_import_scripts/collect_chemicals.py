#!/usr/bin/env python3

import grequests
import csv
import os

codes = {}
fieldnames = [
    "area",
    "code1",
    "code2",
    "code3",
    "code4",
    "code5",
    "code6",
    "codes",
    "description",
    "fatherId",
    "finalNode",
    "id",
    "indx",
    "level",
    "notes",
    "orderList",
    "path",
    "tab",
]


FIRST_LETTER = [
    "0",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
]
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.eciemaps.sanidad.gob.es/",
    "Cache-Control": "max-age=0",
}


def generate_cie_10_code_requests():
    url_prefix = "https://www.eciemaps.sanidad.gob.es/cie10mc/2024/ia/drugsByLetter/"
    urls = []
    for code in FIRST_LETTER:
        urls.append(f"{url_prefix}{code}")
    return [grequests.get(url, headers=headers) for url in urls]


def iterate_through_codes():
    print("Generando solicitudes...")
    future_requests = generate_cie_10_code_requests()
    print(f"Se generaron {len(future_requests)} solicitudes iniciales.")
    print("Iniciando procesamiento de códigos...")
    get_list_of_codes_from_response(future_requests)


def get_list_of_codes_from_response(future_requests):
    # Lista para almacenar todas las respuestas
    responses = list(grequests.imap_enumerated(future_requests, size=10))
    for idx, (index, response) in enumerate(responses):
        print(f"Procesando respuesta {idx + 1}/{len(responses)}: {response.url}")

        child_items = []
        for code_entry in response.json():
            description = code_entry.get("description")
            finalNode = code_entry.get("finalNode")

            information = {}
            for key in fieldnames:
                information[key] = code_entry.get(key)

            codes[description] = information

            if not finalNode:
                child_items.append(information)
                # If not a final node, we need to find its children
        get_childrens(child_items)


def get_childrens(parent_entries):
    future_requests = []
    for parent_entry in parent_entries:
        path = parent_entry.get("path").split(",")[-2]
        future_requests.append(
            grequests.get(
                f"https://www.eciemaps.sanidad.gob.es/cie10mc/2024/lt/sec/{path}",
                headers=headers,
            )
        )

    responses = list(grequests.imap_enumerated(future_requests, size=10))
    for idx, (index, response) in enumerate(responses):
        print(f"    - Procesando hijo {idx + 1}/{len(responses)}: {response.url}")
        parent_entry = parent_entries[idx]
        for code_entry in response.json():
            description = code_entry.get("description")
            finalNode = code_entry.get("finalNode")

            information = {}
            for key in fieldnames:
                information[key] = code_entry.get(key)

            information["description"] = (
                parent_entry["description"] + " | " + information["description"]
            )

            codes[description] = information

            if not finalNode:
                get_childrens(information)


# Check if output file already exists
os.makedirs("cie10-csvs", exist_ok=True)
output_file = "cie10-csvs/cie10-es-chemicals.csv"
if os.path.exists(output_file):
    response = input(
        f"The file {output_file} already exists. Do you want to fetch the data again? (Y/N): "
    )
    if response.upper() != "Y":
        print("Operation cancelled. Exiting...")
        exit()

print("Iniciando la recolección de datos... Esto puede tardar varios minutos.")
iterate_through_codes()

print(f"\nGuardando {len(codes)} códigos en {output_file}...")

with open(output_file, "w", newline="") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(codes[key] for key in sorted(codes))

print(f"¡Proceso completado! Se guardaron {len(codes)} códigos en {output_file}")

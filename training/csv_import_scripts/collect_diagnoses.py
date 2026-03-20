#!/usr/bin/env python3

import grequests
from string import ascii_uppercase
import csv
from progressbar import progressbar
import os

codes = {}
fieldnames = [
    "code",
    "description",
    "perinatal",
    "pediatric",
    "maternity",
    "adult",
    "femalesOnly",
    "malesOnly",
    "poaExempt",
    "noPrincipal",
    "vcdp",
]

min = 0
max = 10  # should be 10

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.eciemaps.sanidad.gob.es/",
    "Cache-Control": "max-age=0",
}


def generate_cie_10_code_requests(code):
    url_prefix = "https://www.eciemaps.sanidad.gob.es/cie10mc/2024/lt/sec/"
    return [
        grequests.get(f"{url_prefix}{code}{number}", headers=headers, timeout=30.0)
        for number in range(min, max)
    ]


def iterate_through_codes():
    for first_char in progressbar(ascii_uppercase, redirect_stdout=True):
        print(f"CODE: {first_char}")
        future_requests = generate_cie_10_code_requests(first_char)
        get_list_of_codes_from_response(future_requests)


def get_list_of_codes_from_response(future_requests):
    pending = future_requests
    while pending:
        retry = []
        for index, response in grequests.imap_enumerated(pending, size=10):
            print(response.url)
            try:
                data = response.json()
            except Exception:
                print(f"  [retry] respuesta vacía: {response.url}")
                retry.append(grequests.get(response.url, headers=headers, timeout=30.0))
                continue
            for code_entry in data:
                id = code_entry.get("code")
                # excluding excludes1 type
                if (
                    code_entry.get("type") == "desc"
                    or code_entry.get("type") == "inclusionTerm"
                ):
                    if codes.get(id) is None:
                        information = {}
                        for key in fieldnames:
                            information[key] = code_entry.get(key)
                        codes[id] = information
                    else:
                        updated_code = codes[id]
                        updated_code["description"] = (
                            updated_code.get("description")
                            + " | "
                            + code_entry.get("description")
                        )
                        print(updated_code["description"])
                        codes[id] = updated_code
        pending = retry


def transform_fields(code):
    female_only = code.pop("femalesOnly") != None
    male_only = code.pop("malesOnly") != None

    if female_only:
        code["exclusiveGender"] = "F"
    elif male_only:
        code["exclusiveGender"] = "M"
    else:
        code["exclusiveGender"] = ""

    code["perinatal"] = 1 if code["perinatal"] is not None else 0
    code["pediatric"] = 1 if code["pediatric"] is not None else 0
    code["maternity"] = 1 if code["maternity"] is not None else 0
    code["adult"] = 1 if code["adult"] is not None else 0
    code["poaExempt"] = 1 if code["poaExempt"] is not None else 0
    code["noPrincipal"] = 1 if code["noPrincipal"] is not None else 0
    code["vcdp"] = 1 if code.pop("vcdp") is not None else 0


# Check if output file already exists
os.makedirs("cie10-csvs", exist_ok=True)
output_file = "cie10-csvs/cie10-es-diagnoses.csv"
if os.path.exists(output_file):
    response = input(
        f"The file {output_file} already exists. Do you want to fetch the data again? (Y/N): "
    )
    if response.upper() != "Y":
        print("Operation cancelled. Exiting...")
        exit()

iterate_through_codes()
for code in codes.values():
    transform_fields(code)

with open(output_file, "w", newline="") as csvfile:
    csv_field_names = list(codes.values())[0].keys()
    writer = csv.DictWriter(csvfile, fieldnames=csv_field_names)
    writer.writeheader()
    writer.writerows(codes[key] for key in sorted(codes))

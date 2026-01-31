#!/usr/bin/env python3

import grequests
import requests
import csv
from progressbar import progressbar, ProgressBar
import os

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.eciemaps.sanidad.gob.es/",
    "Cache-Control": "max-age=0",
}
fieldnames = ["code", "description", "femalesOnly", "malesOnly", "timesSelected"]


def get_t1_entries():
    types = {}
    results = requests.get(
        "https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t1", headers=headers
    ).json()
    print("T1 entries")
    for element in results:
        types[element.get("t3")] = {"name": element.get("d1")}
    return types


def get_t2_entries(types):
    subtypes = {}
    print("T2 entries")
    for type in progressbar(types):
        obj_type = types[type]
        results = requests.get(
            f"https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t2/{type}",
            headers=headers,
        ).json()
        for element in results:
            subtypes[element.get("t3")] = {
                "class_name": obj_type.get("name"),
                "subclass_name": element.get("d1"),
            }
    return subtypes


def get_t3_entries(types):
    subtypes = {}
    print("T3 entries")
    for type in progressbar(types):
        obj_type = types[type]
        results = requests.get(
            f"https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t3/{type}",
            headers=headers,
        ).json()
        for element in results:
            subtypes[element.get("t3")] = {
                "class_name": obj_type.get("class_name"),
                "subclass_name": obj_type.get("subclass_name"),
                "procedure": element.get("d1"),
            }
    return subtypes


def get_procedure_subclasses(types):
    codes = {}
    print("Calculating all combinations!")

    requests = [
        grequests.get(
            f"https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/lt/table/{key}",
            headers=headers,
        )
        for key in types
    ]

    for request in progressbar(
        grequests.imap(requests, size=10), redirect_stdout=True, max_value=len(types)
    ):
        results = request.json()["pcsTable"][0]
        type = results["index"]
        obj_type = types.get(type)
        definition = results["axis"][-1].get("definition")

        for row in results["pcsRow"]:
            localizations = []
            approaches = []
            devices = []
            califications = []

            # TODO: Could be reshaped/refactorised
            for localization in row["axis"][0]["label"]:
                localizations.append(
                    {
                        "localization": localization["value"],
                        "code": localization["code"],
                    }
                )

            for approach in row["axis"][1]["label"]:
                approaches.append(
                    {"approach": approach["value"], "code": approach["code"]}
                )

            for device in row["axis"][2]["label"]:
                devices.append({"device": device["value"], "code": device["code"]})

            for calification in row["axis"][3]["label"]:
                califications.append(
                    {
                        "calification": calification["value"],
                        "code": calification["code"],
                    }
                )

            for localization in localizations:
                for approach in approaches:
                    for device in devices:
                        for calification in califications:
                            key = f"{type}{localization['code']}{approach['code']}{device['code']}{calification['code']}"
                            codes[key] = {
                                "code": key,
                                "class_name": obj_type.get("class_name"),
                                "subclass_name": obj_type.get("subclass_name"),
                                "procedure": obj_type.get("procedure"),
                                "procedure_definition": definition,
                                "localization": localization.get("localization"),
                                "approach": approach.get("approach"),
                                "device": device.get("device"),
                                "calification": calification.get("calification"),
                                "definition": definition,
                            }

    return codes


# Check if output file already exists
os.makedirs("cie10-csvs", exist_ok=True)
output_file = "cie10-csvs/cie10-es-procedures.csv"
if os.path.exists(output_file):
    response = input(
        f"The file {output_file} already exists. Do you want to fetch the data again? (Y/N): "
    )
    if response.upper() != "Y":
        print("Operation cancelled. Exiting...")
        exit()

entries = get_t1_entries()
entries = get_t2_entries(entries)
entries = get_t3_entries(entries)
codes = get_procedure_subclasses(entries)

url_prefix = "https://www.eciemaps.sanidad.gob.es/ref/cie10pcs"
pb = ProgressBar(max_value=len(codes))
# INFO: Prevents ToManyFilesOpen OSError - grequest map doesn't close already processed requests, and there's 75k+
# I'm processing it in 50 slices, as it will force the old object via dereferencing to be GC and sockets will be clossed.
number_of_chunks = 100
print("Getting details of each procedure :::: ~30 min")
for index in range(number_of_chunks):
    cie10_code_requests = [
        grequests.get(f"{url_prefix}/{key}", headers=headers, timeout=30.0)
        for key in list(codes.keys())[index::number_of_chunks]
    ]
    for request in grequests.imap(cie10_code_requests, size=25):
        results = request.json()

        code = codes.get(results["code"])
        code["description"] = results["description"]
        code["timesSelected"] = results["timesSelected"]

        if results["femalesOnly"] != None:
            code["gender"] = "F"
        elif results["malesOnly"] != None:
            code["gender"] = "M"
        else:
            code["gender"] = ""

        codes[results["code"]] = code
        pb.increment()

pb.finish()

fieldnames = [
    "code",
    "class_name",
    "subclass_name",
    "procedure",
    "procedure_definition",
    "localization",
    "approach",
    "device",
    "calification",
    "definition",
    "description",
    "timesSelected",
    "gender",
]
with open(output_file, "w", newline="") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(codes[key] for key in sorted(codes))

defmodule Mix.Tasks.Cie10.Import do
  @moduledoc """
  Imports CIE-10 reference codes (diagnoses, procedures, chemicals) from CSV files into the database.

  Usage:
      mix cie10.import [/path/to/cie10-csvs]

  The path defaults to the CIE10_CSV_DIR environment variable, then to /data/cie10-csvs.
  """

  use Mix.Task
  require Logger

  NimbleCSV.define(CsvParser, separator: ",", escape: "\"")

  @shortdoc "Import CIE-10 reference codes from CSV files"
  @batch_size 500

  @impl Mix.Task
  def run(args) do
    Mix.Task.run("app.start")

    base_dir =
      case args do
        [dir | _] -> dir
        [] -> System.get_env("CIE10_CSV_DIR", "/data/cie10-csvs")
      end

    Logger.info("Importing CIE-10 codes from #{base_dir}")

    n_diagnoses = import_diagnoses(Path.join(base_dir, "cie10-es-diagnoses.csv"))
    n_procedures = import_procedures(Path.join(base_dir, "cie10-es-procedures.csv"))
    n_chemicals = import_chemicals(Path.join(base_dir, "cie10-es-chemicals.csv"))

    Logger.info(
      "Import complete — diagnoses: #{n_diagnoses}, procedures: #{n_procedures}, chemicals: #{n_chemicals}"
    )
  end

  # ── Diagnoses ──────────────────────────────────────────────────────────────

  defp import_diagnoses(path) do
    Logger.info("Importing diagnoses from #{path}")

    rows =
      path
      |> File.stream!(read_ahead: 100_000)
      |> CsvParser.parse_stream(skip_headers: true)
      |> Stream.map(fn
        [code, description | flags] ->
          [perinatal, pediatric, maternity, adult, poa_exempt, no_principal, excl_gender | _] =
            pad(flags, 7)

          %{
            code: String.upcase(String.trim(code)),
            description: clean(description),
            type: "diagnosis",
            metadata: %{
              perinatal: flag(perinatal),
              pediatric: flag(pediatric),
              maternity: flag(maternity),
              adult: flag(adult),
              poa_exempt: flag(poa_exempt),
              no_principal: flag(no_principal),
              exclusive_gender: String.trim(excl_gender)
            },
            inserted_at: now(),
            updated_at: now()
          }
      end)
      |> Stream.filter(fn r -> r.code != "" and r.description != "" end)

    bulk_insert(rows)
  end

  # ── Procedures ─────────────────────────────────────────────────────────────

  defp import_procedures(path) do
    Logger.info("Importing procedures from #{path}")

    rows =
      path
      |> File.stream!(read_ahead: 100_000)
      |> CsvParser.parse_stream(skip_headers: true)
      |> Stream.map(fn row ->
        [
          code,
          class_name,
          subclass_name,
          procedure,
          procedure_def,
          localization,
          approach,
          device,
          calification,
          definition,
          description | rest
        ] = pad(row, 13)

        times = List.first(rest, "") |> String.trim()
        gender = Enum.at(rest, 1, "") |> String.trim()

        %{
          code: String.upcase(String.trim(code)),
          description: clean(description),
          type: "procedure",
          metadata: %{
            class_name: clean(class_name),
            subclass_name: clean(subclass_name),
            procedure: clean(procedure),
            procedure_definition: clean(procedure_def),
            localization: clean(localization),
            approach: clean(approach),
            device: clean(device),
            calification: clean(calification),
            definition: clean(definition),
            times_selected: parse_int(times),
            gender: gender
          },
          inserted_at: now(),
          updated_at: now()
        }
      end)
      |> Stream.filter(fn r -> r.code != "" and r.description != "" end)

    bulk_insert(rows)
  end

  # ── Chemicals ──────────────────────────────────────────────────────────────

  defp import_chemicals(path) do
    Logger.info("Importing chemicals from #{path}")

    rows =
      path
      |> File.stream!(read_ahead: 100_000)
      |> CsvParser.parse_stream(skip_headers: true)
      |> Stream.flat_map(fn row ->
        [_area, c1, c2, c3, c4, c5, c6, _codes, description | rest] = pad(row, 18)

        level = Enum.at(rest, 5, "") |> String.trim()
        notes = Enum.at(rest, 6, "") |> String.trim()

        codes =
          [c1, c2, c3, c4, c5, c6]
          |> Enum.map(&String.trim/1)
          |> Enum.reject(&(&1 == "" or &1 == "-" or &1 == "--"))

        all_codes = Enum.map(codes, &String.upcase/1)

        Enum.map(all_codes, fn code ->
          %{
            code: code,
            description: clean(description),
            type: "chemical",
            metadata: %{
              all_codes: all_codes,
              level: parse_int(level),
              notes: notes
            },
            inserted_at: now(),
            updated_at: now()
          }
        end)
      end)
      |> Stream.filter(fn r -> r.code != "" and r.description != "" end)

    bulk_insert(rows)
  end

  # ── Helpers ────────────────────────────────────────────────────────────────

  defp bulk_insert(stream) do
    total =
      stream
      |> Stream.chunk_every(@batch_size)
      |> Enum.reduce(0, fn batch, acc ->
        unique_batch = batch |> Enum.uniq_by(& &1.code)

        {inserted, _} =
          App.Repo.insert_all(App.Cie10Code, unique_batch,
            on_conflict: {:replace, [:description, :metadata, :updated_at]},
            conflict_target: :code
          )

        new_total = acc + inserted
        IO.write("\r  → #{new_total} registros insertados...")
        new_total
      end)

    IO.write("\r  → #{total} registros insertados. Listo.\n")
    total
  end

  defp clean(s), do: s |> String.trim() |> String.replace(~r/\s+/, " ")

  defp flag("1"), do: true
  defp flag("true"), do: true
  defp flag(_), do: false

  defp parse_int(s) do
    case Integer.parse(s) do
      {n, _} -> n
      _ -> nil
    end
  end

  defp pad(list, min_length) when length(list) >= min_length, do: list
  defp pad(list, min_length), do: list ++ List.duplicate("", min_length - length(list))

  defp now, do: DateTime.truncate(DateTime.utc_now(), :second)
end

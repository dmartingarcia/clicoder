defmodule Mix.Tasks.Cie10.ImportTest do
  @moduledoc """
  Prueba de humo de la importación del catálogo CIE-10.

  La tarea se ejecuta una sola vez al provisionar el sistema, así que no tiene sentido probar
  cada rama; lo que importa es que, dado un CSV con la forma real, acabe dejando los códigos
  en la base de datos con sus campos bien puestos. Si eso se rompe, el sistema arranca con el
  catálogo vacío y el fallo aparece mucho después, al buscar un código y no encontrarlo.
  """
  use App.DataCase

  alias App.Cie10Code
  alias App.Repo
  alias Mix.Tasks.Cie10.Import

  @diagnosticos """
  code,description,perinatal,pediatric,maternity,adult,poa_exempt,no_principal,exclusive_gender
  A15.0,Tuberculosis pulmonar,0,0,0,1,0,0,
  E11.9,Diabetes mellitus tipo 2 sin complicaciones,0,1,0,1,0,0,
  O80,Parto único espontáneo,0,0,1,1,0,0,F
  """

  # Las tres fuentes tienen formatos distintos: procedimientos trae trece columnas con la
  # descripción al final, y químicos reparte un mismo producto en varios códigos por columna.
  @procedimientos """
  code,class_name,subclass_name,procedure,procedure_definition,localization,approach,device,calification,definition,description,timesSelected,gender
  0016070,Médico-Quirúrgica,Sistema Nervioso Central,Derivación,Alterar la vía,Cerebro,Abierto,Autólogo,Ninguno,Def,Derivación de ventrículo cerebral,0,
  """

  @quimicos """
  area,code1,code2,code3,code4,code5,code6,codes,description,fatherId,finalNode,id,indx,level,notes,orderList,path,tab
  0,T51.3X1,T51.3X2,-,-,-,-,,1-Propanol,0,1,84636,F,0,,110359.0,"0,84636,",
  """

  setup do
    dir = Path.join(System.tmp_dir!(), "cie10_#{System.unique_integer([:positive])}")
    File.mkdir_p!(dir)
    File.write!(Path.join(dir, "cie10-es-diagnoses.csv"), @diagnosticos)
    File.write!(Path.join(dir, "cie10-es-procedures.csv"), @procedimientos)
    File.write!(Path.join(dir, "cie10-es-chemicals.csv"), @quimicos)
    on_exit(fn -> File.rm_rf!(dir) end)
    {:ok, dir: dir}
  end

  test "importa las tres fuentes y deja los códigos consultables", %{dir: dir} do
    Import.run([dir])

    import Ecto.Query

    cuenta = fn tipo -> Repo.aggregate(from(c in Cie10Code, where: c.type == ^tipo), :count) end
    assert cuenta.("diagnosis") == 3
    assert cuenta.("procedure") >= 1
    assert cuenta.("chemical") >= 1

    diagnostico = Repo.get_by(Cie10Code, code: "A15.0")
    assert diagnostico.description == "Tuberculosis pulmonar"
    assert diagnostico.type == "diagnosis"

    assert Repo.get_by(Cie10Code, code: "0016070").type == "procedure"
    assert Repo.get_by(Cie10Code, code: "T51.3X1").type == "chemical"
  end

  test "conserva los indicadores clínicos de cada diagnóstico", %{dir: dir} do
    Import.run([dir])

    parto = Repo.get_by(Cie10Code, code: "O80")
    assert parto.metadata["maternity"] == true
    assert parto.metadata["perinatal"] == false
    # El indicador de género restringe a qué pacientes aplica el código: si se pierde,
    # el sistema propondría códigos obstétricos a cualquier paciente.
    assert parto.metadata["exclusive_gender"] == "F"
  end

  test "reimportar no duplica y actualiza la descripción", %{dir: dir} do
    Import.run([dir])

    File.write!(
      Path.join(dir, "cie10-es-diagnoses.csv"),
      """
      code,description,perinatal,pediatric,maternity,adult,poa_exempt,no_principal,exclusive_gender
      A15.0,Tuberculosis pulmonar confirmada,0,0,0,1,0,0,
      """
    )

    Import.run([dir])

    import Ecto.Query
    assert Repo.aggregate(from(c in Cie10Code, where: c.type == "diagnosis"), :count) == 3
    assert Repo.get_by(Cie10Code, code: "A15.0").description == "Tuberculosis pulmonar confirmada"
  end
end

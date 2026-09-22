defmodule AppWeb.ApiSpecTest do
  @moduledoc """
  La especificación OpenAPI se genera a partir del router, de modo que se desactualiza sola
  si alguien anota mal un endpoint. Este test la construye para que un error de anotación
  falle aquí y no al abrir la documentación.
  """
  use ExUnit.Case, async: true

  test "la especificación se genera sin errores" do
    spec = AppWeb.ApiSpec.spec()

    assert spec.info.title == "CIE-10 API"
    assert spec.info.version
    assert map_size(spec.paths) > 0
  end

  test "declara el esquema de autenticación por token" do
    spec = AppWeb.ApiSpec.spec()
    assert %{"bearer_auth" => esquema} = spec.components.securitySchemes
    assert esquema.scheme == "bearer"
  end

  test "incluye los endpoints principales" do
    rutas = Map.keys(AppWeb.ApiSpec.spec().paths)
    assert Enum.any?(rutas, &String.contains?(&1, "/auth/login"))
    assert Enum.any?(rutas, &String.contains?(&1, "/cie10"))
  end
end

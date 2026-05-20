# Script for populating the database. You can run it as:
#
#     mix run priv/repo/seeds.exs
#
# Inside the script, you can read and write to any of your
# repositories directly:
#
#     App.Repo.insert!(%App.SomeSchema{})
#
# We recommend using the bang functions (`insert!`, `update!`
# and so on) as they will fail if something goes wrong.

alias App.Repo
alias App.Accounts.User

# Usuario de prueba: admin@test.com / password123
unless Repo.get_by(User, email: "admin@test.com") do
  %User{}
  |> User.registration_changeset(%{
    first_name: "Admin",
    last_name: "Test",
    username: "admin",
    email: "admin@test.com",
    password: "password123"
  })
  |> User.confirm_changeset()
  |> Ecto.Changeset.put_change(:is_admin, true)
  |> Repo.insert!()

  IO.puts("Seed: usuario admin@test.com / password123 creado")
end

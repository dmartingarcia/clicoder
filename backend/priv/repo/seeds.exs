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

admin_email = System.get_env("SEED_ADMIN_EMAIL", "myadminuser@ciecoder.app")
admin_password = System.get_env("SEED_ADMIN_PASSWORD", "password123!")

unless Repo.get_by(User, email: admin_email) do
  %User{}
  |> User.registration_changeset(%{
    first_name: "Admin",
    last_name: "Test",
    username: "admin",
    email: admin_email,
    password: admin_password
  })
  |> User.confirm_changeset()
  |> Ecto.Changeset.put_change(:is_admin, true)
  |> Repo.insert!()

  IO.puts("Seed: usuario #{admin_email}/#{admin_password} creado")
end

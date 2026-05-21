# Dialyzer false positives for Mix tasks.
# Mix.Task behaviour and Mix.Task.run/1 are build-time only and not included
# in Dialyzer PLTs, causing spurious warnings in mix task modules.
[
  {"lib/mix/tasks/cie10_import.ex", :callback_info_missing},
  {"lib/mix/tasks/cie10_import.ex", :unknown_function}
]

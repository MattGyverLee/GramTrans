# Present solely to give this directory's test modules a package-qualified
# import name. tests/unit/test_038_process_rules.py and
# tests/integration/test_038_process_rules.py share a basename, which under
# pytest's default "prepend" import mode collides:
#
#   import file mismatch: imported module 'test_038_process_rules' has this
#   __file__ attribute: .../tests/integration/test_038_process_rules.py
#
# That error aborts COLLECTION, so the entire suite becomes unrunnable in one
# command -- not just the two files involved. With this file present the two
# modules resolve as `unit.test_038_process_rules` and
# `integration.test_038_process_rules` and both collect.

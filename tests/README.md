# Validation

Run from the repository root (Python 3.10 or newer and Bash):

```sh
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
python scripts/validate_probe_framework.py
bash tests/install_mcu_templates_test.sh
```

The lifecycle tests render the actual macro templates with Klipper's Jinja
delimiters and inspect emitted command order. They cover default behavior,
custom ordered actions, parameter forwarding, missing actions and unhomed cancellation.
They do not simulate firmware, probe readings, motors or physical clearance.

# Metadata Harmonizer Tests #
This folder includes the testing setup to ensure proper functionality of all the tools included in the EMSO Metadata 
Harmonizer. The main tool is the `test_metadata_harmonizer.py`, which will perform the following operations:

1. Deploy locally an ERDDAP server using the `docker-compose.yaml` file
2. Create ALL datasets listed in the [examples folder](https://github.com/emso-eric/metadata-harmonizer/tree/develop/examples)
3. Run the [CF Checker](https://github.com/cedadev/cf-checker) against all produced dataset to ensure their compliance with the [CF conventions](https://cfconventions.org/)
4. Integrate all datasets into the local ERDDAP deployment: http://localhost:8080/erddap

⚠️ Only tested in Ubuntu, but will most likely work with WSL. Won't work with regular windows cli.

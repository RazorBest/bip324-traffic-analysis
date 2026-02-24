# Public Grafana dashboard behind a reverse proxy

## Running

Fill in the required environment file in `.env` (or your preffered method of passing environment variables to docker compose). Take as example the file `example_env_file`, copy it to `.env`, and change the values.

** !Be careful: ** The environent variables require a Grafana admin password. Failing to change it increase the risk of someone on the internet getting access to your grafana instance.

Example:
```
docker compose -f grafana-compose.yml up --abort-on-container-exit
```

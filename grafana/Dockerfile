FROM grafana/grafana:12.4-ubuntu

ENV GF_SECURITY_ADMIN_USER=admin

ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_NAME="Main Org."
ENV GF_AUTH_ANONYMOUS_ORG_ROLE="Viewer"
ENV GF_AUTH_ANONYMOUS_HIDE_VERSION="true"
ENV GF_AUTH_ANONYMOUS_DEVICE_LIMIT=100

ENV GF_USERS_ALLOW_SIGN_UP=false
ENV GF_USERS_ALLOW_ORG_CREATE=false

ENV GF_SECURITY_DISABLE_GRAVATAR=true

ENV GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/etc/grafana/provisioning/dashboard_imports/public_dashboards.json

# Env variables used in datasources_provisioning.yml
ENV PROMETHEUS_URL1=${PROMETHEUS_URL1:-"http://localhost:9090"}
ENV PROMETHEUS_URL2=${PROMETHEUS_URL2:-"http://localhost:9091"}
ENV PROMETHEUS_DATASOURCE_TIME_INTERVAL=${PROMETHEUS_DATASOURCE_TIME_INTERVAL:-"1s"}

# The path is present in dashboards_provisioning.yml
RUN mkdir -p /etc/grafana/provisioning/dashboard_imports/
COPY public_dashboards.json /etc/grafana/provisioning/dashboard_imports/
COPY dashboards_provisioning.yml /etc/grafana/provisioning/dashboards/
COPY datasources_provisioning.yml /etc/grafana/provisioning/datasources/

# A script that checks if the mandatory environment variavbles were set
RUN echo '#!/bin/sh \n\
set -e \n\
: "${GF_SECURITY_ADMIN_PASSWORD:?GF_SECURITY_ADMIN_PASSWORD is required}" \n\
: "${GF_SERVER_ROOT_URL:?GF_SERVER_ROOT_URL is required}" \n\
# Execute the givven command \n\
exec "$@"' > /home/grafana/entrypoint.sh\
	&& chmod +x /home/grafana/entrypoint.sh

ENTRYPOINT ["/home/grafana/entrypoint.sh"]

# When running, you'll need to set GF_SECURITY_ADMIN_PASSWORD and GF_SERVER_ROOT_URL
# Eg. GF_SECURITY_ADMIN_PASSWORD=pas; GF_SERVER_ROOT_URL=http://server.com

# Example run: docker run --rm -e GF_SECURITY_ADMIN_PASSWORD=<PASSWORD> -e GF_SERVER_ROOT_URL=http://google.com -p 3000:3000 --name=grafana <IMAGE_ID>

CMD ["grafana", "server", "--homepath=/usr/share/grafana", "--config=/etc/grafana/grafana.ini"]

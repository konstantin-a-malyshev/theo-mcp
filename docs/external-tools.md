# AWS Graph Explorer

The docker can be run with this command:

```bash
docker run -p 8080:80 \
 --name graph-explorer \
 --env PROXY_SERVER_HTTPS_CONNECTION=false \
 --env GRAPH_EXP_HTTPS_CONNECTION=false \
 --env PUBLIC_OR_PROXY_ENDPOINT=http://localhost:8080 \
 --env GRAPH_TYPE=gremlin \
 --env USING_PROXY_SERVER=true \
 --env GRAPH_CONNECTION_URL=http://host.docker.internal:8182 \
 --add-host=host.docker.internal:host-gateway \
 public.ecr.aws/neptune/graph-explorer
```

Open the tool with: `http://localhost:8080/explorer`.

# Neptune Connect

Folder: `/opt/neptune`.
Start command: `node dist/index.js`
Open the tool with: `http://localhost:3000`.
Login: `admin@techvariable.com`
Password: `[s]`

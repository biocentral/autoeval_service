# Biocentral public_hub_services

Microservice to provide open functionality for the biocentral hub server

## Local Deployment

First, set up redis:

```shell
# 1. Install Docker
# 2. Run Redis via Docker (using non default port here)
docker run --name redis-autoeval -p 6380:6379 -d redis:7.4.1
# Optionally: Run redis commander for debug view in browser
docker run --name redis-commander -d --env REDIS_HOSTS=local:redis:6379 --link redis-autoeval:redis -p 8081:8081 rediscommander/redis-commander:latest
# Remove the containers if they are no longer needed
docker rm redis-commander
docker rm redis-autoeval
```

Then install dependencies and run the service:
```shell
uv venv
source .venv/bin/activate
uv sync

python run-autoeval_service.py
```

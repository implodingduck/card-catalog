docker build -t card-catalog .

docker stop card-catalog
docker rm card-catalog

docker run --env-file ./.env --name card-catalog card-catalog
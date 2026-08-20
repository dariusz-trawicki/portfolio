model=ipipan/silver-retriever-base-v1
volume=$PWD/embedding_model_data # share a volume with the Docker container to avoid downloading weights every run

export DOCKER_DEFAULT_PLATFORM=linux/amd64
docker run -p 8080:80 -v $volume:/data --pull always ghcr.io/huggingface/text-embeddings-inference:cpu-1.8 --model-id $model

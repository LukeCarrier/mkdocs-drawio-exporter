# Docker

Build the base container with:

```shell
docker-compose build mkdocs_build
```

In `docker-compose.yml`, set the values `mkdocs_uid` and `mkdocs_gid` to your uid and gid respectively.

You can now launch the container:

```shell
docker-compose up
```

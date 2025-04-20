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

If you're using Docker rootless, you'll need to run the `mkdocs_build` container rather than the `mkdocs` one, since your host user is unintuitively mapped to root on the container, and there's no way to map uids/gids on the bind mounted `/mkdocs` directory. If you have the choice, use Podman instead.

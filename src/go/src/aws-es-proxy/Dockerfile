# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).
FROM golang:1.14.1-alpine3.11
ARG GIT_COMMIT
RUN apk add --update bash curl git && rm /var/cache/apk/*

ENV GO111MODULE=on

WORKDIR /app

COPY go.mod .
COPY go.sum .

RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "-X main.gitCommit=${GIT_COMMIT}"   -o /usr/local/bin/aws-es-proxy


ENV PORT_NUM 9200
EXPOSE ${PORT_NUM}

ENTRYPOINT ["aws-es-proxy"] 
CMD ["-h"]
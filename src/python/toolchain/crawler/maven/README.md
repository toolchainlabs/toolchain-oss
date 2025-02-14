# Maven Crawler

A crawler for Maven artifacts and metadata.

Implemented as a Django app, for ease of database schema management.
A basic working knowledge of the Django ORM is useful in understanding this code.

Uses [`toolchain.workflow`](../workflow) for work scheduling.

## Basic Concepts

### WorkUnitPayload/Worker Types

- `FetchURL`/`URLFetcher`: Fetch the content located at a given URL.

- `VerifySHA1`/`SHA1Verifier`: Verify that a resource matches its published SHA1 hash.

- `ProcessLinkPage`/`LinkPageProcessor`: Process an HTML page of links to other resources.

- `ProcessMavenMetadata`/`MavenMetadataProcessor`: Process a `maven-metadata.xml` file.

- `LocateParentPOM`/`ParentPOMLocator`: Locate the parent POM of a POM file, and trigger fetching it.

- `ExtractPOMInfo`/`POMInfoExtractor`: Extract dependencies and other useful information from a POM file.

- `IndexMavenArtifact`/`MavenArtifactIndexer`: Run Kythe on a Maven artifact's sources.

## Django Management Commands

- `seed`: Seed the database with some initial resources to crawl.

- `crawl`: Run a single process that executes the main loop of the crawl work.

For example, to run a crawl process use
`./src/python/toolchain/service/crawler/maven/worker/manage.py crawl`.

Note that we break from Django's custom of placing the management script in the root,
since we have several Django services, and a lot more to our repo besides.

### Details

To start a local test crawler with completely fresh state:

- [Run a local db](/src/sh/db/README.md), possibly destroying a previous one, or dropping all relevant tables,
  to achieve completely fresh state.

- Run the users ui server:
   `./src/python/toolchain/service/users/ui/manage.py runserver`

- Seed the crawler (note the different path to the worker vs. api `manage.py` scripts):
   `./src/python/toolchain/service/crawler/maven/worker/manage.py seed`

- Run the crawler:
   `./src/python/toolchain/service/crawler/maven/worker/manage.py crawl`

You can now view the workunits by visiting `http://localhost:9050`.

Note: If you are endlessly redirected to the `auth/login/` endpoint, make sure you are
visiting `localhost` not `127.0.0.1` as the hostnames do not share cookies.

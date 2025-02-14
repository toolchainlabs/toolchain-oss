# How the PyPI crawler works

## Background

PyPI publishes a changelog, and provides an API to query it.

The changelog includes events such as "new project added", "new distribution added", "distribution removed"
and so on.

Every event in the changelog is identified by a _serial id_. These serial ids increase monotonically with time.

Our crawler depends heavily on this changelog and its serial ids.

## Overview

The PyPI crawler consists of two work pipelines:

- *Crawl*: `PeriodicChangelogProcessor` (work unit type `PeriodicallyProcessChangelog`) periodically checks the PyPI
  changelog, processes the data in it, updates the DB, and also dumps relevant data out to S3.
- *LevelDB Update*: `PeriodicLevelDbUpdater` (work unit type `PeriodicallyUpdateLevelDb`) periodically scans S3 for
  updates and uses those to update leveldbs (currently the module data and the depgraph data) used by various
  dependency API endpoints.

Note that these two periodic work pipelines are currently independent. It may be desirable in the future to combine
them into a single pipeline, so that a data dump to S3 synchronously triggers leveldb updates, but that requires
further discussion.

## The crawl pipeline

The initial state of the crawl pipeline is established by a full crawl.
After that full crawl, the changelog is sampled and processed as described above.

### The full crawl

A full crawl is managed by a `AllProjectsProcessor` (work unit type `ProcessAllProjects`).
This work is triggered by the `trigger_full` command.

When we create the `ProcessAllProjects` work unit we populate its `serial` field with the latest serial id in the
changelog.  We know that the subsequent full crawl will contain all data at least as far as that serial id (and
probably a bit past it, as it will advance while we're processing, but that's fine).

`AllProjectsProcessor` queries the PyPI API for a list of every single project on PyPI. It then creates a
`ProcessProject` work unit for every project.

#### Avoiding contention

> There are currently over 220K projects on PyPI. Having each `ProcessProject` work unit be a direct requirement of
> `ProcessAllProjects` would cause a lot of contention: every time a `ProcessProject`completed it would decrement
> the `num_unsatisfied_requirements` counter on that single `ProcessAllProjects` row.
> To avoid this, `AllProjectsProcessor` creates N `ProcessAllProjectsShard` work units (currently N=1000).
> The requirements of each `ProcessAllProjectsShard` are a shard's worth of `ProcessProject` work units, and the
> direct requirements of `ProcessAllProjects` are just the N shards.
>
> Note that the worker that processes `ProcessAllProjectsShard` (`AllProjectsShardProcessor`) is trivial.
> These shards exist just to shard the work unit update contention.

Each `ProcessProject` work unit is performed by a `ProjectProcessor` worker. This worker queries the PyPI API
for the list of distributions in the project, creates `Project`, `Release` and `Distribution` instances for them,
schedules `FetchURL` work and `ProcessDistribution` work and sets up the work unit requirements appropriately.

### Processing distributions

`ProcessDistribution` is performed by `DistributionProcessor`. This worker extracts useful metadata from
distributions (sdists, eggs and wheels), such as which modules a distribution provides and what its
requirements are, and writes that metadata to the database in `DistributionData` instances.

### The full dump

After a full crawl has completed, which can take a couple of days and occasionally runs into load issues, such
as being throttled by PyPI, we need to trigger a full dump of the initial data to S3.
This is done manually, using the `dump_full` command.

The full dump work is broken into shards (256 by default), each represented by a `DumpDistributionData` work unit.
Each `DumpDistributionData` work unit has a serial id range and a shard number, and represents a shard of work
for that range.

We don't create all the shards up front. Instead we only create as many work units as the `concurrency` option
allows. For example, if `concurrency` is 4 then we'll initially create shards 0, 64, 128 and 192.

Each `DumpDistributionData` work unit is performed by a `DistributionDataDumper` worker. This worker fetches the
relevant data shard from the db and dumps it to S3.  It then creates the next `DumpDistributionData` shard.

For example, with `concurrency` equal to 4, the worker that completes shard 0 will create shard 1, the worker that
completes shard 64 will create shard 65, and so on, until all 256 shards have been created and completed.

Thus, the number of shards controls how big the db queries (and S3 files) get, while the concurrency controls the
concurrent load on the database.

### The incremental crawl

An incremental crawl is orchestrated by a `PeriodicallyProcessChangelog` work unit, which is
performed by a `PeriodicChangelogProcessor` worker.  The `trigger_incremental` command creates the
initial `PeriodicallyProcessChangelog` work unit.

This worker wakes up and fetches two serial ids:

- The most recent serial id that has been fully processed. This is the most recent serial id in a successful
  `ProcessAllProjects` or `ProcessChangelog` work unit. This means that an incremental crawl requires
  at least one full crawl to have succeeded before it can proceed.
  See the [`most_recent_complete_serial()`](models.py) function.
- The latest serial id known to the PyPI API.

The worker then  creates a `ProcessChangelog` work unit to process the changelog entries between those two
serial ids. It also creates a `DumpDistributionData` work unit (which requires the `ProcessChangelog` work unit),
and then reschedules itself to wake up again after its period expires.

The `ProcessChangelog` work unit is performed by a `ChangelogProcessor` worker. This worker queries the
PyPI API for all distributions added or removed between the two serial ids. For each such distribution
it creates or updates the state of a `Distribution` instance appropriately. For added distributions it
creates a `ProcessDistribution` work unit, which is then processed as described above for the full crawl.

One all `ProcessDistribution` work is done, the `DumpDistributionData` work can proceed. This is a single
shard, unlike in the full dump, because the incremental batch is very small compared to the overall data size.

### The S3 directory structure

The production distribution data is written to
`s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/`.

Each dump creates a subdirectory under this directory, whose name is the serial id range of
the dump: `XXXXXXX-YYYYYYY`. E.g., the full dump is `0-AAAAAAA/`, and incremental dumps are
`AAAAAAA-BBBBBBB/`, `BBBBBBB-CCCCCCC/` and so on.

Under each such subdirectory is one gzipped json file per shard. So the full dump subdirectory
will contain 256 files, and the incremental dump subdirectories will contain a single file.

### Re-dumping

Sometimes we need to recompute metadata by re-running specific `ProcessDistribution` work. For example,
if we change the module extraction heuristics and want to reapply them to some set of dists.

Once these have re-run, the database is updated with the new metadata, but the data dumps are not.

The current solution is to nuke the `s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/`
directory and trigger a full dump using the `dump_full` command. Note that this is not safe to do with concurrent
LevelDB update work, as we'll see.

A full dump only takes a few minutes, and so is an easier solution than trying to re-dump selectively.

## The LevelDB update pipeline

### The LevelDB directory structure

LevelDB data lives under `s3://pypi.us-east-1.toolchain.com/prod/v1/<dataset>/`. Currently we have two datasets,
`depgraph` and `modules`.

The structure under each dataset directory consists of two subdirectories:

`s3://pypi.us-east-1.toolchain.com/prod/v1/<dataset>/input_lists/`
`s3://pypi.us-east-1.toolchain.com/prod/v1/<dataset>/leveldbs/`

Every version of a leveldb has a corresponding input list. Specifically, the input list
`s3://pypi.us-east-1.toolchain.com/prod/v1/<dataset>/input_lists/XXXXX`
describes the inputs that went into creating the leveldb at
`s3://pypi.us-east-1.toolchain.com/prod/v1/<dataset>/leveldbs/XXXXX/`.

The input list file is a text file in which each line is the URI of a data dump file that participated in
creating the leveldb. E.g.,

```text
s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/0-AAAAAAA/python_distribution_data0000.json.gz
s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/0-AAAAAAA/python_distribution_data0001.json.gz
...
s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/0-AAAAAAA/python_distribution_data0255.json.gz
s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/AAAAAAA-BBBBBBB/python_distribution_data0000.json.gz
s3://pypi.us-east-1.toolchain.com/prod/v1/data_dumps/python_distribution_data/BBBBBBB-CCCCCCC/python_distribution_data0000.json.gz
...
```

Notice that this typically includes files from both the initial full dump and incremental dumps.

### The LevelDB update work

There is no distinction between full and incremental LevelDB update work. The same worker either creates an initial
LevelDB or updates an existing one with new data.

The work unit is `UpdateLevelDb` and the corresponding worker is `LevelDbUpdater`. This worker locates the most recent
LevelDB, if any, and reads its input list.

The worker then finds all available data dump files it finds on S3, and subtracts the input list of the previous
LevelDB, if any. It then generates a new LevelDB using the old LevelDB (if any) and the new data dump files.
Finally, it writes an input list file for the new LevelDB, consisting of all the old and new files.

Since writing a single file to S3 is atomic, the presence of the input list is what  signals that the LevelDB exists
and is valid.

Note that if we delete data dump files while a LevelDB update is going on, say because we need to do a full re-dump
(see above for why we might need to do that), then there's a race condition - the update code will read the list of
available files, but by the time it tries to read their content they may have been deleted.

However, adding data dump files while a LevelDB update is going on is safe: we'll read the list of files and they
will all be readable - we might miss some, but the next update will get them.

### TODO: Safe full re-dumps

We need to consider a strategy for re-dumping that doesn't cause the race condition mentioned above vs. LevelDB updates.

It is important to nuke existing dumps before doing a re-dump, so that the directory names (`AAAAAAA-BBBBBBB` etc.)
form an exact non-overlapping set starting at 0.  And it's only this nuking that causes problems, so two possible
solutions are:

- Do the nuking in a work unit, and have it be a requirement of the `PeriodicallyUpdateLevelDb`, so that no new updates
  are triggered while the nuking is pending. However it would have to check that there are no `UpdateLevelDb` work units
  currently in-flight, and reschedule itself if there are.

- Have a global lock: each LevelDB update work holds a shared lock in the appropriate critical section,
  and the nuking work cannot proceed until it acquires an exclusive lock.  We can implement this lock in the database
  pretty easily.

The former solution has the advantage of using existing workflow capabilities. The latter is conceptually simpler.

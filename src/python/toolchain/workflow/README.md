# Toolchain Workflow

A very simple generic workflow idiom.
For troubleshooting info see [run book](./RUNBOOK.md)

Used to implement the Maven and PyPi crawlers, and buildsense data processing, and can be reused for other purposes.

Implemented as a Django app, for ease of database schema management.
A basic working knowledge of the Django ORM is useful in understanding this code.

## Basic Concepts

- `WorkUnit`: A model representing a unit of work.

- `WorkUnitPayload`: A model representing arguments to a work unit.
  Subclasses of this model represent specific work types, and provide any
  input data required by the code performing the work.
  
- `WorkUnitRequirement`: A model representing a dependency of a `WorkUnit` X on some other `WorkUnit` Y, such that Y must complete before work on X can begin.

- `Worker`: A base class for classes that perform work. Each subclass of of this class performs work described by a specific subclass of `WorkUnitPayload`.

- `WorkExecutor`: Executes the work described by a `WorkUnit`, using a `Worker`.
  It takes care of atomically updating the database with the results of the work attempt.

- `WorkDispatcher`: The main work management loop.  It polls the database
  for available work and uses a `WorkExecutor` to execute each `WorkUnit`.
  It takes care of registering `Worker` types against `WorkUnit` types, acquiring task leases and so on.

- `WorkException`: An `Exception` subclass raised by a worker to indicate that the work has failed. An exception can be in one of two categories:
  `TRANSIENT` or `PERMANENT`. A `TRANSIENT` error (e.g., a 500 when fetching a web resource) may be retried later, while a `PERMANENT` error (e.g., a 400 when fetching a web resource) should not be retried until the issue has been fixed.

- `WorkExceptionLog`: A model representing a log of an exception encountered while performing work.

## Details

The production database is PostgreSQL, which supports the transactional properties we require, such as exclusive row locking via "SELECT FOR UPDATE".

A worker does work in its `do_work()` method. It can signal one of three outcomes to the system:

- If it raises an exception, the work has failed.
- If it returns `True`, the work has succeeded.
- If it returns `False`, the work should be rescheduled later.
  This is typically used by workers to add new requirements to the work unit they're acting on.

Using the `on_success()/on_failure()/on_reschedule()` callbacks, a worker can commit to the database in the same transaction as the one the dispatcher uses to mark the work as successful.  In particular, the worker can insert new `WorkUnit` instances, of any type, to be performed in the future.  
In this way, work can trigger further work dynamically.  There is no need to produce a full work graph up front.

For example, a work unit that computes the location of some web resource can insert a work unit to cause that web resource to be fetched, and that work unit can insert another work unit to process the content of that web resource.

Workers get an exclusive lease on a specific unit of work for some period of time.  Only the worker holding the lease can commit.
Therefore any database work performed by the worker in its `on_*()` callbacks need not be idempotent.  However any side effects must be idempotent, as
there is no guarantee that a worker will execute only once.  In general, side effects are discouraged.  All input and output of work should be generated via the database.

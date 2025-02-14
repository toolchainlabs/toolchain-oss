# Maven Package repo

Models Maven concepts.

Implemented as a Django app, for ease of database schema management.
A basic working knowledge of the Django ORM is useful in understanding this code.

## Basic Concepts

### Models

- `MavenArtifact`: An unversioned Maven artifact, identified by Maven GA coordinates,
  i.e., a `(groupId, artifactId)` pair.

- `MavenArtifactVersion`: A versioned Maven artifact, identified by Maven GAV coordinates,
  i.e., a `(groupId, artifactId, version)` triple.

- `MavenDependency`: A Maven dependency specification. The target of the dependency can be
  a specific version of some other artifact, but can also be a range of versions or any
  other specification allowed by Maven.

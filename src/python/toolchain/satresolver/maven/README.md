# Dependency graph and configuration for maven specific resolves

## Pom Specific Definitions

Definitions from [https://maven.apache.org/pom.html#Dependencies](https://maven.apache.org/pom.html#Dependencies)

## Classifier

>The classifier distinguishes artifacts that were built from the same POM but differ in content. It is some optional and arbitrary string that - if present - is appended to the artifact name just after the version number. As a motivation for this element, consider for example a project that offers an artifact targeting JRE 1.5 but at the same time also an artifact that still supports JRE 1.4. The first artifact could be equipped with the classifier jdk15 and the second one with jdk14 such that clients can choose which one to use.
>
>Another common use case for classifiers is to attach secondary artifacts to the project's main artifact. If you browse the Maven central repository, you will notice that the classifiers sources and javadoc are used to deploy the project source code and API docs along with the packaged class files.

TODO: The resolver does not currently take classifiers into account and it is unclear how it should do so.

The major question is whether depending on the same artifact at different classifiers should be a conflict. In the case of `foo:bar:1.0.0-jdk14`, and `foo:bar:1.0.0-jdk15` maybe it should be (and maybe both of these should also conflict with `bar:baz:2.0.0-jdk8`). On the other hand, `foo:bar:1.0.0-javadoc` is not a conflict with `foo:bar:1.0.0-source`, or `foo:bar:1.0.0`. Classifiers will be needed in order to fetch the package correctly though, as the classifier is appended to the path on maven central.

## Type

>Corresponds to the chosen dependency type. This defaults to jar. While it usually represents the extension on the filename of the dependency,that is not always the case: a type can be mapped to a different extension and a classifier. The type often corresponds to the packaging used, though this is also not always the case. Some examples are jar, ejb-client and test-jar: see default artifact handlers for a list. New types can be defined by plugins that set extensions to true, so this is not a complete list.

See [artifact-handlers](https://maven.apache.org/ref/3.6.0/maven-core/artifact-handlers.html) for more details.

TODO: The resolver does not currently take Type into account.

## Scope

>This element refers to the classpath of the task at hand (compiling and runtime, testing, etc.) as well as how to limit the transitivity of a dependency. There are five scopes available:
>
> - *compile* - this is the default scope, used if none is specified. Compile dependencies are available in all classpaths. Furthermore, those dependencies are propagated to dependent projects.
> - *provided* - this is much like compile, but indicates you expect the JDK or a container to provide it at runtime. It is only available on the compilation and test classpath, and is not transitive.
> - *runtime* - this scope indicates that the dependency is not required for compilation, but is for execution. It is in the runtime and test classpaths, but not the compile classpath.
> - *test* - this scope indicates that the dependency is not required for normal use of the application, and is only available for the test compilation and execution phases. It is not transitive.
> - *system* - this scope is similar to provided except that you have to provide the JAR which contains it explicitly. The artifact is always available and is not looked up in a repository.

`MavenConfig` takes a set of scopes as an argument and will return a resolve specific to the provided scopes. By default it will use scope `compile`. Provided scopes must be one of those defined above.

## Optional

>Marks optional a dependency when this project itself is a dependency. Confused? For example, imagine a project A that depends upon project B to compile a portion of code that may not be used at runtime, then we may have no need for project B for all project. So if project X adds project A as its own dependency, then Maven will not need to install project B at all. Symbolically, if => represents a required dependency, and --> represents optional, although A=>B may be the case when building A X=>A-->B would be the case when building X.
>
>In the shortest terms, optional lets other projects know that, when you use this project, you do not require this dependency in order to work correctly.

TODO: `MavenConfig` currently ignores all dependencies marked as optional. Add an `include_optional` parameter.

## Version Spec

>Dependencies' version element define version requirements, used to compute effective dependency version. Version requirements have the following syntax:
>
>1.0: "Soft" requirement on 1.0 (just a recommendation, if it matches all other ranges for the dependency)
>[1.0]: "Hard" requirement on 1.0
>(,1.0]: x <= 1.0
>[1.2,1.3]: 1.2 <= x <= 1.3
>[1.0,2.0): 1.0 <= x < 2.0
>[1.5,): x >= 1.5
>(,1.0],[1.2,): x <= 1.0 or x >= 1.2; multiple sets are comma-separated
>(,1.1),(1.1,): this excludes 1.1 (for example if it is known not to work in combination with this library)

When building our `MavenGraph` we translate all version specs into sets of valid versions as soon as possible using `MavenVersionSpec` (see: src/python/toolchain/packagerepo/maven/version/maven_semantic_version_spec.py) to calculate the set of valid versions for a given spec.

### A Note on "Soft" Requirements

"Soft" requirements are unfortunately very common, frequently occurring in isolation - meaning all versions of this dependency are valid.

When calculating the best `PackageVersion` for a package we check for "Soft" requirements by first checking the current solution for a list of `PackageVersions` that have been decided, and then checking  the `MavenGraph` to see if any of the already decided `PackageVersions` have soft requirements on the relevant package. If there are soft requirements on otherwise valid versions of the package, we select the most commonly preferred version. If there are no soft requirements or if there are soft requirements on versions that are invalid, we ignore them.

Soft requirements are ignored when calculating the most constrained package (the package with the fewest valid versions), so we'll make as many firm decisions as possible before attempting to select a preferred version. It is possible that the most preferred version of a package will change based on decisions made later in the resolve, but we never go back to check. It's possible we should, but it adds substantial complexity to support ill defined dependencies.

## Exclusions

>Exclusions contain one or more exclusion elements, each containing a groupId and artifactId denoting a dependency to exclude. Unlike optional, which may or may not be installed and used, exclusions actively remove themselves from the dependency tree.

Exclusions may contain wildcards meaning we should exclude all transitive dependencies of this dependency.

```xml
  <groupId>*</groupId>
  <artifactId>*</artifactId>
```

See [https://maven.apache.org/guides/introduction/introduction-to-optional-and-excludes-dependencies.html](https://maven.apache.org/guides/introduction/introduction-to-optional-and-excludes-dependencies.html) for more details on exclusions.

TODO: `POMInfoExtractor` and the `MavenDependency` django model do not currently include exclusion information.

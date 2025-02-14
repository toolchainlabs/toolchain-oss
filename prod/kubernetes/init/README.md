Configs for initializing cluster-wide Kubernetes admin services.

In some cases we embed config snippets in the apply scripts, usually because they didn't originate from a
linkable source. But in almost all cases we consume the standard configs suggested by Kubernetes from specific
github SHAs in their repos (not tags, which might be repointed).

In some cases we use yq to apply necessary changes to the standard configs, such as replacing placeholders or
adding annotations to the YAML.

Note that running this will create containers from public docker images that we currently just assume have
not been maliciously tampered with.  So locking down the public kubernetes configs is only half the battle.

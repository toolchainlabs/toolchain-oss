// Copyright 2020 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![deny(warnings)]
#![allow(clippy::derive_partial_eq_without_eq)]
#![allow(clippy::doc_lazy_continuation)]

// NOTE: Prost automatically relies on the existence of this nested module structure because
// it uses multiple `super` references (e.g., `super::super::super::Foo`) to traverse out of
// a module to refer to protos in other modules.

pub mod google {
    pub mod bytestream {
        include!(concat!(env!("OUT_DIR"), "/google.bytestream.rs"));
    }
    pub mod devtools {
        pub mod remoteworkers {
            pub mod v1test2 {
                include!(concat!(
                    env!("OUT_DIR"),
                    "/google.devtools.remoteworkers.v1test2.rs"
                ));
            }
        }
    }
    pub mod longrunning {
        include!(concat!(env!("OUT_DIR"), "/google.longrunning.rs"));
    }
    pub mod rpc {
        include!(concat!(env!("OUT_DIR"), "/google.rpc.rs"));
    }
}

pub mod build {
    pub mod bazel {
        pub mod remote {
            pub mod execution {
                pub mod v2 {
                    include!(concat!(
                        env!("OUT_DIR"),
                        "/build.bazel.remote.execution.v2.rs"
                    ));
                }
            }
        }
        pub mod semver {
            include!(concat!(env!("OUT_DIR"), "/build.bazel.semver.rs"));
        }
    }
}

#[cfg(test)]
mod tests;

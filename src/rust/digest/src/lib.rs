// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::convert::TryFrom;
use std::fmt;

use bytes::Bytes;
use protos::build::bazel::remote::execution::v2 as remoting_protos;
use sha2::{Digest as Sha2Digest, Sha256};

// See the [`hashing` crate](https://github.com/pantsbuild/pants/blob/master/src/rust/engine/hashing/src/lib.rs)
// for the inspiration for this module.

const HASH_SIZE_BYTES: usize = 32;

const EMPTY_HASH_BYTES: [u8; HASH_SIZE_BYTES] = [
    0xe3, 0xb0, 0xc4, 0x42, 0x98, 0xfc, 0x1c, 0x14, 0x9a, 0xfb, 0xf4, 0xc8, 0x99, 0x6f, 0xb9, 0x24,
    0x27, 0xae, 0x41, 0xe4, 0x64, 0x9b, 0x93, 0x4c, 0xa4, 0x95, 0x99, 0x1b, 0x78, 0x52, 0xb8, 0x55,
];

#[derive(Clone, Copy, Hash, Eq, PartialEq, Ord, PartialOrd)]
pub struct Digest {
    pub hash: [u8; HASH_SIZE_BYTES],
    pub size_bytes: usize,
}

impl fmt::Debug for Digest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Digest<{}, {}>", hex::encode(self.hash), self.size_bytes)
    }
}

impl Digest {
    pub const EMPTY: Self = Self {
        hash: EMPTY_HASH_BYTES,
        size_bytes: 0,
    };

    pub fn new(hash_str: &str, size_bytes: usize) -> Result<Self, String> {
        let hash =
            hex::decode(hash_str).map_err(|err| format!("Failed to convert digest: {err}"))?;
        if hash.len() != HASH_SIZE_BYTES {
            return Err(format!("Digest had unexpected length {}", hash.len()));
        }
        Self::from_slice(&hash, size_bytes)
    }

    pub fn from_slice(hash: &[u8], size_bytes: usize) -> Result<Self, String> {
        if hash.len() != HASH_SIZE_BYTES {
            return Err(format!("Digest had unexpected length {}", hash.len()));
        }
        let mut digest = Digest {
            hash: [0; HASH_SIZE_BYTES],
            size_bytes,
        };
        digest.hash.clone_from_slice(hash);
        Ok(digest)
    }

    pub fn of_bytes(content: &Bytes) -> Result<Self, String> {
        let mut hasher = Sha256::default();
        hasher.update(&content[..]);
        let hash = hasher.finalize();
        let mut digest = Digest {
            hash: [0; HASH_SIZE_BYTES],
            size_bytes: content.len(),
        };
        digest.hash.clone_from_slice(hash.as_slice());
        Ok(digest)
    }

    pub fn hex(&self) -> String {
        hex::encode(self.hash)
    }
}

impl TryFrom<remoting_protos::Digest> for Digest {
    type Error = String;

    fn try_from(d: remoting_protos::Digest) -> Result<Self, Self::Error> {
        Digest::new(&d.hash, d.size_bytes as usize)
    }
}

impl From<Digest> for remoting_protos::Digest {
    fn from(digest: Digest) -> Self {
        remoting_protos::Digest {
            hash: hex::encode(digest.hash),
            size_bytes: digest.size_bytes as i64,
        }
    }
}

pub fn required_digest(
    field_name: &str,
    api_digest_opt: Option<remoting_protos::Digest>,
) -> Result<Digest, String> {
    let api_action_digest = match api_digest_opt {
        Some(digest) => digest,
        None => return Err(format!("Missing {field_name}")),
    };
    api_action_digest
        .try_into()
        .map_err(|err| format!("Malformed {field_name}: {err}"))
}

#[cfg(test)]
mod tests {
    use std::convert::TryFrom;
    use std::fmt::Write;

    use protos::build::bazel::remote::execution::v2 as remoting_protos;

    use super::Digest;
    use bytes::BytesMut;

    #[test]
    fn convert_from_reapi_digest() {
        let reapi_digest = remoting_protos::Digest {
            hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855".to_owned(),
            size_bytes: 0,
        };

        let digest = Digest::try_from(reapi_digest).unwrap();
        assert_eq!(digest, Digest::EMPTY);
    }

    #[test]
    fn convert_to_reapi_digest() {
        let expected_reapi_digest = remoting_protos::Digest {
            hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855".to_owned(),
            size_bytes: 0,
        };

        let actual_reapi_digest: remoting_protos::Digest = Digest::EMPTY.into();

        assert_eq!(actual_reapi_digest, expected_reapi_digest);
    }

    #[test]
    fn hash_bytes() {
        let content = {
            let mut buf = BytesMut::new();
            buf.write_str("foobar").unwrap();
            buf.freeze()
        };
        let actual_digest = Digest::of_bytes(&content).unwrap();
        let expected_digest = Digest::new(
            "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
            content.len(),
        )
        .unwrap();
        assert_eq!(actual_digest, expected_digest);
    }
}

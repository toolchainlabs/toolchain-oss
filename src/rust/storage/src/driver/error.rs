// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::fmt;

use redis::RedisError;
use tonic::Status;

use crate::Digest;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StorageError {
    Cancelled(String),
    InvalidArgument(String),
    InvalidSize {
        expected_size: usize,
        is_data_loss: bool,
    },
    InvalidHash {
        expected_digest: Digest,
        actual_digest: Digest,
        is_data_loss: bool,
    },
    Internal(String),
    Unavailable(String),
    OutOfRange(String, usize),
}

impl std::error::Error for StorageError {}

impl fmt::Display for StorageError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            StorageError::Cancelled(msg) => write!(f, "Cancelled: {msg}"),
            StorageError::InvalidArgument(msg) => write!(f, "Invalid argument: {msg}"),
            StorageError::InvalidSize {
                expected_size,
                is_data_loss,
            } => {
                if *is_data_loss {
                    write!(
                        f,
                        "Invalid size detected for content in data store (expected size was {expected_size})"
                    )
                } else {
                    write!(
                        f,
                        "Invalid size for provided content (expected size was {expected_size})"
                    )
                }
            }
            StorageError::InvalidHash {
                expected_digest,
                actual_digest,
                is_data_loss,
            } => {
                if *is_data_loss {
                    write!(
                        f,
                        "Invalid hash detected for content in data store (expected digest was {expected_digest:?}, actual digest is {actual_digest:?})"
                    )
                } else {
                    write!(
                        f,
                        "Invalid hash for provided content (expected digest was {expected_digest:?}, actual digest is {actual_digest:?})"
                    )
                }
            }
            StorageError::Internal(msg) => {
                write!(f, "{msg}")
            }
            StorageError::Unavailable(msg) => {
                write!(f, "{msg}")
            }
            StorageError::OutOfRange(param_name, value) => {
                write!(f, "Out-of-range value {param_name} for parameter {value}")
            }
        }
    }
}

impl From<RedisError> for StorageError {
    fn from(err: RedisError) -> Self {
        let err_str = format!("Redis error: {err}");
        if err.is_io_error()
            || err.is_cluster_error()
            || err.is_connection_refusal()
            || err.is_connection_dropped()
            || err.is_timeout()
        {
            StorageError::Unavailable(err_str)
        } else {
            StorageError::Internal(err_str)
        }
    }
}

impl From<String> for StorageError {
    fn from(msg: String) -> Self {
        StorageError::Internal(msg)
    }
}

impl From<StorageError> for String {
    fn from(err: StorageError) -> Self {
        format!("{err}")
    }
}

impl From<StorageError> for Status {
    fn from(err: StorageError) -> Self {
        match err {
            StorageError::Cancelled(msg) => Status::cancelled(msg),
            StorageError::InvalidArgument(msg) => Status::invalid_argument(msg),
            StorageError::InvalidSize { is_data_loss, .. }
            | StorageError::InvalidHash { is_data_loss, .. } => {
                let msg = format!("{err}");
                if is_data_loss {
                    Status::data_loss(msg)
                } else {
                    Status::invalid_argument(msg)
                }
            }
            StorageError::Internal(msg) => Status::internal(msg),
            StorageError::Unavailable(msg) => Status::unavailable(msg),
            StorageError::OutOfRange(_, _) => {
                let msg = format!("{err}");
                Status::out_of_range(msg)
            }
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StreamingWriteError {
    StorageError(StorageError),
    AlreadyExists,
}

impl StreamingWriteError {
    /// For most consumers, an `AlreadyExists` error during streaming should be treated as a
    /// successful write overall. This method can be used with `Result::or_else` to convert
    /// a `StreamingWriteError` into a `StorageError` while rescuing `AlreadyExists` into a
    /// successful Result.
    pub fn ok_if_already_exists(err: Self) -> Result<(), StorageError> {
        match err {
            Self::AlreadyExists => Ok(()),
            Self::StorageError(e) => Err(e),
        }
    }

    #[cfg(test)]
    pub fn unwrap_storage_error(self) -> StorageError {
        match self {
            Self::StorageError(e) => e,
            Self::AlreadyExists => panic!("Was not a StorageError!"),
        }
    }
}

impl From<StorageError> for StreamingWriteError {
    fn from(err: StorageError) -> Self {
        Self::StorageError(err)
    }
}

impl From<String> for StreamingWriteError {
    fn from(err: String) -> Self {
        Self::StorageError(err.into())
    }
}

impl From<RedisError> for StreamingWriteError {
    fn from(err: RedisError) -> Self {
        Self::StorageError(err.into())
    }
}

// Copyright 2022 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use bytes::{Bytes, BytesMut};
use futures::{Stream, TryStreamExt};

use crate::driver::StorageError;

/// Consolidate a stream of `Bytes` into a single `Bytes`.
pub async fn consolidate_stream(
    stream: impl Stream<Item = Result<Bytes, StorageError>> + Unpin,
) -> Result<Bytes, StorageError> {
    let mut buffers: Vec<_> = stream.try_collect().await?;
    match buffers.len() {
        0 => return Ok(Bytes::new()),
        1 => return Ok(buffers.pop().unwrap()),
        _ => {}
    }

    let result_len = buffers.iter().map(|b| b.len()).sum();
    let mut result = BytesMut::with_capacity(result_len);
    for buffer in buffers {
        result.extend_from_slice(&buffer);
    }

    Ok(result.freeze())
}

// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use std::pin::Pin;
use std::task::{Context, Poll};

use futures::{Future, Stream};

/// SyncWrapper implements a "statically-checked mutex" prototyped in [this Rust blog
/// entry](https://internals.rust-lang.org/t/what-shall-sync-mean-across-an-await/12020/2).
///
/// It solves a mismatch between Tonic and async_trait where Tonic requires that `Stream`'s
/// are `Send + Sync` and `async_trait` produces `Future`s that are just `Send`. The issue
/// arises when trying to use a `Future` produced by `async_trait` in implementing a `Stream`
/// returned to Tonic. See [the Tonic issue on the Sync requirement](https://github.com/hyperium/tonic/issues/117)
/// for more information.
///
/// The solution is to wrap the `Send` `Stream` with this `SyncWrapper` which *statically*
/// guarantees that only a single thread can access its contents by virtue of the fact that
/// the only methods granting access require a &mut reference. Thus, it is safe for this
/// type to implement `Sync`.
#[repr(transparent)]
pub struct SyncWrapper<T: ?Sized>(T);

impl<T> SyncWrapper<T> {
    pub fn new(t: T) -> SyncWrapper<T> {
        SyncWrapper(t)
    }
    pub fn into_inner(self) -> T {
        self.0
    }
}

impl<T: ?Sized> SyncWrapper<T> {
    pub fn get_mut(&mut self) -> &mut T {
        &mut self.0
    }

    pub fn get(&self) -> &T {
        &self.0
    }

    pub fn get_mut_pin(self: Pin<&mut Self>) -> Pin<&mut T> {
        unsafe { self.map_unchecked_mut(|this| &mut this.0) }
    }
}

// SAFETY: An immutable reference to SyncWrapper<T> is worthless because there is no way to
// gain mutable access to its contents. Thus, it is safe to share such a reference between
// threads (which is the capability represented by `Sync`).
unsafe impl<T: ?Sized> Sync for SyncWrapper<T> {}

//
// Extension of the blog's solution to include Future and Stream implementations.
//
// SAFETY: The poll methods of `Future` and `Stream` require a &mut reference, and thus do not
// violate the single thread access requirement of `SyncWrapper`.
//

impl<F: Future> Future for SyncWrapper<F> {
    type Output = F::Output;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        self.get_mut_pin().poll(cx)
    }
}

impl<S: Stream> Stream for SyncWrapper<S> {
    type Item = S::Item;

    fn poll_next(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        self.get_mut_pin().poll_next(cx)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        self.get().size_hint()
    }
}

/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

// Common interface for API list responses.
export interface ApiListResponse<T> {
  results: T[];
  total_pages: number;
  page: number;
  max_pages: number;
}

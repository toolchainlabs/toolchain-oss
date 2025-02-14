// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use serde::{Deserialize, Serialize};

#[derive(Default, Deserialize, Serialize)]
#[serde(rename_all = "UPPERCASE")]
struct Transition {
    pub timestamp: u64,
    pub from_label: Option<String>,
    pub to_label: Option<String>,
}

/// A single secret and its state transitions.
#[derive(Default, Deserialize, Serialize)]
#[serde(rename_all = "UPPERCASE")]
struct Secret {
    /// The secret's value
    pub value: String,

    /// The state transitions for a secret.
    pub transitions: Option<Vec<Transition>>,
}

/// A set of "rotatable secrets". This code only cares about decoding the `current` secret
/// and so does not decode any of the other supported states for a secret: namely,
/// "previous", "proposed", "removable", and "removed". (These keys will be ignored by serde.)
#[derive(Default, Deserialize, Serialize)]
#[serde(rename_all = "UPPERCASE")]
struct RotatableSecret {
    /// The current secret.
    pub current: Option<Vec<Secret>>,

    /// Previous values that may still be in use.
    pub previous: Option<Vec<Secret>>,

    /// A proposed new value for the secret.  Represented as a singleton list, for uniformity.
    pub proposed: Option<Vec<Secret>>,

    /// A list of previous values that are definitely not in use.
    pub removable: Option<Vec<Secret>>,

    /// A list of previous values that have been fully removed. Kept only for auditing/debugging.
    /// Can be pruned.
    pub removed: Option<Vec<Secret>>,
}

#[allow(dead_code)]
pub fn parse_secret(buffer: impl AsRef<[u8]>) -> Result<String, String> {
    let rotatable_secret: RotatableSecret = serde_json::from_slice(buffer.as_ref())
        .map_err(|err| format!("Failed to parse rotatable secret: {err}"))?;

    match rotatable_secret.current.unwrap_or_default().as_slice() {
        [secret] => Ok(secret.value.clone()),
        [] => Err("Failed to parse rotatable secret: No current secret found".to_owned()),
        _ => Err("Failed to parse rotatable secret: Multiple current secrets found".to_owned()),
    }
}

#[cfg(test)]
mod tests {
    use super::parse_secret;

    #[test]
    fn decodes_current_secret() {
        let data = "
        {
            \"CURRENT\": [
                {
                    \"VALUE\": \"value1\",
                    \"TRANSITIONS\": [
                        {\"TIMESTAMP\": 1, \"FROM_LABEL\": null, \"TO_LABEL\": \"PROPOSED\"},
                        {\"TIMESTAMP\": 2, \"FROM_LABEL\": \"PROPOSED\", \"TO_LABEL\": \"CURRENT\"}
                    ]
                }
            ]
        }
        ";

        let secret = parse_secret(data).unwrap();
        assert_eq!(secret, "value1");
    }

    #[test]
    fn fails_with_multiple_current_secrets() {
        let data = "
        {
            \"CURRENT\": [
                {
                    \"VALUE\": \"value1\",
                    \"TRANSITIONS\": [
                        {\"TIMESTAMP\": 1, \"FROM_LABEL\": null, \"TO_LABEL\": \"PROPOSED\"},
                        {\"TIMESTAMP\": 2, \"FROM_LABEL\": \"PROPOSED\", \"TO_LABEL\": \"CURRENT\"}
                    ]
                },
                {
                    \"VALUE\": \"value1\",
                    \"TRANSITIONS\": [
                        {\"TIMESTAMP\": 1, \"FROM_LABEL\": null, \"TO_LABEL\": \"PROPOSED\"},
                        {\"TIMESTAMP\": 2, \"FROM_LABEL\": \"PROPOSED\", \"TO_LABEL\": \"CURRENT\"}
                    ]
                }
            ]
        }
        ";

        let err = parse_secret(data).unwrap_err();
        assert!(err.contains("Multiple current secrets found"));
    }

    #[test]
    fn fails_with_no_current_secret() {
        let data = "
        {
            \"CURRENT\": []
        }
        ";

        let err = parse_secret(data).unwrap_err();
        assert!(err.contains("No current secret found"));
    }
}

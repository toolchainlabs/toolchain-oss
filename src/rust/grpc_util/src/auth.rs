// Copyright 2021 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).

#![allow(clippy::upper_case_acronyms)]
#![allow(clippy::result_large_err)]

use std::collections::HashMap;

use biscuit::errors::Error as BiscuitError;
use biscuit::errors::ValidationError;
use biscuit::jwa::{Algorithm, SignatureAlgorithm};
use biscuit::jwk::JWK;
use biscuit::Validation;
use biscuit::{ClaimPresenceOptions, TemporalOptions, ValidationOptions};
use biscuit::{Presence, SingleOrMultiple};
use chrono::Duration;
use chrono::TimeDelta;
use serde::{Deserialize, Serialize};
use tonic::metadata::MetadataMap;
use tonic::Status;

#[derive(Copy, Clone, Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
pub enum AuthScheme {
    Jwt,
    AuthToken,
    DevOnlyNoAuth,
}

#[derive(strum_macros::Display)]
pub enum Permissions {
    #[strum(serialize = "cache_ro")]
    Read,
    #[strum(serialize = "cache_rw")]
    ReadWrite,
    #[strum(serialize = "exec")]
    Execute,
}

impl Permissions {
    pub fn is_valid(&self, audience: &SingleOrMultiple<String>) -> bool {
        let all_valid_audiences = match self {
            Self::Read => vec![
                Self::Read.to_string(),
                Self::ReadWrite.to_string(),
                Self::Execute.to_string(),
            ],
            Self::ReadWrite => vec![Self::ReadWrite.to_string(), Self::Execute.to_string()],
            Self::Execute => vec![Self::Execute.to_string()],
        };
        all_valid_audiences
            .iter()
            .any(|valid_aud| audience.contains(valid_aud))
    }
}

/// Extract the bearer auth token from the request's headers.
///
/// Logs if there are any issues with the header.
pub fn get_bearer_token(metadata: &MetadataMap) -> Result<String, Status> {
    fn get(metadata: &MetadataMap) -> Result<String, String> {
        let auth_value = metadata
            .get("authorization")
            .ok_or("authorization header not provided")?
            .to_str()
            .map_err(|err| err.to_string())?;
        auth_value
            .strip_prefix("Bearer ")
            .ok_or_else(|| "authorization header did not start with `Bearer `".to_owned())
            .map(|tok| tok.to_owned())
    }

    get(metadata).map_err(|err| {
        log::error!(
            "auth_failure: missing or malformed authorization header: {}. metadata: {:?}",
            err,
            metadata
        );
        Status::unauthenticated("missing or invalid authorization header")
    })
}

// ---------------------------------------------------------------------------------------
// Auth token
// ---------------------------------------------------------------------------------------

#[derive(Eq, Hash, PartialEq, Deserialize)]
pub struct AuthToken(String);

impl AuthToken {
    pub fn new(token: String) -> Self {
        Self(token)
    }

    /// The first 10 characters of the token, with the rest truncated for security.
    pub fn truncated(&self) -> &str {
        let len = std::cmp::min(self.0.len(), 10);
        &self.0[0..len]
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct AuthTokenEntry {
    /// The ID for this auth token entry.
    pub id: String,
    /// The customer ID.
    pub instance_name: String,
    /// The human-readable slug for the customer.
    ///
    /// This should not be used for auth, and is only to have more readable logs.
    pub customer_slug: String,
    /// Whether the token is still active, e.g. if expired or revoked.
    pub is_active: bool,
}

pub fn validate_auth_token(
    token: AuthToken,
    requested_instance_name: &str,
    token_mapping: &HashMap<AuthToken, AuthTokenEntry>,
) -> Result<(), Status> {
    let entry = token_mapping.get(&token).ok_or_else(|| {
        log::error!("auth_failure: token {}... not found", token.truncated());
        Status::unauthenticated("auth token not valid")
    })?;
    if entry.instance_name != requested_instance_name {
        log::error!(
            "auth_failure: requested instance name {requested_instance_name} but only authorized \
            for {} (customer: {}). token: {}...",
            entry.instance_name,
            entry.customer_slug,
            token.truncated()
        );
        return Err(Status::unauthenticated("auth token not valid"));
    };
    if !entry.is_active {
        log::error!(
            "auth_failure: token {}... is not active (customer: {})",
            token.truncated(),
            entry.customer_slug,
        );
        return Err(Status::unauthenticated("auth token not valid"));
    }
    Ok(())
}

// ---------------------------------------------------------------------------------------
// JWT auth
// ---------------------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PrivateClaims {
    toolchain_customer: String,
}

pub type ClaimsSet = biscuit::ClaimsSet<PrivateClaims>;
pub type JWKSet = biscuit::jwk::JWKSet<biscuit::Empty>;
pub type JWT = biscuit::JWT<PrivateClaims, biscuit::Empty>;

pub fn deserialize_jwk_set(json: &str) -> Result<JWKSet, serde_json::Error> {
    serde_json::from_str(json)
}

/// Validate the JWT and its claims.
///
/// This intentionally returns vague messages for obfuscation/security, but it logs the full error.
pub fn validate_jwt(
    token: String,
    requested_instance_name: &str,
    required_permissions: Permissions,
    jwk_set: &JWKSet,
) -> Result<(), Status> {
    let jwt = JWT::new_encoded(&token);
    let claims = decode_jwt(jwk_set, jwt).map_err(|err| {
        log::error!(
            "auth_failure: token could not be decoded with our JWK Set: {err}. token: {token}"
        );
        Status::unauthenticated("authorization failed")
    })?;
    validate_claims_defined_and_not_expired(&claims).map_err(|err| {
        log::error!("auth_failure: token validation failed: {err}. token: {token}",);
        Status::unauthenticated("authorization failed")
    })?;

    if claims.private.toolchain_customer != requested_instance_name {
        log::error!(
            "auth_failure: requested instance name {requested_instance_name} but only authorized for {}. token {token}",
            claims.private.toolchain_customer,
        );
        return Err(Status::invalid_argument("unknown instance name"));
    };

    let audience = claims.registered.audience.unwrap();
    if !required_permissions.is_valid(&audience) {
        log::error!(
            "auth_failure: insufficient permissions in `audience`, needed {required_permissions} \
            but given {audience:?}. token {token}",
        );
        return Err(Status::permission_denied("insufficient permissions"));
    }

    Ok(())
}

fn decode_jwt(jwk_set: &JWKSet, jwt: JWT) -> Result<ClaimsSet, BiscuitError> {
    // The JWKs will have the algorithm used already in their metadata.
    let decoded = jwt.decode_with_jwks(jwk_set, None)?;
    decoded.payload().map(|payload| payload.to_owned())
}

fn validate_claims_defined_and_not_expired(claims_set: &ClaimsSet) -> Result<(), ValidationError> {
    let validation_options = ValidationOptions {
        claim_presence_options: ClaimPresenceOptions {
            issued_at: Presence::Required,
            expiry: Presence::Required,
            audience: Presence::Required,
            not_before: Presence::Optional,
            issuer: Presence::Optional,
            subject: Presence::Optional,
            id: Presence::Optional,
        },
        temporal_options: TemporalOptions {
            epsilon: Duration::seconds(1),
            now: None,
        },
        // Check that iat is not in the future, but don't worry about it being too old of a token.
        issued_at: Validation::Validate(TimeDelta::MAX),
        // Check that token has not expired.
        expiry: Validation::Validate(()),
        not_before: Validation::Ignored,
        issuer: Validation::Ignored,
        audience: Validation::Ignored,
    };
    claims_set.registered.validate(validation_options)
}

/// A key id for use in testing. The JWT should have the same key id as its JWK.
pub const TEST_KEY_ID_1: &str = "my_key_id_1";

/// Second key ID for use in testing
pub const TEST_KEY_ID_2: &str = "my_key_id_2";

/// An octet secret to encrypt JWTs and to set up a JWK in tests.
pub const TEST_SECRET_1: &[u8] = b"0123456789ABCDEF";

/// An octet secret to encrypt JWTs and to set up a JWK in tests.
pub const TEST_SECRET_2: &[u8] = b"ABCDEF0123456789";

/// Name of the REAPI instance to use in requests.
pub const TEST_INSTANCE_NAME: &str = "main";

/// A JWK Set useful for tests.
///
/// This uses TEST_KEY_ID_1 and TEST_SECRET_1 to create the key. When creating a JWT that will be
/// validated by this JWK Set, be sure to use the same key ID and secret.
pub fn make_jwk_set() -> JWKSet {
    let jwk = JWK {
        common: biscuit::jwk::CommonParameters {
            key_id: Some(TEST_KEY_ID_1.to_owned()),
            algorithm: Some(Algorithm::Signature(SignatureAlgorithm::HS256)),
            ..Default::default()
        },
        algorithm: biscuit::jwk::AlgorithmParameters::OctetKey(biscuit::jwk::OctetKeyParameters {
            value: TEST_SECRET_1.to_vec(),
            key_type: Default::default(),
        }),
        additional: Default::default(),
    };
    JWKSet { keys: vec![jwk] }
}

/// Makes a JWKSet with multiple keys.
pub fn make_jwk_set_multiple() -> JWKSet {
    let jwk1 = JWK {
        common: biscuit::jwk::CommonParameters {
            key_id: Some(TEST_KEY_ID_1.to_owned()),
            algorithm: Some(Algorithm::Signature(SignatureAlgorithm::HS256)),
            ..Default::default()
        },
        algorithm: biscuit::jwk::AlgorithmParameters::OctetKey(biscuit::jwk::OctetKeyParameters {
            value: TEST_SECRET_1.to_vec(),
            key_type: Default::default(),
        }),
        additional: Default::default(),
    };
    let jwk2 = JWK {
        common: biscuit::jwk::CommonParameters {
            key_id: Some(TEST_KEY_ID_2.to_owned()),
            algorithm: Some(Algorithm::Signature(SignatureAlgorithm::HS256)),
            ..Default::default()
        },
        algorithm: biscuit::jwk::AlgorithmParameters::OctetKey(biscuit::jwk::OctetKeyParameters {
            value: TEST_SECRET_2.to_vec(),
            key_type: Default::default(),
        }),
        additional: Default::default(),
    };
    JWKSet {
        keys: vec![jwk1, jwk2],
    }
}

/// Generate a JWT string for tests.
pub fn generate_jwt(audience: &str, instance_name: &str, key_id: &str, secret: &[u8]) -> String {
    let issued_at = Some(biscuit::Timestamp::from(
        chrono::Utc::now() - chrono::Duration::minutes(5),
    ));
    let expiry = Some(biscuit::Timestamp::from(
        chrono::Utc::now() + chrono::Duration::minutes(5),
    ));
    let decoded_jwt = JWT::new_decoded(
        biscuit::jws::Header {
            registered: biscuit::jws::RegisteredHeader {
                key_id: Some(key_id.to_owned()),
                ..Default::default()
            },
            private: Default::default(),
        },
        ClaimsSet {
            registered: biscuit::RegisteredClaims {
                issued_at,
                expiry,
                audience: Some(biscuit::SingleOrMultiple::Single(audience.to_owned())),
                ..Default::default()
            },
            private: PrivateClaims {
                toolchain_customer: instance_name.to_owned(),
            },
        },
    );
    let encoded_jwt = decoded_jwt
        .into_encoded(&biscuit::jws::Secret::Bytes(secret.to_vec()))
        .unwrap();
    encoded_jwt.unwrap_encoded().to_string()
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;
    use std::str::FromStr;

    use crate::auth::{
        generate_jwt, get_bearer_token, make_jwk_set, validate_auth_token,
        validate_claims_defined_and_not_expired, validate_jwt, AuthToken, AuthTokenEntry,
        ClaimsSet, Permissions, PrivateClaims, TEST_INSTANCE_NAME, TEST_KEY_ID_1, TEST_SECRET_1,
    };
    use biscuit::errors::ValidationError;
    use biscuit::{RegisteredClaims, SingleOrMultiple, Timestamp};
    use chrono::Duration;
    use tonic::metadata::{AsciiMetadataKey, AsciiMetadataValue, MetadataMap};
    use tonic::{Code, Status};

    #[test]
    fn test_validate_auth_token() {
        fn validate(token: &str, requested_instance_name: &str) -> Result<(), Status> {
            let mut token_mapping = HashMap::new();
            token_mapping.insert(
                AuthToken::new("inactive-token".to_owned()),
                AuthTokenEntry {
                    id: "abc".to_owned(),
                    is_active: false,
                    instance_name: "abc".to_string(),
                    customer_slug: "my-customer".to_string(),
                },
            );
            token_mapping.insert(
                AuthToken::new("active-token".to_owned()),
                AuthTokenEntry {
                    id: "xyz".to_owned(),
                    is_active: true,
                    instance_name: "abc".to_string(),
                    customer_slug: "my-customer".to_string(),
                },
            );
            validate_auth_token(
                AuthToken::new(token.to_owned()),
                requested_instance_name,
                &token_mapping,
            )
        }

        assert_eq!(
            validate("missing-token", "abc").expect_err("").code(),
            Code::Unauthenticated
        );
        assert_eq!(
            validate("inactive-token", "abc").expect_err("").code(),
            Code::Unauthenticated
        );
        assert!(validate("active-token", "abc").is_ok());
        assert_eq!(
            validate("inactive-token", "xyz").expect_err("").code(),
            Code::Unauthenticated
        );
    }

    #[test]
    fn test_validate_jwt() {
        fn validate(
            token: Option<&str>,
            requested_instance_name: &str,
            required_permissions: Permissions,
        ) -> Result<(), Status> {
            let mut metadata = MetadataMap::new();
            if let Some(token) = token {
                metadata.insert(
                    AsciiMetadataKey::from_str("authorization").unwrap(),
                    AsciiMetadataValue::try_from(token).unwrap(),
                );
            }
            let token = get_bearer_token(&metadata)?;
            validate_jwt(
                token,
                requested_instance_name,
                required_permissions,
                &make_jwk_set(),
            )
        }

        // All is good.
        let valid_token = generate_jwt(
            &Permissions::Read.to_string(),
            TEST_INSTANCE_NAME,
            TEST_KEY_ID_1,
            TEST_SECRET_1,
        );
        let valid_header = format!("Bearer {valid_token}");
        assert!(validate(Some(&valid_header), TEST_INSTANCE_NAME, Permissions::Read).is_ok());

        // Token must work with the JWS.
        let invalid_token = generate_jwt(
            &Permissions::Read.to_string(),
            TEST_INSTANCE_NAME,
            "bad_key_id",
            TEST_SECRET_1,
        );
        let invalid_header = format!("Bearer {invalid_token}");
        assert_eq!(
            validate(Some(&invalid_header), TEST_INSTANCE_NAME, Permissions::Read)
                .expect_err("")
                .code(),
            Code::Unauthenticated
        );
        let invalid_token = generate_jwt(
            &Permissions::Read.to_string(),
            TEST_INSTANCE_NAME,
            TEST_KEY_ID_1,
            b"bad_secret",
        );
        let invalid_header = format!("Bearer {invalid_token}");
        assert_eq!(
            validate(Some(&invalid_header), TEST_INSTANCE_NAME, Permissions::Read)
                .expect_err("")
                .code(),
            Code::Unauthenticated
        );

        // Requested instance name must match the token's instance name.
        // TODO: This will become a hard check after transition away from BuildBarn.
        // assert_eq!(
        //     validate(Some(&valid_header), "unknown instance", Permissions::Read)
        //         .expect_err("")
        //         .code(),
        //     Code::InvalidArgument
        // );

        // Spot check that the audience must match what's required. See
        // test_permissions_is_valid() for more comprehensive testing.
        let invalid_token = generate_jwt(
            "bad_audience",
            TEST_INSTANCE_NAME,
            TEST_KEY_ID_1,
            TEST_SECRET_1,
        );
        let invalid_header = format!("Bearer {invalid_token}");
        assert_eq!(
            validate(Some(&invalid_header), TEST_INSTANCE_NAME, Permissions::Read)
                .expect_err("")
                .code(),
            Code::PermissionDenied
        );

        // Auth header is required and must be well-formed.
        assert_eq!(
            validate(None, TEST_INSTANCE_NAME, Permissions::Read)
                .expect_err("")
                .code(),
            Code::Unauthenticated
        );
        assert_eq!(
            validate(
                Some("Invalid prefix: abc.xy.abc"),
                TEST_INSTANCE_NAME,
                Permissions::Read
            )
            .expect_err("")
            .code(),
            Code::Unauthenticated
        );
    }

    #[test]
    fn test_validate_claims_defined_and_not_expired() {
        fn validate(
            issued_at: Option<Timestamp>,
            expiry: Option<Timestamp>,
            audience: Option<biscuit::SingleOrMultiple<String>>,
        ) -> Result<(), ValidationError> {
            let claims = ClaimsSet {
                registered: RegisteredClaims {
                    issued_at,
                    expiry,
                    audience,
                    ..Default::default()
                },
                private: PrivateClaims {
                    toolchain_customer: TEST_INSTANCE_NAME.to_owned(),
                },
            };
            validate_claims_defined_and_not_expired(&claims)
        }

        // Missing required claims.
        assert_eq!(
            validate(None, None, None),
            Err(ValidationError::MissingRequiredClaims(vec![
                "exp".to_owned(),
                "iat".to_owned(),
                "aud".to_owned()
            ]))
        );

        // All good to go.
        let valid_issued_at = Some(Timestamp::from(
            chrono::Utc::now() - chrono::Duration::minutes(2),
        ));
        let valid_expiry = Some(Timestamp::from(
            chrono::Utc::now() + chrono::Duration::minutes(2),
        ));
        let valid_audience = Some(SingleOrMultiple::Single("cache_ro".to_owned()));
        assert_eq!(
            validate(valid_issued_at, valid_expiry, valid_audience.clone()),
            Ok(())
        );

        // Invalid issued_at (because it's in the future).
        let invalid_issued_at = Some(Timestamp::from(chrono::Utc::now() + Duration::minutes(3)));
        assert!(matches!(
            validate(invalid_issued_at, valid_expiry, valid_audience.clone()),
            Err(ValidationError::NotYetValid(_))
        ));

        // Invalid expiration (because it's expired).
        let invalid_expiry = Some(Timestamp::from(chrono::Utc::now() - Duration::minutes(3)));
        assert!(matches!(
            validate(valid_issued_at, invalid_expiry, valid_audience),
            Err(ValidationError::Expired(_))
        ));
    }

    #[test]
    fn test_permissions_is_valid_audience() {
        // Read permissions can be satisfied by cache_ro, cache_rw, or exec.
        assert!(Permissions::Read.is_valid(&SingleOrMultiple::Single("cache_ro".to_owned())));
        assert!(Permissions::Read.is_valid(&SingleOrMultiple::Single("cache_rw".to_owned())));
        assert!(Permissions::Read.is_valid(&SingleOrMultiple::Single("exec".to_owned())));
        assert!(!Permissions::Read.is_valid(&SingleOrMultiple::Single("bad".to_owned())));
        assert!(
            Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec!["cache_ro".to_owned()]))
        );
        assert!(
            Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec!["cache_rw".to_owned()]))
        );
        assert!(Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec!["exec".to_owned()])));
        assert!(Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec![
            "cache_ro".to_owned(),
            "bad".to_owned()
        ])));
        assert!(!Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec![])));
        assert!(!Permissions::Read.is_valid(&SingleOrMultiple::Multiple(vec!["bad".to_owned()])));

        // ReadWrite permissions require either cache_rw or exec.
        assert!(Permissions::ReadWrite.is_valid(&SingleOrMultiple::Single("cache_rw".to_owned())));
        assert!(Permissions::ReadWrite.is_valid(&SingleOrMultiple::Single("exec".to_owned())));
        assert!(!Permissions::ReadWrite.is_valid(&SingleOrMultiple::Single("cache_ro".to_owned())));
        assert!(!Permissions::ReadWrite.is_valid(&SingleOrMultiple::Single("bad".to_owned())));
        assert!(Permissions::ReadWrite
            .is_valid(&SingleOrMultiple::Multiple(vec!["cache_rw".to_owned()])));
        assert!(
            Permissions::ReadWrite.is_valid(&SingleOrMultiple::Multiple(vec!["exec".to_owned()]))
        );
        assert!(!Permissions::ReadWrite
            .is_valid(&SingleOrMultiple::Multiple(vec!["cache_ro".to_owned()])));
        assert!(
            Permissions::ReadWrite.is_valid(&SingleOrMultiple::Multiple(vec![
                "cache_rw".to_owned(),
                "bad".to_owned()
            ]))
        );
        assert!(!Permissions::ReadWrite.is_valid(&SingleOrMultiple::Multiple(vec![])));
        assert!(
            !Permissions::ReadWrite.is_valid(&SingleOrMultiple::Multiple(vec!["bad".to_owned()]))
        );

        // Execute permissions require exec.
        assert!(Permissions::Execute.is_valid(&SingleOrMultiple::Single("exec".to_owned())));
        assert!(!Permissions::Execute.is_valid(&SingleOrMultiple::Single("cache_ro".to_owned())));
        assert!(!Permissions::Execute.is_valid(&SingleOrMultiple::Single("cache_rw".to_owned())));
        assert!(!Permissions::Execute.is_valid(&SingleOrMultiple::Single("bad".to_owned())));
        assert!(Permissions::Execute.is_valid(&SingleOrMultiple::Multiple(vec!["exec".to_owned()])));
        assert!(!Permissions::Execute
            .is_valid(&SingleOrMultiple::Multiple(vec!["cache_ro".to_owned()])));
        assert!(!Permissions::Execute
            .is_valid(&SingleOrMultiple::Multiple(vec!["cache_rw".to_owned()])));
        assert!(
            Permissions::Execute.is_valid(&SingleOrMultiple::Multiple(vec![
                "exec".to_owned(),
                "bad".to_owned()
            ]))
        );
        assert!(!Permissions::Execute.is_valid(&SingleOrMultiple::Multiple(vec![])));
        assert!(!Permissions::Execute.is_valid(&SingleOrMultiple::Multiple(vec!["bad".to_owned()])));
    }
}

# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Our standard key pairs.
# Currently just the `toolchain` key pair.


resource "aws_key_pair" "toolchain" {
  key_name   = "toolchain"
  public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCCyQU3UxvpTmd9oY+apY1SrwDJyEO6+Zz4QOSeKlgPdMAQEhVKhrgBr/kJyF4vGAyqtUV+wbEbWmSDQG72dln3lh4zGsDRSjGgn2D7/LHNyyzXGx2zkYF1mZRIRr3qW26vfyHQ+Z8ePAgj95HO3tAxzTCo2SMgxVw1+rjoN10O2G5bjgcUVu29lsnsvxOsM/cKg5ApmwqqyqkRoGnhbOy37swIAGwDrb2k1nrHC/uQHrgjYJi/iHmziT8VreOtrJMuoiKBxKF1c9NCVMMDcakLen6VzqJaD7h3TvcrEUA5x4Fsfcp8WabgNeqQn70ZX/junI08tO0lSqAulwqbiqwJ toolchain"
}

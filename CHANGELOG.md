# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2021-09-11
### Fixed
- Removed legacy handling of now  non-existent error case.
- Updated the class selector for ads.
- Changed wrong path in Dockerfile for build.
- Log to console instead of file for logging.
- Removed failing fake_useragent package.

### Changed
- Reduced initial delay to 5 seconds.
- Deleted unused torrc file.
- Removed unused imports and torrequest package.
- Added square meter unit to generated chat message.
- Updated all feature selectors to current page-structure.
- Added more verbose exception logging.
- Removed more tor-specific code.
- Replaced tor requests with normal ones.
- Added more verbose exception logging for logging.
- Fixed path to main executable script for dockerfile.
- Sorted files into src and res directories for fs.
- Added simple Docker configuration for tor.

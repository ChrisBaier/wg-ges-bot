## v1.1.1 (2021-09-15)

### Fix

- Removed unrequired logging configuration
- Added logging to listing-parsing for better tracabaility
- Re-added torrequest as dependency to stop crashes

## v1.1.0 (2021-09-11)

### Refactor

- Reduced initial delay to 5 seconds
- Removed unused imports and torrequest package
- Updated all feature selectors to current page-structure
- Added more verbose exception logging
- Removed more tor-specific code
- Replaced tor requests with normal ones
- **logging**: Added more verbose exception logging

### Fix

- Removed legacy handling of now  non-existent error case
- Updated the class selector for ads
- **build**: Changed wrong path in Dockerfile
- **logging**: Log to console instead of file
- Removed failing fake_useragent package

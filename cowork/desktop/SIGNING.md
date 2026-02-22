# Code Signing & Notarization

## Current State: Ad-hoc (unsigned)

The app is currently configured for **unsigned/ad-hoc builds** so we can develop
and test without an Apple Developer account ($99/yr).

Users will see a Gatekeeper warning on first launch and must right-click > Open.

## How to enable signing + notarization later

### 1. electron-builder.json — revert these three changes:

```jsonc
// REMOVE this line (ad-hoc, skips signing):
"identity": null,

// CHANGE from false to true:
"hardenedRuntime": true,

// ADD this line back (above the "mac" key):
"afterSign": "./config/notarize.cjs",
```

### 2. Set environment variables:

```bash
export APPLE_ID="your@apple.id"
export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # Generate at appleid.apple.com
export APPLE_TEAM_ID="XXXXXXXXXX"                          # From developer.apple.com
```

### 3. Install your Developer ID Application certificate:

- Download from developer.apple.com > Certificates
- Double-click to install in Keychain Access
- electron-builder will find it automatically

### 4. Build:

```bash
npm run build:mac
```

The `config/notarize.cjs` hook will automatically submit to Apple for notarization
after signing. It already skips gracefully if env vars are missing.

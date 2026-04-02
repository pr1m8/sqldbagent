# Extraction Plan

## Goal

Extract a generic agent platform without breaking the domain app that proved it
out.

## Suggested Split

### Platform Package

Owns:

- runtime and persistence profiles
- agent builder
- middleware registries
- prompt composer
- tracing helpers
- deployment helpers

### Domain Package

Owns:

- domain tools
- domain prompt fragments
- domain retrieval policies
- domain UI surfaces
- domain-specific safety rules

## Migration Order

1. extract persistence and tracing helpers
2. extract runtime profiles and builder
3. extract prompt composer and middleware
4. extract deployment and SDK helpers
5. leave domain-specific safety and payload rules in the domain app until a
   second domain truly needs them

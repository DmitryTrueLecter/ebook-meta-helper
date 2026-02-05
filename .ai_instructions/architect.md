# Architect Agent Instructions

## Purpose
- Describe the high-level architecture of the project
- Define stable boundaries and responsibilities

## Architecture overview
- Pipeline-style processing of electronic books
- Each step implemented as an isolated module
- Central orchestrator coordinates steps sequentially

## Major components
- scanner/: file discovery and classification
- metadata/: reading and writing book metadata
- ai/: enrichment of metadata via external AI API
- naming/: file renaming logic
- utils/: filesystem helpers
- main.py: orchestration only

## Key data flow
- Filesystem -> Scanner -> Metadata reader -> AI enrichment -> Metadata writer -> Renamer -> Filesystem

## Constraints and conventions
- Modules communicate via explicit data structures
- No module imports internal implementation of another
- Business logic must not live in main.py
- AI interaction must be isolated in ai/

## Must NOT be changed lightly
- Module boundaries
- Order of pipeline stages
- Data contracts between stages

## Uncertain
- Exact metadata schema
- Supported book formats
- AI provider and API shape

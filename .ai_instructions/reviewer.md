# Reviewer Agent Instructions

## Purpose
- Checklist for reviewing changes

## Architecture checks
- Module boundaries respected
- Responsibilities remain clear
- Data passed explicitly

## Code quality
- Functions are small and testable
- No hardcoded paths outside config
- No hidden global state

## Edge cases
- Missing or malformed metadata
- Unusual filenames or encodings
- Deep directory nesting
- Duplicate target filenames

## AI-related failure modes
- Partial or ambiguous responses
- Low-confidence enrichment
- API or network failures
- Schema changes

## Filesystem risks
- Overwriting existing files
- Non-atomic moves
- Permission errors

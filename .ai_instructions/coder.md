# Coder Agent Instructions

## Purpose
- Rules for implementing code changes

## General rules
- One logical change per commit
- Small, composable functions
- Explicit inputs and outputs

## Scope limits
- Do not mix responsibilities across modules
- Do not add orchestration logic outside main.py
- Do not bypass metadata reader/writer

## Style rules
- Python, standard library first
- Shared data models should be explicit (uncertain)
- No side effects in pure logic modules

## Dependencies
- Avoid new third-party dependencies
- Any dependency must be isolated to one module
- AI SDK usage only in ai/

## Error handling
- Fail explicitly
- Do not silently ignore errors
- Prefer structured error reporting

## Uncertain
- Logging framework
- Configuration mechanism

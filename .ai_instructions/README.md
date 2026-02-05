# AI Agents Usage

## Purpose
- Explain how to use AI agents for this repository

## Workflow
- One role per chat session
- Do not mix roles

## Roles
- architect: architecture and high-level decisions
- coder: implement changes
- reviewer: review diffs and risks
- memory: record long-term decisions

## Memory update process
1. Finalize a decision with architect
2. Summarize the outcome
3. Ask memory agent to record it
4. Treat memory.md as authoritative

## Rules
- Agents rely only on repository content
- Unclear points must be marked as uncertain
- Do not invent missing details
